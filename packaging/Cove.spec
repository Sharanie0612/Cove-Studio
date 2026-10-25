from pathlib import Path
import sys
import ssl

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from toolbench.plugin_framework.bundle import sdk_files

def resources(folder, destination):
    return [(str(path), str(Path(destination) / path.relative_to(folder).parent))
            for path in folder.rglob('*') if path.is_file()
            and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.tmp')]

datas = [(str(root / 'assets/cove.ico'), 'assets'),
         (str(root / 'LICENSE'), '.'), (str(root / 'THIRD-PARTY-NOTICES.md'), '.')]
# The bundled build interpreter can load trust-policy data next to ssl.py when
# creating any SSLContext. Preserve that policy unchanged in the frozen layout.
ssl_policy = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
if ssl_policy.is_file():
    datas.append((str(ssl_policy), '.'))
for folder, destination in [('dist', 'dist'), ('docs', 'docs'), ('schemas', 'schemas'),
                            ('plugins/projects/mcp', 'builtin-plugins/mcp')]:
    datas += resources(root / folder, destination)
# The built-in MCP service ship in a dedicated data directory; imported plugins stay external.
for source in sdk_files(root / 'toolbench'):
    relative = source.relative_to(root / 'toolbench')
    datas.append((str(source), str(Path('sdk-runtime/toolbench') / relative.parent)))
analysis = Analysis([str(root / 'desktop_entry.py')], pathex=[str(root)], datas=datas,
    hiddenimports=['psutil', 'tomlkit', 'yaml', 'json5', 'webview.platforms.winforms', 'webview.platforms.edgechromium',
                   # Standard-library capabilities used by independently imported Python plugins.
                   'logging.handlers', 'decimal', 'contextvars', 'concurrent.futures',
                   'urllib.request', 'http.cookiejar', 'html.parser', 'importlib.resources'],
    # The host uses an authenticated HTTP loopback, not webview's optional TLS server.
    excludes=['cryptography', 'bcrypt', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter', 'matplotlib', 'pytest', 'IPython'],
    noarchive=False)
pyz = PYZ(analysis.pure)
gui = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='Cove',
    console=False, debug=False, icon=str(root / 'assets/cove.ico'), uac_admin=False)
worker = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='Cove-worker',
    console=True, debug=False, icon=str(root / 'assets/cove.ico'), uac_admin=False)
collection = COLLECT(gui, worker, analysis.binaries, analysis.datas, strip=False, upx=False, name='Cove')
