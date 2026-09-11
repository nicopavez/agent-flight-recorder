"""
Agent Flight Recorder — trace viewer.

Takes a recorded multi-agent run (the same shape `get_trace` returns from
the Workato-side MCP server) and turns it into two things a human can
actually use to debug what happened:

1. A Mermaid sequence diagram — who handed off to whom, in what order,
   and where something failed.
2. A plain-text run summary — agents involved, failures, and how long
   each step took.

This is deliberately independent of Workato: the trace format is a plain
JSON contract, so this viewer works whether the trace came from the
Workato recipe, a test fixture, or any other orchestrator that adopts the
same schema.

Usage:
    python trace_viewer.py sample_data/sample_trace.json
    python trace_viewer.py sample_data/sample_trace.json --mermaid-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_trace(path: str) -> dict:
    with open(path) as f:
        data = json.load(f)
    if "steps" not in data or not isinstance(data["steps"], list):
        raise ValueError("Trace file must contain a 'steps' list")
    return data


def _caller_of(step: dict, steps_by_id: dict[str, dict]) -> str:
    parent_id = step.get("parent_step_id")
    if parent_id and parent_id in steps_by_id:
        return steps_by_id[parent_id]["agent_name"]
    return "Orchestrator"


def build_mermaid_sequence(trace: dict) -> str:
    steps = trace["steps"]
    steps_by_id = {s["step_id"]: s for s in steps}

    participants: list[str] = []
    for s in steps:
        for name in (_caller_of(s, steps_by_id), s["agent_name"]):
            if name not in participants:
                participants.append(name)

    lines = ["sequenceDiagram"]
    for name in participants:
        lines.append(f"    participant {name.replace(' ', '_')}")

    for s in steps:
        caller = _caller_of(s, steps_by_id).replace(" ", "_")
        callee = s["agent_name"].replace(" ", "_")
        action = s["action"]
        status = s.get("status", "unknown")
        arrow = "->>" if status == "success" else "-x"
        lines.append(f"    {caller}{arrow}{callee}: {action}")
        if status == "failure":
            err = s.get("error_message", "failed")
            lines.append(f"    Note over {callee}: FAILED — {err}")
        else:
            out = s.get("output_summary")
            if out:
                lines.append(f"    {callee}-->>{caller}: {out}")

    return "\n".join(lines)


def build_summary(trace: dict) -> dict[str, Any]:
    steps = trace["steps"]
    agents = sorted({s["agent_name"] for s in steps})
    failures = [s for s in steps if s.get("status") == "failure"]

    starts = [t for t in (_parse_ts(s.get("started_at")) for s in steps) if t]
    ends = [t for t in (_parse_ts(s.get("ended_at")) for s in steps) if t]
    duration_seconds = None
    if starts and ends:
        duration_seconds = (max(ends) - min(starts)).total_seconds()

    slowest = None
    for s in steps:
        start, end = _parse_ts(s.get("started_at")), _parse_ts(s.get("ended_at"))
        if start and end:
            secs = (end - start).total_seconds()
            if slowest is None or secs > slowest[1]:
                slowest = (s["step_id"], secs, s["action"])

    return {
        "session_id": trace.get("session_id"),
        "total_steps": len(steps),
        "agents_involved": agents,
        "failed_steps": len(failures),
        "failed_step_ids": [s["step_id"] for s in failures],
        "total_duration_seconds": duration_seconds,
        "slowest_step": (
            {"step_id": slowest[0], "seconds": slowest[1], "action": slowest[2]}
            if slowest
            else None
        ),
    }


def format_summary_text(summary: dict[str, Any]) -> str:
    lines = [
        f"Session: {summary['session_id']}",
        f"Steps: {summary['total_steps']}  |  "
        f"Agents involved: {', '.join(summary['agents_involved'])}",
    ]
    if summary["total_duration_seconds"] is not None:
        lines.append(f"Total duration: {summary['total_duration_seconds']:.1f}s")
    if summary["failed_steps"]:
        lines.append(
            f"Failures: {summary['failed_steps']} "
            f"(step ids: {', '.join(summary['failed_step_ids'])})"
        )
    else:
        lines.append("Failures: none")
    if summary["slowest_step"]:
        slow = summary["slowest_step"]
        lines.append(
            f"Slowest step: {slow['action']} ({slow['step_id']}) — {slow['seconds']:.1f}s"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_file", help="Path to a trace JSON file")
    parser.add_argument(
        "--mermaid-only", action="store_true", help="Print only the Mermaid diagram"
    )
    args = parser.parse_args()

    trace = load_trace(args.trace_file)
    mermaid = build_mermaid_sequence(trace)

    if args.mermaid_only:
        print(mermaid)
        return

    summary = build_summary(trace)
    print("=== Run Summary ===")
    print(format_summary_text(summary))
    print()
    print("=== Sequence Diagram (Mermaid) ===")
    print(mermaid)


if __name__ == "__main__":
    main()
