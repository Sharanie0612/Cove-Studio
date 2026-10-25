# Windows build and delivery

Use the project virtual environment from the repository root. Keep a previously validated installer for the upgrade check. Native-window checks need an interactive Windows session; browser screenshots do not verify native dragging.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.lock -r requirements-dev.txt
.venv\Scripts\python.exe scripts/audit_core.py
npm run test:i18n
npm run test:contribution
npm run test:frontend
npm run format:check
.venv\Scripts\python.exe -m unittest discover -s tests
npm run build
npx playwright install chromium
npm run test:ui
.venv\Scripts\python.exe scripts/build_windows.py
$version = (Get-Content package.json | ConvertFrom-Json).version
.venv\Scripts\python.exe scripts/verify_packaged.py "artifacts/desktop-$version/Cove"
.venv\Scripts\python.exe scripts/verify_mcp.py "artifacts/desktop-$version/Cove"
.venv\Scripts\python.exe scripts/verify_runtime.py "artifacts/desktop-$version/Cove"
.venv\Scripts\python.exe scripts/verify_sdk_examples.py "artifacts/desktop-$version/Cove"
.venv\Scripts\python.exe scripts/verify_release_payload.py "artifacts/desktop-$version/Cove"
.venv\Scripts\python.exe scripts/verify_window_frame.py
```

On Windows, `$env:COVE_BROWSER_CHANNEL='msedge'` uses an installed Edge for browser checks instead of downloading Chromium.

When the build interpreter ships `codex-rejected-cas.pem` beside `ssl.py`, packaging
retains that trust-policy file unchanged beside the frozen standard library.
Without it, that interpreter's `SSLContext` initialization fails even when an
HTTP-only MCP bridge constructs urllib's default handlers. Packaged MCP calls
verify this dependency as part of delivery.

| Artifact | Contents |
| --- | --- |
| `artifacts/Cove-<version>-setup.exe` | Per-user Windows installer |
| `artifacts/Cove-<version>-windows.zip` | Portable application folder |
| `artifacts/Cove-<version>-bundle.zip` | Exported installer, MCP package and guides |
| `artifacts/Cove-<version>-source.zip` | Corresponding core and plugin source inputs, licenses and build scripts |
| `plugins/packages/` | Individual plugin and portable MCP packages |

## Export and verify the delivered file

After building, run this from a normal PowerShell session. Use a **new folder outside the workspace**:

```powershell
scripts/export_windows_release.ps1 -Destination "$env:USERPROFILE\Downloads\Cove-$version"
.venv\Scripts\python.exe scripts/verify_versioned_installer.py `
  --baseline "C:\path\to\previous-validated-setup.exe" `
  --candidate "$env:USERPROFILE\Downloads\Cove-$version\Cove-$version-setup.exe" `
  --desktop-check
```

The export checks SHA-256 hashes and rejects Low-integrity destinations without changing permissions. An executable that inherits a sandbox workspace's Low integrity label can fail with **“Error writing temporary file”** before the wizard opens. Validate the exact delivered path with normal `TEMP` and `TMP`. Do not change Windows protection settings or treat a successful relocated test as validation of the workspace original.

The upgrade check uses disposable install and user-data folders. With `--desktop-check`, it opens an actual old desktop, verifies that installation is blocked, requests a normal exit and only then upgrades. It also verifies identical reinstalls, stable-entry launches, owned shortcut repair, active old MCP adapters, locked files and uninstall preservation. Run it sequentially in both languages. Do not overlap installer runs or native desktop checks: the installer mutex intentionally blocks desktop startup. Existing personal Cove sessions must remain untouched. Frozen tests, installation success, UI inspection and real hardware behavior are separate evidence.

## Installer appearance

Starting with 0.12.11, interactive setup uses `src/setup/SetupApp.tsx` in an isolated temporary WebView. It imports the same local WOFF2 fonts, foundation/button styles, 8px control radii, 12px cards, appearance tokens and composited native frame as the main app. A native language dialog is not shown. Since 0.12.12, the wizard advances through language, location, license, installation and completion. Back/Next preserve selections. Progress reports engine phases and completed destination file sizes; preparation remains indeterminate and success requires the engine exit. Percentages are never advanced by a timer.

`toolbench/setup_ui.py` exposes only this setup's fixed engine and controls. It does not instantiate the normal host, load plugins, use a personal Cove directory or reset preferences. The browser profile is disposable and stored outside the runtime payload. After license/close consent, it waits for the NSIS silent engine, which retains mutex, normal-shutdown, versioned files, payload verification, activation and shortcut rules. The UI cannot close during active writes. Completion is shown only after a successful engine exit. The completion page independently offers opening Cove and creating a desktop shortcut. Both are selected by default; the GUI engine runs with `/NO_DESKTOP_SHORTCUT` and creates a new shortcut only after confirmation. Existing owned shortcuts are still repaired and are not deleted when the option is unchecked. Silent setup creates its normal shortcuts unless `/NO_DESKTOP_SHORTCUT` is supplied; `/TESTMODE` and silent installs do not launch it. The mutex protects actual installation; a new app launch before the user begins setup is checked again by the engine.

