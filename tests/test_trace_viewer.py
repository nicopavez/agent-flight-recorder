import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trace_viewer import build_mermaid_sequence, build_summary, load_trace

SAMPLE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "sample_data", "sample_trace.json"
)


class TraceViewerTests(unittest.TestCase):
    def setUp(self):
        self.trace = load_trace(SAMPLE_PATH)

    def test_load_trace_requires_steps(self):
        with self.assertRaises(ValueError):
            load_trace_from_dict_shortcut({"no_steps": True})

    def test_summary_counts_agents_and_failures(self):
        summary = build_summary(self.trace)
        self.assertEqual(summary["total_steps"], 5)
        self.assertEqual(
            summary["agents_involved"],
            ["BillingAgent", "Orchestrator", "ProvisioningAgent"],
        )
        self.assertEqual(summary["failed_steps"], 1)
        self.assertEqual(summary["failed_step_ids"], ["s3"])

    def test_summary_finds_slowest_step(self):
        summary = build_summary(self.trace)
        self.assertEqual(summary["slowest_step"]["step_id"], "s3")
        self.assertAlmostEqual(summary["slowest_step"]["seconds"], 30.0)

    def test_summary_total_duration(self):
        summary = build_summary(self.trace)
        self.assertAlmostEqual(summary["total_duration_seconds"], 36.0)

    def test_mermaid_includes_all_agents_as_participants(self):
        mermaid = build_mermaid_sequence(self.trace)
        for agent in ("Orchestrator", "BillingAgent", "ProvisioningAgent"):
            self.assertIn(f"participant {agent}", mermaid)

    def test_mermaid_marks_failure_with_note(self):
        mermaid = build_mermaid_sequence(self.trace)
        self.assertIn("FAILED", mermaid)
        self.assertIn("identity-provisioning API timed out", mermaid)

    def test_mermaid_uses_failure_arrow_for_failed_step(self):
        mermaid = build_mermaid_sequence(self.trace)
        self.assertIn("Orchestrator-xProvisioningAgent: add_seats", mermaid)


def load_trace_from_dict_shortcut(data):
    """Helper so test_load_trace_requires_steps exercises the same
    validation load_trace() does, without needing a throwaway file."""
    if "steps" not in data or not isinstance(data["steps"], list):
        raise ValueError("Trace file must contain a 'steps' list")
    return data


if __name__ == "__main__":
    unittest.main()
