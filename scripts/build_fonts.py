"""Regenerate locally bundled OFL fonts; never downloads fonts at application runtime.

Optional build tools: pip install fonttools==4.61.1 brotli==1.2.0
Normal product builds use the checked-in outputs and do not need these tools.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '45e3d5269e4a17d823f6d84470bc084dc5ae46f6'
SOURCES = [
    ('inter', 'Inter.ttf', 'Inter%5Bopsz,wght%5D.ttf',
     '29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031'),
    ('notosanssc', 'NotoSansSC.ttf', 'NotoSansSC%5Bwght%5D.ttf',
     'a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da'),
]


def rename(font, family, style='Regular'):
    names = {1: family, 2: style, 3: f'{family}-{style}-CoveSubset',
             4: f'{family} {style}', 6: f'{family.replace(" ", "")}-{style}',
             16: family, 17: style, 25: family.replace(' ', '')}
    for name_id, value in names.items():
        font['name'].removeNames(nameID=name_id)
        font['name'].setName(value, name_id, 3, 1, 0x409)
        font['name'].setName(value, name_id, 1, 0, 0)
    # Original copyright, authorship and OFL records are retained.
    if 'fvar' in font:
        font['fvar'].instances = []


def cjk_characters():
    chars = set(range(0x20, 0x100)) | set(range(0x2000, 0x2070)) | set(range(0x3000, 0x3040))
    for lead in range(0xA1, 0xF8):
        for trail in range(0xA1, 0xFF):
            try:
                chars.add(ord(bytes([lead, trail]).decode('gb2312')))
            except UnicodeDecodeError:
                pass
    for folder in ('src', 'packaging'):
        for path in sorted((ROOT / folder).rglob('*')):
            if path.suffix in {'.ts', '.tsx', '.nsh', '.nsi'}:
                chars.update(ord(c) for c in path.read_text(encoding='utf-8') if ord(c) >= 0x100)
    return chars


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'artifacts/font-input')
    args = parser.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True)
    output = ROOT / 'assets/fonts'
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for name, filename, remote, expected in SOURCES:
        url = f'https://raw.githubusercontent.com/google/fonts/{COMMIT}/ofl/{name}/{remote}'
        source = args.source_dir / filename
        if not source.is_file():
            source.write_bytes(urlopen(url, timeout=60).read())
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Font source checksum mismatch: {filename}')
        license_url = f'https://raw.githubusercontent.com/google/fonts/{COMMIT}/ofl/{name}/OFL.txt'
        license_path = output / f'{name}-OFL.txt'
        if not license_path.is_file():
            license_path.write_bytes(urlopen(license_url, timeout=30).read())
        family = 'Cove Sans Latin' if name == 'inter' else 'Cove Sans CJK'
        font = TTFont(source, recalcTimestamp=False)
        version = font['name'].getDebugName(5)
        limits = {'wght': (400, 700)}
        if name == 'inter':
            limits['opsz'] = (14, 32)
        if name == 'notosanssc':
            options = subset.Options()
            options.name_IDs = ['*']
            options.name_legacy = True
            options.recalc_timestamp = False
            subsetter = subset.Subsetter(options=options)
            subsetter.populate(unicodes=cjk_characters())
            subsetter.subset(font)
        instantiateVariableFont(font, limits, inplace=True)
        rename(font, family)
        for weight in ((600,) if name == 'inter' else (400, 600)):
            static = instantiateVariableFont(font, {'wght': weight, **({'opsz': 24} if name == 'inter' else {})}, inplace=False)
            static.flavor = None
            rename(static, family, 'SemiBold' if weight == 600 else 'Regular')
            static.save(output / f'{name}-{weight}.ttf')
        font.flavor = 'woff2'
        web = output / f'{name}-ui.woff2'
        font.save(web)
        records.append({'name': name, 'family': family, 'version': version, 'license': 'OFL-1.1',
                        'sourceUrl': url, 'sourceSha256': expected, 'licenseFile': license_path.name,
                        'licenseUrl': license_url, 'unicodeCount': len(font.getBestCmap()),
                        'changes': 'Subset/weight range, renamed family; original outlines and attribution retained.'})
    files = [{'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(output.iterdir()) if p.suffix in {'.woff2', '.ttf', '.txt'}]
    (output / 'inventory.json').write_text(json.dumps({'fonts': records, 'files': files}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'fonts': len(records), 'files': len(files)}))


if __name__ == '__main__':
    main()
