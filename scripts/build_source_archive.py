"""Archive only product source inputs; never personal state, Git internals or outputs."""
import json
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('.github', 'assets', 'docs', 'packaging', 'schemas', 'scripts', 'src', 'tests', 'toolbench',
           'plugins/projects/mcp')
FILES = ('AGENTS.md', '.gitignore', '.gitattributes', '.prettierrc.json', 'run.bat', 'LICENSE', 'THIRD-PARTY-NOTICES.md', 'README.md', 'README.zh-CN.md',
         'CONTRIBUTING.md', 'SECURITY.md', 'package.json', 'package-lock.json', 'pyproject.toml',
         'requirements.txt', 'requirements-dev.txt', 'requirements-build.lock', 'index.html',
         'vite.config.ts', 'tsconfig.json', 'playwright.config.ts', 'desktop_entry.py', 'setup.html')


def build_source_archive():
    from audit_core import audit
    audit(ROOT)
    version = json.loads((ROOT / 'package.json').read_text())['version']
    output = ROOT / f'artifacts/Cove-{version}-source.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates = [ROOT / name for name in FILES]
    for folder in FOLDERS:
        candidates.extend(path for path in (ROOT / folder).rglob('*') if path.is_file())
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        manifest = []
        for path in sorted(set(candidates)):
            relative = path.relative_to(ROOT)
            if not path.exists():
                continue
            if any(part in {'__pycache__', '.git', '.venv', 'node_modules', '.local'} for part in relative.parts):
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                raise ValueError(f'Source input escapes checkout: {relative}')
            if path.suffix.lower() in {'.pyc', '.log', '.tmp', '.cove-plugin'} or path.name.startswith('.env'):
                continue
            archive.write(path, 'cove-studio/' + relative.as_posix())
            manifest.append({'path': relative.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        archive.writestr('source-manifest.json', json.dumps({'version': version, 'files': manifest}, indent=2))
    from audit_core import audit_archive
    audit_archive(output)
    return output


if __name__ == '__main__':
    print(build_source_archive())
