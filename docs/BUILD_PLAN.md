# Build Plan: the Workato side

`trace_viewer.py` is done and tested. It works today, against the sample
trace, independent of Workato. This is the other half: building the
recorder itself as a Workato recipe, so real agents can write to it, and
exposing it as an MCP server so any agent can call it.

Written as a runbook because this part happens in Workato's UI, in your
sandbox. I can't drive that from here.

## 1. Create the Data Table

**Workato → Data Tables → New Table**: name it `agent_trace_steps`, with
columns matching the trace schema `trace_viewer.py` already expects:

| Column | Type |
|---|---|
| `session_id` | Text |
| `step_id` | Text |
| `parent_step_id` | Text (nullable) |
| `agent_name` | Text |
| `action` | Text |
| `input_summary` | Text |
| `output_summary` | Text (nullable) |
| `status` | Text (`success` / `failure` / `in_progress`) |
| `error_message` | Text (nullable) |
| `started_at` | Date/Time |
| `ended_at` | Date/Time (nullable) |

Keeping this identical to the JSON shape in `sample_data/sample_trace.json`
means `trace_viewer.py` can read a real export with zero changes.

## 2. Build the `record_step` recipe

**New recipe → API Platform trigger** (request-response), input schema
matching the table columns above (all optional except `session_id`,
`agent_name`, `action`, `status`).

Steps:
1. Generate a `step_id` if one wasn't provided (formula: a UUID or
   timestamp-based ID).
2. Insert a row into `agent_trace_steps` with the input fields.
3. Respond with the generated `step_id`.

This is the tool other agents call after each step of their work:
*"log that I just did X, here's what happened."*

**Known issue on the trial plan:** don't wrap `step_id` (or any field) in
a conditional formula (`if()`/ternary) that also references a data pill
in this action's field editor: e.g. `if(step_id.blank?, SecureRandom.uuid,
step_id)` reliably fails the recipe's "Formula has errors" check on
Start, regardless of what's inside the branches (tested with
`SecureRandom.uuid`, `Time.now.strftime(...)`, and a plain string
literal; all three failed once combined with `if()` + a pill, and all
three work individually with no pill, and a bare pill with no formula also
works). Root cause not identified beyond "this Workato trial workspace's
Data Table connector rejects conditional-formula + pill combos in New
record fields." Current workaround: `step_id` is a plain pill (Text
mode, no formula) mapped straight from the request's `Step ID`. If the
caller doesn't supply one, it's just left blank rather than
auto-generated.

## 3. Build the `get_trace` recipe

**New recipe → API Platform trigger**, input: `session_id`.

Steps:
1. Query `agent_trace_steps` where `session_id` matches, ordered by
   `started_at`.
2. Shape the result into `{"session_id": ..., "steps": [...]}`, the
   exact shape `trace_viewer.py` expects.
3. Respond with that JSON.

Test this by exporting its output straight into `trace_viewer.py`:

```
python trace_viewer.py exported_trace.json
```

If it runs without modification, the contract matches.

## 4. Expose both via Enterprise MCP

**AI Hub → Enterprise MCP → Create MCP Server**, source: Project assets,
select both recipes. Name the tools `record_step` and `get_trace` so an
agent's tool-calling makes the intent obvious. Add an instruction for the
calling LLM: *"Call record_step after completing any meaningful action.
Call get_trace to review what happened in a past run."*

Same caveat as always: this may hit a paid-plan wall in the dev sandbox.
Screenshot whichever happens (a working MCP URL, or the upgrade prompt)
for `docs/screenshots/`.

## 5. Generate a real demo trace

The sample trace is hand-written. For a stronger demo, actually run a
small multi-agent task (two or three Claude/GPT agent calls chained
together, even a simple script that plays "Orchestrator," "AgentA,"
"AgentB") and have each step call `record_step`. Pull the result with
`get_trace` and run it through `trace_viewer.py`. A diagram built from a
real run is a meaningfully stronger artifact than one built from fixture
data.

## 6. Export and assemble

The `workato` Python CLI (`pip install workato-platform-cli`) is
deprecated and can't authenticate against a trial-tenant workspace no
matter what scopes its token has. Use the newer Go-based CLI instead
([workato-devs/wk](https://github.com/workato-devs/wk)):

```
wk auth login --token <token> --environment dev --region trial --no-input
wk clone "hello-world" --local-path recipe --no-input
```

`region trial` (Developer Sandbox) is the key flag the old CLI never
had; that's what actually lets it authenticate here. The token needs a
Client Role with, at minimum: Projects & folders, Resources, Recipes,
**Export manifests** (under Recipe lifecycle management, this is the
one that's easy to miss and the clone will 401 without it), and
Workspace details (under Admin, needed for the `/users/me` check
`wk auth login` does up front). Build these in **Workspace admin → API
clients → Client roles**.

Copy the exported files into `recipe/`, add your screenshots to
`docs/screenshots/`, update the checklist in `README.md`, then:

```
git init
git add .
git commit -m "Agent Flight Recorder: MCP-based tracing for multi-agent handoffs"
gh repo create agent-flight-recorder --public --source=. --push
```

Or send me the exported recipe files and screenshots and I'll assemble
the final zip.
