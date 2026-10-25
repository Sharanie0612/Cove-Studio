# Third-party notices — Cove Studio

The MIT license covers original core and SDK code. Third-party licenses and trademark rights remain with their owners.

The installer and portable application include `licenses/` with original notices, wheel SBOMs, component versions and hashes. `scripts/collect_notices.py` checks the frozen module inventory against those notices. The matching core source archive is included under `sources/`.

Runtime dependencies include CPython (PSF), pywebview (BSD-3-Clause), pythonnet/clr-loader/Bottle (MIT), proxy_tools (upstream BSD-2-Clause notice retained), cffi (MIT-0), pycparser (BSD-3-Clause), psutil (BSD-3-Clause), jsonschema and related components (MIT), tomlkit/PyYAML (MIT), json5 (Apache-2.0), and the upstream notices of packaging/setuptools and their bundled dependencies. Exact versions and license texts are included in the generated inventory.

React, React DOM, Scheduler, xterm.js and addon-fit retain MIT notices. Lucide retains ISC and upstream icon notices. PyInstaller retains GPL plus its bootloader distribution exception. NSIS retains its zlib/libpng notice. The Microsoft WebView2 SDK/loader retains its redistribution notice. The separately detected WebView2 Runtime remains a Microsoft product; users install it under Microsoft's terms.

Inter and Noto Sans SC subsets retain OFL-1.1 and upstream copyright. Provenance and modifications are in `assets/fonts/inventory.json`. No Apple font files are redistributed. Provider marks identify supported MCP clients; provenance is in `assets/providers/sources.json`. No provider affiliation is claimed.
