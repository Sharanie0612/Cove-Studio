# Cove Studio core — agent instructions

## Scope and architecture

- This checkout contains the generic desktop host, SDK and disposable fixtures. MCP is the only bundled plugin. Business tools, identities, guides, packages and screenshots belong in independent projects.
- Discovery and archive inspection read metadata only. Never import or execute plugin code during a scan.
- Keep transport, lifecycle policy, SDK, plugin management, client configuration and native windows in their existing modules. Execution budgets, activity guards and diagnostics belong in `toolbench/plugin_framework`; shared surfaces and workspaces belong in `src/framework`.
- Keep management navigation on the left and mounted workspaces in top tabs. AI authorization and MCP client configuration are separate workflows. Preserve plugin independence; do not add plugin-specific branches to shared orchestration.

## Preserve work and permissions

- Inspect the checkout before editing. Preserve unrelated changes, saved configurations, connections and background work. Never force-close an existing application.
- Use disposable hosts, data directories and fixtures for tests. Do not use a personal Cove data directory, browser profile or client configuration.
- Keep stdout protocol-only. Never log credentials, raw private configuration or secret command arguments. Each tool write requires Cove approval.
- Do not stage unrelated files. Do not commit, push, publish, create a PR or change the user's installation unless requested. Building and testing a disposable installer does not authorize release publication.

## Interface and localization

- Reuse shared appearance, spacing, radius and motion tokens. Verify light/dark modes, reduced motion and the 960 × 660 minimum window.
- Simplified Chinese and English are supported. Add host-owned copy through `t()` and update `src/locales/en-US.json` in the same change. Use complete messages and interpolation parameters; do not assemble translated sentences from fragments.
- Translate labels, tooltips, accessible names, confirmations, empty states and help. Keep protocol names, paths, identifiers, user data, plugin output and executable examples intact. Plugins own their business translations.
- Resolve plugin-owned catalogs through `localization` and the SDK `Context.locale` / `Context.t()` contract. Keep business messages out of the host catalog; missing translations fall back to source text.
- Resolve translations during render/call time, not module initialization. Language changes must preserve mounted workspaces, drafts, terminal instances and active connections.
- Follow [localization](docs/localization.md). Do not advertise a language without a complete catalog and layout checks.

## Checks and delivery

Run these checks from the repository root and fix affected failures:

```powershell
.venv\Scripts\python.exe scripts/audit_core.py
npm run format:check
npm run test:i18n
npm run test:contribution
npm run test:frontend
.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run build
npm run test:ui
```

- Product changes also require a new Windows installer built with `.venv`, frozen runtime/MCP checks, a native-window check and a disposable baseline-to-candidate upgrade. Use [Windows delivery](docs/windows-release.md).
- Keep `package.json`, `package-lock.json`, `pyproject.toml` and `toolbench.__version__` aligned. Preserve earlier release artifacts.
- Report source checks, payload, frozen runtime, native interaction and upgrade evidence separately. Give exact paths and hashes. Frame checks do not prove real pointer drag or Snap behavior; client profile generation does not prove model calls in every client.
- Documentation-only changes need documentation/contribution checks. Record exact limitations for any required checks that cannot run; never imply unrelated validation passed.

## Commits and pull requests

- Follow [CONTRIBUTING.md](CONTRIBUTING.md) and `.github/pull_request_template.md`.
- PR titles use `type(scope): summary`; scope is optional. Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. Use `!` for a breaking change and explain migration.
- Lead descriptions with the user problem and resulting behavior. Include validation, screenshots for affected themes/languages, compatibility changes and unverified outcomes. Describe the final implementation.
- Prepare a concrete, reviewable result before requesting publication approval. Never invent passing checks, remote CI results or installed-upgrade evidence.
