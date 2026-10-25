# Plugin-owned interface example

Download the complete SDK starter from Cove's Developer Guide. This example includes its own HTML, CSS and JavaScript in `ui/index.html`. It needs no frontend dependencies.

Run `python -S dev.py snapshot` to exercise the Python implementation and `python -S package.py` to build the plugin package. Import that package into Cove 0.13.0 or later. Use Read counter, then Increment: the latter must show a confirmation in the trusted Cove interface before the value changes.

The iframe uses `window.Cove.ready`, `Cove.call(name, arguments)` and `Cove.on('context'|'event', callback)`. It cannot access the host's DOM, native API, filesystem or another plugin through this bridge. Reads do not require AI sharing. Declared writes always require Cove approval, including when MCP is disabled. Closing the interface invalidates its pending approvals.

See [plugin UI contract](../../plugin-ui.md) in the core documentation for bounds, lifecycle and trust limitations.
