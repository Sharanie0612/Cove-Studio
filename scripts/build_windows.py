"""Build a shared-runtime desktop folder and a per-user Windows installer."""
import json
import hashlib
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--distribution', type=Path, help='Build into a new folder when an earlier verification runtime is still open')
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / 'scripts/audit_core.py')], cwd=ROOT, check=True)
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    sys.path.insert(0, str(ROOT))
    from toolbench import __version__
    metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    if version != __version__ or version != metadata['project']['version']:
        raise SystemExit('Host, frontend and Python package versions must agree before packaging.')
    distribution = (args.distribution or ROOT / f'artifacts/desktop-{version}').resolve()
    subprocess.run([shutil.which('npm') or 'npm.cmd', 'run', 'build'], cwd=ROOT, check=True)
    frontend = ROOT / 'dist'
    frontend_manifest = {'version': version, 'files': [
        {'path': path.relative_to(frontend).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(frontend.rglob('*')) if path.is_file() and path.name != 'build-manifest.json']}
    (frontend / 'build-manifest.json').write_text(json.dumps(frontend_manifest, indent=2), encoding='utf-8')
    legal = ROOT / 'artifacts/legal'
    subprocess.run([sys.executable, str(ROOT / 'scripts/collect_notices.py'), '--output', str(legal)], cwd=ROOT, check=True)
    from build_source_archive import build_source_archive
    sources = build_source_archive()
    subprocess.run([sys.executable, '-m', 'PyInstaller', str(ROOT / 'packaging/Cove.spec'),
                    '--distpath', str(distribution), '--workpath', str(ROOT / 'artifacts/build'),
                    '--noconfirm'], cwd=ROOT, check=True)
    plugin_folder = distribution / 'Cove/plugins'
    plugin_folder.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'docs/plugin-folder.txt', plugin_folder / 'README.txt')
    subprocess.run([sys.executable, str(ROOT / 'scripts/collect_notices.py'), '--output', str(legal),
                    '--analysis', str(ROOT / 'artifacts/build/Cove/Analysis-00.toc')], cwd=ROOT, check=True)
    for document in ('LICENSE', 'THIRD-PARTY-NOTICES.md'):
        shutil.copyfile(ROOT / document, distribution / 'Cove' / document)
    shutil.copytree(legal, distribution / 'Cove/licenses', dirs_exist_ok=True)
    (distribution / 'Cove/sources').mkdir(exist_ok=True)
    shutil.copyfile(sources, distribution / 'Cove/sources' / sources.name)
    runtime = distribution / 'Cove'
    inventory = {'version': version, 'files': [
        {'path': path.relative_to(runtime).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(runtime.rglob('*')) if path.is_file() and path.name != 'runtime-manifest.json']}
    (runtime / 'runtime-manifest.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    makensis = shutil.which('makensis')
    if not makensis:
        candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'tauri/NSIS/makensis.exe'
        if candidate.is_file():
            makensis = str(candidate)
    if not makensis:
        raise SystemExit('Desktop folder built. Install NSIS and run this script again to create the installer.')
    palette = json.loads(subprocess.check_output([
        shutil.which('node') or 'node.exe', '--experimental-strip-types', '-e',
        "import {normalizeAppearance,themeTokens} from './src/core/appearance.ts'; console.log(JSON.stringify(themeTokens(normalizeAppearance({scheme:'cove'}),'light')));"
    ], cwd=ROOT, text=True))
    theme_names = {'BACKGROUND': 'bg', 'SURFACE': 'surface', 'CHROME': 'sidebar',
                   'TEXT': 'text', 'MUTED': 'text-2', 'BORDER': 'border', 'ACCENT': 'primary'}
    (ROOT / 'artifacts/installer-theme.nsh').write_text('\n'.join(
        f'!define COVE_THEME_{name} "{palette[key].lstrip("#").upper()}"'
        for name, key in theme_names.items()) + '\n' + '\n'.join(
        f'!define COVE_THEME_{name}_BGR 0x{palette[key][5:7]}{palette[key][3:5]}{palette[key][1:3]}'
        for name, key in theme_names.items()) + '\n', encoding='utf-8')
    launcher = ROOT / f'artifacts/launcher-{version}/Cove.exe'
    launcher.parent.mkdir(exist_ok=True)
    # Keep compiler scratch writable for the launching process, including a
    # Low-integrity development workspace. This changes only the child env.
    with tempfile.TemporaryDirectory(prefix='nsis-compile-', dir=ROOT / 'artifacts') as scratch:
        assert Path(scratch).resolve().is_relative_to((ROOT / 'artifacts').resolve())
        environment = {**os.environ, 'TEMP': scratch, 'TMP': scratch}
        subprocess.run([makensis, '/INPUTCHARSET', 'UTF8', '/V2', f'/DCOVE_VERSION={version}',
                        f'/DCOVE_LAUNCHER={launcher}', 'launcher.nsi'],
                       cwd=ROOT / 'packaging', env=environment, check=True)
        inventory['launcherSha256'] = hashlib.sha256(launcher.read_bytes()).hexdigest()
        (runtime / 'runtime-manifest.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
        subprocess.run([makensis, '/INPUTCHARSET', 'UTF8', '/V2', f'/DCOVE_VERSION={version}',
                        f'/DCOVE_DISTDIR={distribution / "Cove"}', f'/DCOVE_LAUNCHER={launcher}', 'installer.nsi'],
                       cwd=ROOT / 'packaging', env=environment, check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/build_plugins.py')], cwd=ROOT, check=True)
    shutil.make_archive(str(ROOT / f'artifacts/Cove-{version}-windows'), 'zip', distribution, 'Cove')
    print(ROOT / f'artifacts/Cove-{version}-setup.exe')


if __name__ == '__main__':
    main()
