"""Enforce the source and bundled-service boundary before publishing."""
import json
from pathlib import Path
import re
import os
import zipfile

IGNORED={'.git','.venv','node_modules','artifacts','dist','__pycache__','.local','.pytest_cache'}
MCP='dev.cove.mcp'
def source_files(root):
    for folder, directories, files in os.walk(root):
        directories[:]=[name for name in directories if name not in IGNORED]
        for name in files:
            yield Path(folder)/name
def audit(root):
    assert not (root/'src/framework/surfaces/instrument').exists(), 'Domain UI sources belong in independent plugins'
    assert not (root/'src/framework/surfaces/InstrumentSurface.tsx').exists(), 'Domain renderer remains in core'
    for path in (root/'src').rglob('*'):
        if path.suffix in {'.ts', '.tsx', '.json', '.css'}:
            text = path.read_text(encoding='utf-8-sig')
            assert not re.search(r'InstrumentSurface|scope-control-panel|局域网示波器|连接示波器', text), f'Domain UI in {path.relative_to(root)}'
    manifests=list((root/'plugins/projects').glob('*/manifest.json'))
    assert len(manifests)==1, 'Only one built-in service is allowed'
    assert json.loads(manifests[0].read_text(encoding='utf-8'))['id']==MCP
    for path in source_files(root):
        relative=path.relative_to(root)
        if relative.parts[0]=='plugins':
            assert relative.parts[:3]==('plugins','projects','mcp') or relative.parts[1]=='packages', relative
        if path.suffix in {'.py','.ts','.tsx','.md','.json','.toml','.yml','.txt','.nsi','.spec'}:
            content=path.read_text(encoding='utf-8-sig')
            identities=set(re.findall(r'dev[.](?:cove|toolbench)[.][a-z0-9.-]+',content))
            assert identities <= {MCP}, f'Non-core identity in {relative}'
    print('Core boundary passed: MCP only; generic SDK and fixtures retained.')
    return True
def audit_archive(path):
    with zipfile.ZipFile(path) as archive:
        manifests=[]
        for name in archive.namelist():
            assert '/surfaces/instrument/' not in name and '/InstrumentSurface.' not in name, name
            if name.startswith('cove-studio/plugins/'):
                assert name.startswith('cove-studio/plugins/projects/mcp/'), name
                if name.endswith('/manifest.json'):
                    manifests.append(json.loads(archive.read(name)))
            assert not any(part in IGNORED for part in Path(name).parts), name
        assert len(manifests)==1 and manifests[0]['id']==MCP
    return True
if __name__=='__main__':audit(Path(__file__).resolve().parent.parent)
