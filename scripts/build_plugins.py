"""Package the only built-in service and the core delivery bundle."""
from pathlib import Path
import json
import sys
import zipfile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from toolbench.packages import build_package, package_filename, write_bytes_atomic
from audit_core import audit
def main():
    audit(ROOT)
    output=ROOT/'plugins/packages';output.mkdir(parents=True,exist_ok=True)
    package=build_package(ROOT/'plugins/projects/mcp')
    destination=output/package_filename(package['manifest'])
    write_bytes_atomic(destination,package['content'])
    version=json.loads((ROOT/'package.json').read_text())['version']
    installer=ROOT/f'artifacts/Cove-{version}-setup.exe'
    if installer.exists():
        with zipfile.ZipFile(ROOT/f'artifacts/Cove-{version}-bundle.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for path in [installer,ROOT/f'artifacts/Cove-{version}-source.zip',ROOT/'LICENSE',ROOT/'THIRD-PARTY-NOTICES.md']:
                archive.write(path,path.name)
            archive.write(destination,'plugins/'+destination.name)
    print(destination)
if __name__=='__main__':main()
