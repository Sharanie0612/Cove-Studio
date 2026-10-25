"""Portable plugin archives share the exact Cove plugin source and tool contract."""
from __future__ import annotations
import io
from pathlib import Path
import zipfile

from toolbench.packages import build_package
from toolbench.plugin_framework.policy import POLICY


SERVE = '''from pathlib import Path
import sys
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "runtime"))
from toolbench.plugin_mcp import main
if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--plugin", str(root / "plugin"), *sys.argv[1:]]
    main()
'''

SETUP = '''from pathlib import Path
import hashlib, json, sys
root = Path(__file__).resolve().parent
manifest = root / "plugin/manifest.json" if (root / "plugin/manifest.json").exists() else root / "manifest.json"
identity = json.loads(manifest.read_text(encoding="utf-8-sig"))["id"]
namespace = hashlib.sha256(identity.encode()).hexdigest()[:10]
config = [{"insert": [{"id": "cove-portable-" + namespace, "name": "@deepseek-ai/dsh-mcp-client", "config": {
    "serverName": "cove_" + namespace, "transport": "stdio", "command": sys.executable,
    "args": [str(root / "serve.py")], "toolCallTimeoutMs": __COVE_CLIENT_TIMEOUT__}}]}]
path = root / "cove.dsh.yml"
path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
print(path)
print('dsh web --patch "' + str(path) + '"')
'''
SETUP = SETUP.replace('__COVE_CLIENT_TIMEOUT__', str(int(POLICY.client * 1000)))


def portable_archive(folder, runtime_root=None):
    package = build_package(Path(folder))
    if not any(tool['readOnly'] for tool in package['manifest'].get('ai', {}).get('tools', [])):
        raise ValueError('该插件没有可独立导出的只读 MCP 工具')
    if runtime_root is not None:
        runtime = Path(runtime_root)
        license_path = runtime.parent / 'LICENSE'
    else:
        from toolbench.host import ROOT
        runtime = ROOT / 'sdk-runtime/toolbench' if (ROOT / 'sdk-runtime/toolbench').exists() else ROOT / 'toolbench'
        license_path = ROOT / 'LICENSE'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        with zipfile.ZipFile(io.BytesIO(package['content'])) as source:
            for name in source.namelist():
                if not name.endswith('/'):
                    archive.writestr('plugin/' + name, source.read(name))
        from toolbench.plugin_framework.bundle import sdk_files
        for source in sdk_files(runtime):
            archive.writestr('runtime/toolbench/' + source.relative_to(runtime).as_posix(), source.read_bytes())
        archive.writestr('runtime/LICENSE', license_path.read_bytes())
        archive.writestr('serve.py', SERVE)
        archive.writestr('setup_dsh.py', SETUP)
        requirements = (Path(folder) / 'requirements.txt').read_text(encoding='utf-8') if (Path(folder) / 'requirements.txt').exists() else ''
        archive.writestr('requirements.txt', requirements.rstrip() + '\njsonschema>=4.23,<5\n')
        archive.writestr('README.md', '# Cove portable plugin\n\n1. Install Python 3.11+.\n2. Run `python -m pip install -r requirements.txt`.\n3. Run `python setup_dsh.py`; use the printed command to launch DSH with the generated overlay.\n4. Ask DSH to list and call this plugin tool.\n\nOnly declared read-only tools are exposed. To use an active Cove tool session and approved writes, connect DSH to Cove from the desktop MCP page.\nBusiness logic is in plugin/plugin.py and is identical to the Cove package. No model API key is handled by this archive.\n')
    return buffer.getvalue()

