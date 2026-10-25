"""Verify license/source delivery from the actual frozen application folder."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from toolbench.maintenance import verify_runtime_payload


def verify(installation):
    frontend = installation / '_internal/dist'
    frontend_manifest = json.loads((frontend / 'build-manifest.json').read_text(encoding='utf-8'))
    runtime_files = verify_runtime_payload(installation, frontend_manifest['version'])
    actual_files = {path.relative_to(frontend).as_posix() for path in frontend.rglob('*')
                    if path.is_file() and path.name != 'build-manifest.json'}
    assert not any('InstrumentSurface' in name for name in actual_files), 'Domain UI must not ship in the core'
    assert any('WebSurface' in name for name in actual_files), 'Missing generic plugin UI container'
    assert actual_files == {item['path'] for item in frontend_manifest['files']}, 'Frontend file inventory differs'
    for item in frontend_manifest['files']:
        path = PurePosixPath(item['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert hashlib.sha256((frontend / path).read_bytes()).hexdigest() == item['sha256'], f'Stale frontend asset: {path}'
    license_text = (installation / 'LICENSE').read_text(encoding='utf-8')
    assert license_text.startswith('MIT License') and 'Cove contributors' in license_text
    assert (installation / 'THIRD-PARTY-NOTICES.md').is_file()
    inventory = json.loads((installation / 'licenses/inventory.json').read_text(encoding='utf-8'))
    for item in inventory['files']:
        assert hashlib.sha256((installation / 'licenses' / item['path']).read_bytes()).hexdigest() == item['sha256']
    assert inventory['nativeComponents']
    assert {item['name'] for item in inventory['components'] if item['kind'] == 'font'} == {'inter', 'notosanssc'}
    fonts = json.loads((installation / 'licenses/fonts/inventory.json').read_text(encoding='utf-8'))
    for font in fonts['files']:
        if font['path'].endswith('.woff2'):
            stem = Path(font['path']).stem
            bundled = list((installation / '_internal/dist/assets').glob(stem + '-*.woff2'))
            assert len(bundled) == 1, f'Missing or ambiguous bundled font: {stem}'
            assert hashlib.sha256(bundled[0].read_bytes()).hexdigest() == font['sha256']
    sources = list((installation / 'sources').glob('Cove-*-source.zip'))
    assert len(sources) == 1
    with zipfile.ZipFile(sources[0]) as archive:
        names = set(archive.namelist())
        required = {'LICENSE', 'THIRD-PARTY-NOTICES.md', 'package-lock.json', 'requirements-build.lock',
                    'packaging/installer.nsi', 'packaging/studio-ui.nsh', 'scripts/collect_notices.py',
                    'assets/fonts/inventory.json', 'scripts/build_fonts.py',
                    'docs/plugin-sdk.en.md', 'docs/examples/result-starter/plugin.py',
                    'toolbench/plugin_framework/transactions.py'}
        assert all('cove-studio/' + name in names for name in required)
        manifest = json.loads(archive.read('source-manifest.json'))
        package_version = json.loads(archive.read('cove-studio/package.json'))['version']
        assert frontend_manifest['version'] == manifest['version'] == package_version, 'Frontend and source versions differ'
        for item in manifest['files']:
            path = PurePosixPath(item['path'])
            assert not path.is_absolute() and '..' not in path.parts
            assert not any(part in {'.git', '.local', '.venv', 'node_modules', '__pycache__'} or part.startswith('.env') for part in path.parts)
            assert hashlib.sha256(archive.read('cove-studio/' + item['path'])).hexdigest() == item['sha256']
        core_license = archive.read('cove-studio/LICENSE')
        assert core_license == (installation / 'LICENSE').read_bytes()
    return {'frontendVersion': frontend_manifest['version'], 'frontendAssetHashesVerified': len(actual_files),
            'runtimeFileHashesVerified': runtime_files,
            'mitIncluded': True, 'bundledFontHashesVerified': True, 'noticeFilesVerified': len(inventory['files']),
            'components': len(inventory['components']), 'nativeComponents': len(inventory['nativeComponents']),
            'correspondingSourceFilesVerified': len(manifest['files']),
            'sourceArchiveSha256': hashlib.sha256(sources[0].read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation', type=Path)
    result = verify(parser.parse_args().installation.resolve())
    print(json.dumps(result))
