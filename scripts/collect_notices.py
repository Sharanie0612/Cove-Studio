"""Collect original runtime notices and pinned corresponding sources, offline."""
import argparse
import ast
import hashlib
from importlib.metadata import distribution, packages_distributions
import json
from pathlib import Path
import shutil
import sys
import tarfile

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ['pywebview', 'psutil', 'jsonschema', 'tomlkit', 'PyYAML', 'json5',
           'setuptools', 'packaging', 'idna']


def python_packages():
    pending, found = list(RUNTIME), {}
    while pending:
        item = distribution(pending.pop())
        name = item.metadata['Name']
        if name in found:
            continue
        found[name] = item
        for value in item.requires or []:
            requirement = Requirement(value)
            if not requirement.marker or requirement.marker.evaluate({'extra': ''}):
                pending.append(requirement.name)
    return found


def collect(output: Path, analysis=None):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    def copy(source, relative):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return str(relative).replace('\\', '/')

    packages = python_packages()
    # The bootloader exception and installer are documented even though they are build tools.
    for name, item in sorted({**packages, 'pyinstaller': distribution('pyinstaller')}.items()):
        notices = []
        for entry in item.files or []:
            path = Path(str(entry))
            if path.suffix in {'.py', '.pyc'} or not any(word in str(path).lower() for word in ('license', 'copying', 'notice', 'sboms/')):
                continue
            if path.is_absolute() or '..' in path.parts:
                raise ValueError(f'Unexpected license path: {entry}')
            if item.locate_file(entry).is_file():
                notices.append(copy(item.locate_file(entry), Path('python') / name / path))
        if not notices and name != 'proxy_tools':
            raise ValueError(f'No original license text for {name}')
        license_text = item.metadata.get('License-Expression') or item.metadata.get('License') or 'see original license'
        records.append({'kind': 'python', 'name': name, 'version': item.version,
                        'license': license_text.splitlines()[0],
                        'files': notices, 'projectUrls': item.metadata.get_all('Project-URL') or [item.metadata.get('Home-page', '')]})

    pending = list(json.loads((ROOT / 'package.json').read_text())['dependencies'])
    found = set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        folder = ROOT / 'node_modules' / name
        info = json.loads((folder / 'package.json').read_text(encoding='utf-8'))
        found.add(name)
        notices = [copy(path, Path('frontend') / name / path.name) for path in folder.iterdir()
                   if path.is_file() and path.name.lower().startswith(('license', 'copying', 'notice'))]
        if not notices:
            raise ValueError(f'No original license text for frontend dependency {name}')
        records.append({'kind': 'frontend', 'name': name, 'version': info['version'],
                        'license': info.get('license', 'see original license'), 'files': notices,
                        'repository': info.get('repository')})
        pending.extend(info.get('dependencies', {}))

    copy(Path(sys.base_prefix) / 'LICENSE.txt', Path('python') / 'CPython-LICENSE.txt')
    font_inventory = json.loads((ROOT / 'assets/fonts/inventory.json').read_text(encoding='utf-8'))
    for entry in font_inventory['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or len(relative.parts) != 1:
            raise ValueError(f'Unexpected font asset path: {relative}')
        if hashlib.sha256((ROOT / 'assets/fonts' / relative).read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Font asset differs from its provenance inventory: {relative}')
    for font in font_inventory['fonts']:
        notice = copy(ROOT / 'assets/fonts' / font['licenseFile'], Path('fonts') / font['licenseFile'])
        records.append({'kind': 'font', 'name': font['name'], 'version': font['version'],
                        'license': font['license'], 'files': [notice], 'sourceUrl': font['sourceUrl'],
                        'sourceSha256': font['sourceSha256'], 'changes': font['changes']})
    copy(ROOT / 'assets/fonts/inventory.json', Path('fonts/inventory.json'))
    for path in (ROOT / 'packaging/third-party-extra').rglob('*'):
        if path.is_file():
            copy(path, Path('additional') / path.relative_to(ROOT / 'packaging/third-party-extra'))
    for metadata in (ROOT / 'packaging/third-party-sources').glob('*.json'):
        source = json.loads(metadata.read_text(encoding='utf-8'))
        archive = metadata.with_name(source['file'])
        if source['version'] != distribution(source['name']).version:
            raise ValueError(f'Pinned source version differs from installed {source["name"]}')
        if hashlib.sha256(archive.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError(f'Source archive hash differs: {archive.name}')
        copy(archive, Path('sources') / archive.name)
        copy(metadata, Path('sources') / metadata.name)

    if analysis:
        mapping = packages_distributions()
        actual = set()
        for section in ast.literal_eval(analysis.read_text(encoding='utf-8')):
            if not isinstance(section, list):
                continue
            for entry in section:
                if isinstance(entry, tuple) and len(entry) == 3 and isinstance(entry[1], str) and 'site-packages' in entry[1]:
                    actual.update(mapping.get(entry[0].split('.')[0], []))
        if actual - set(packages):
            raise ValueError(f'Frozen dependencies missing notices: {sorted(actual - set(packages))}')

    files = [{'path': path.relative_to(output).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(output.rglob('*')) if path.is_file() and path != output / 'inventory.json']
    native = json.loads((ROOT / 'packaging/third-party-extra/native/inventory.json').read_text(encoding='utf-8'))
    if native['errors']:
        raise ValueError('Native component license collection is incomplete')
    inventory = {'pythonVersion': sys.version.split()[0], 'components': records, 'nativeComponents': native['components'], 'files': files,
                 'sourcePolicy': 'Core source and rebuild instructions accompany the application.'}
    (output / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'components': len(records), 'noticeAndSourceFiles': len(files), 'analysisChecked': bool(analysis)}))
    return inventory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--analysis', type=Path)
    args = parser.parse_args()
    collect(args.output.resolve(), args.analysis)
