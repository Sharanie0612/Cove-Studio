# Core publication boundary

Only the built-in MCP service belongs in `plugins/projects/`. Generic SDK templates and disposable fixtures belong in `docs/templates`, `docs/examples` and `tests`.

Run `python scripts/audit_core.py`, the regression suites and the Windows delivery checks before publishing. Source archives use an explicit allowlist and audit their contents. Do not add local state, credentials, build dependencies or generated artifacts to commits. Keep original third-party notices for the dependencies actually shipped. Publication does not establish code-signing reputation or target-client success.