WebView2 missing/initialization failures retain the native prerequisite/recovery wizard (`packaging/studio-ui.nsh`). Its colors still come from `artifacts/installer-theme.nsh`, generated from the shared tokens. No new browser runtime is silently downloaded. The legacy fallback loads private OFL font subsets and does not install fonts into Windows.

`scripts/verify_installer_ui.py` opens the actual packaged setup frontend in Chinese/English, verifies shared typography, button color/radius, native frame and all five wizard pages, then exits without installing. `/TESTMODE` plus `COVE_INSTALL_UI_PAGE=language|location|license|installing|finish` writes JSON only to a fresh absolute `COVE_INSTALL_UI_REPORT`; normal setup ignores these test variables. Browser UI tests additionally check minimum size, focus/close consent, disabled controls and screenshots. Visual screenshots and actual installation are separate evidence.

Silent setup accepts `/LANGUAGE=2052` or `/LANGUAGE=1033`. The interactive selector starts from the system display language; its choice is passed to the engine. The app's saved interface language remains independent. Run the disposable upgrade check once with each `--language` value. Native recovery/uninstall strings remain in `packaging/languages.nsh`.

Missing WebView2 is detected from Microsoft's documented per-user and per-machine registry keys before application files are written. Interactive users can open Microsoft's download/terms page; silent installation fails with code 1603. `/TESTMODE /SIMULATE_MISSING_WEBVIEW2` can force this rejection without changing registry keys or bypassing a real prerequisite check.

Every build collects exact third-party license texts and wheel SBOMs, checks frozen Python dependency coverage, and embeds the corresponding core source archive. MCP is the only bundled service. See [third-party notices](../THIRD-PARTY-NOTICES.md). The source and binary hashes must be exported and verified together.

The frozen frontend includes `dist/build-manifest.json` with its version and asset hashes. The payload check verifies every asset and matches the frontend version to the embedded source archive. This detects stale or incomplete frontend packaging.

Starting with 0.12.10, `runtime-manifest.json` also records the full versioned payload and the stable launcher's hash. Activation verifies those bytes before atomically publishing `.cove-current`. The desktop and Start menu links target `<installation>/Cove.exe`, a small launcher that resolves the published version. Existing links in those folders and the current user's pinned-taskbar folder are repaired only when their target is a Cove executable within this installation. User arguments and unrelated shortcuts are preserved; tests use isolated shortcut folders. Direct launches of versioned desktops from 0.12.10 onward also forward to the active version.

## When an update looks unchanged

Setup requires every Cove desktop belonging to the selected installation to exit before any version is installed, including identical reinstalls. After consent, it sends a normal close request to visible main windows and waits. Active-work confirmation remains in Cove; cancelling it leaves setup blocked. No process is killed. A silent install returns 1618 while a desktop remains open. Other installations are unaffected.

Check the version in Settings and use the updated shortcut or the fixed `<installation>/Cove.exe` entry. Saved appearance presets and custom colors survive upgrades; select **Cove** in Settings to use its current palette. Do not reset user preferences to force a visual change.

MCP adapters are separate processes. Installing a new host preserves existing sessions, so the host and adapters can run different versions. The connection page reports live session versions and warns about earlier versions. Reload Cove MCP in the client when ready to update that session. Adapters older than 0.12.4 must reload before the new disconnect controls work. Rewriting the configuration alone does not replace an already running adapter.

## Documentation captures

Build the frontend, run `.venv\Scripts\python.exe scripts/serve_e2e.py --showcase --port 18329`, then `node scripts/capture_product.mjs`. This captures the MCP-only catalog in Chinese/English and light/dark modes with disposable data. It does not connect hardware or inspect personal client configuration. Screenshots are UI evidence, not verification of device workflows.

Preview binaries are unsigned. Installer tests do not establish SmartScreen reputation or a malware verdict. Do not claim that a remote CI run happened until its actual result is available.

## Native move, size and Snap (0.12.12)

The native host enables [WebView2 non-client regions](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2settings.isnonclientregionsupportenabled); the shared title bar declares `app-region: drag`, excluding buttons and editable controls. When unavailable, the bridge posts the system move/size command on the WinForms UI thread with the current pointer location, never after mouse release. Resize hit bands occupy the visible client edge. This avoids reconstructing native gestures from pointer-capture/mousemove events.

The host queries [IsWindowArranged](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindowarranged) on size, location and end-of-move transitions. Snapped/maximized windows remove the composited inset, CSS corner and shadow, and turn off Win11 DWM rounding. Restored windows recover the normal corner. State/layout tests are not proof of real pointer dragging or Windows Snap; record actual input separately.
