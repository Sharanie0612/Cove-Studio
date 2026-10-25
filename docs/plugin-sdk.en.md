# Cove plugin SDK v1

Cove supplies the workspace, forms, themes, terminal, result views and task controls.
Your Python plugin supplies commands, data and resource cleanup. You do not need
React, a frontend build or a change to Cove's registration code to add a tool.

## Start with a working example

Download the developer starter from Cove's Developer Guide. The ZIP includes a
standalone SDK and four projects:

| Project | Purpose | Run from that project's directory |
| --- | --- | --- |
| Starter root | A minimal command returning JSON | `python -S dev.py greet name=Cove` |
| `examples/result-starter` | Summary cards and a paginated table | `python -S dev.py analyze "text=Hello Cove hello"` |
| `examples/web-starter` | A sandboxed plugin-owned interface | `python -S dev.py snapshot` |
| `examples/job-starter` | Progress, cancellation and safe background activity | `python -S dev.py` |

The job example's dedicated command-line runner waits for a short demonstration
to finish. Import it in Cove to observe progress and exercise cancellation.
Run `python -S doctor.py` to inspect metadata and the selected Python environment,
then `python -S package.py` to produce a `.cove-plugin` in `exports/`. Import the
package on the Plugins page and open its card from Workbench. Python 3.11+ is required.
Each example has its own SDK and can be copied into a separate directory.

## The boundary

`manifest.json` declares fields, public commands, capabilities and UI bindings.
`plugin.py` exports `class Tool(Plugin)`. Only declared commands can be called.
Inputs and results must be JSON-serializable; validate inputs in Python as well as
the UI. Commands may execute concurrently: protect shared state with `self.lock`.
Release connections, threads and devices in an idempotent `close()`.

The optional `icon` selects a local Cove illustration: `terminal`, `plug`, `activity`,
`circuit-board`, `file-chart-column`, `list-todo`, `folder`, `wrench` or `braces`.
Missing or unknown names fall back to the declared surface capabilities. Icon
discovery does not load plugin code. Plugin illustrations share the original
Cove logo's black and white palette, rounded shapes, negative space and gentle
tilt. `color` remains accepted metadata; plugin artwork keeps its own brand ink.

Ordinary commands have a 20-second execution budget. Use `BackgroundJob` for
long work rather than holding a command open. Permission labels and worker process
isolation are not an OS security sandbox. Plugins run as the local user.

## Declarative result views (Cove 0.11.0)

Choose `ui.surface: "form"` and declare `ui.result`. `fields` displays top-level
result keys; `table.key` selects an array of row objects. Columns select keys in
each row. Keys are literal identifiers, not paths or executable expressions.

```json
{
  "compatibility": {"minHostVersion": "0.11.0", "capabilities": ["ui.result"]},
  "ui": {
    "result": {
      "title": "Measurements",
      "fields": [{"key": "count", "label": "Samples", "format": "number"}],
      "table": {"key": "rows", "columns": [
        {"key": "name", "label": "Name"},
        {"key": "voltage", "label": "Voltage", "format": "number", "unit": "V"}
      ]}
    }
  }
}
```

This is a fragment; retain the normal fields, actions and other manifest metadata.
Return `{"count": 2, "rows": [{"name": "A", "voltage": 3.3}, ...]}` from Python.
Formats are `text`, `number` and `json`. Layouts support up to 24 summary fields
and 12 table columns. The host paginates tables at 50 rows without discarding rows.
All text is escaped. No HTML, CSS, JavaScript, links or frontend component names
are executed from the manifest or result. Only explicitly selected keys appear.
Missing values display a dash. A missing or empty table displays its empty state.

Declare the `ui.result` capability explicitly. It cannot be combined with `ui.job`
or `ui.web`. Older SDK v1 plugins without this layout keep their JSON view;
metadata-free v1 manifests remain supported.

## Background jobs

Import `BackgroundJob` from `toolbench.sdk`, create one per plugin, bind
`ui.job.snapshot` and `ui.job.cancel` to public methods, and have the main action
call `job.start(callback, total=..., message=...)`. The callback receives a control
object with `update(completed=..., message=...)`, `check_cancelled()` and an
interruptible `wait(seconds)`. It returns an optional JSON object for the final
view; state defaults to `completed` and may explicitly be `partial`.

The helper emits `job` and `activity` events and manages revision numbers.
`cancel()` requests cooperative cancellation; the job stays active until its
callback actually exits. Use bounded I/O and check cancellation between operations.
Call `job.close()` from `Tool.close()`. It waits for a bounded period and does not
claim to forcibly stop non-cooperative callbacks. The helper does not roll back
external effects, persist tasks, or resume work after a process exits.

## Terminal, plugin-owned UI and AI integration

Terminal plugins bind connect/disconnect/write/resize commands and emit text events.
Plugins can also ship a self-contained interface through `ui.web` on Cove 0.13.0+.
Its HTML/CSS/JavaScript runs in an opaque-origin iframe and calls declared commands
through a controlled bridge. Writes require Cove confirmation; AI grants remain
separate. Domain controls and polling belong to the plugin. See the
[plugin UI contract](plugin-ui.md) and [detailed SDK reference](plugin-sdk.md).

Declare AI tools with JSON Schema and an accurate `readOnly` flag. In Cove, grant
access on Agent Tools, open MCP from Workbench, save the target client's configuration,
then start/reload its adapter in that client and perform a real tool call. Saved
configuration alone does not establish a working connection. Writes require Cove
approval. Portable MCP/DSH exports share Python commands but do not supply Cove's
desktop UI, live device sessions or write approvals; only read-only tools are exposed.

## Before sharing

Test invalid input, repeated runs, cancellation, closing an active task, switching
pages, dark mode and a fresh import. Discovery and package inspection must never
execute plugin code. Export excludes local data, environments and SDK development
files. New host capabilities require a contract and a shared renderer before they
can be advertised as supported.
