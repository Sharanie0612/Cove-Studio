# Contributing to Cove Studio

Build the shared workbench or SDK here. Business tools belong in independent repositories. MCP is the only bundled plugin. Read [AGENTS.md](AGENTS.md), [architecture](docs/architecture.md) and the [SDK contract](docs/plugin-sdk.en.md) before changing host boundaries.

## Development

Follow the source setup in [README](README.md). Install test/build dependencies with:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.lock -r requirements-dev.txt
```

Run `npm run dev` and `npm run desktop:dev` in separate terminals. Keep credentials and user data outside source; integration tests use disposable hosts and fixtures. Browser preview does not execute local commands.

## Design and compatibility

- Keep SDK v1 additive. Capabilities need schema validation, host support, documentation and compatibility checks.
- Reuse shared surfaces, mounted workspaces, appearance and motion tokens. Keep business-plugin branches out of the host.
- Keep discovery metadata-only. Dependency installation, imports and network calls do not belong in scans.
- Preserve framing, approvals, client backups, user data and active work. Workers run with the current user's permissions; they are not an operating-system sandbox.
- Update Chinese and English together; follow [localization](docs/localization.md). Do not translate user data, plugin output or protocol identifiers.

## Validation

For product changes, run the checks in [AGENTS.md](AGENTS.md), including the complete Python and UI suites. Set `COVE_BROWSER_CHANNEL=msedge` on Windows or install Playwright Chromium. Check both languages, themes, reduced motion and the minimum window for UI changes.

Desktop delivery also requires a new installer, frozen runtime/MCP checks, a native-window check and a disposable baseline upgrade. See [Windows delivery](docs/windows-release.md). Preserve the user's running Cove; never force-close it for a test.

For documentation-only changes, run `npm run test:contribution`. Translation changes also need `npm run test:i18n` and relevant UI checks. Report checks as passed, failed, not run with a reason, or not applicable with a reason. A successful build does not prove installation or real-client behavior.

## Commit and PR conventions

Keep one coherent change per PR. Suggested branches: `feat/language-switcher`, `fix/mcp-status`, `docs/setup-guide`; a particular branch name is not required. When authorized to commit, stage only related files.

PR titles follow `type(scope): concise summary`. Scope is optional and uses lowercase letters, digits or hyphens. Allowed types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. Use `!` before the colon for breaking changes and explain migration. Titles must be one line, at most 96 characters, with a meaningful summary. Chinese and English summaries are accepted.

```text
feat(i18n): add English interface and persistent language selection
fix(mcp): preserve client errors until retry
docs: clarify installation and verification requirements
feat(sdk)!: replace a public surface contract
```

Commit subjects should use the same format. Prefer a squash merge with the reviewed PR title unless maintainers choose another strategy. Check locally with `npm run test:contribution -- --title "feat(i18n): add English interface"`; the PR workflow checks it too.

Use the [PR template](.github/pull_request_template.md). Lead with the user problem and resulting behavior; explain migrations when relevant. Include affected language/theme screenshots. Separate source tests, frozen payload, native interaction, actual upgrade and real client evidence. List remaining unverified outcomes.

Do not commit tokens, personal configuration, local data, virtual environments, installers, generated reports or validation logs. Store delivery artifacts outside the source change. Opening a PR or publishing a release requires authorization; implementation and a prepared description do not imply publication.

## License

Core and SDK contributions use [MIT](LICENSE). Preserve dependencies' and plugins' own licenses and notices. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) and the [publication checklist](docs/open-source.md).
