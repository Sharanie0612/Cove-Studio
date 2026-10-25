import sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'sdk'))
from toolbench.packages import build_package, package_filename, write_bytes_atomic
from toolbench.distribution import portable_archive
package = build_package(root)
output = root / 'exports'
output.mkdir(exist_ok=True)
name = package_filename(package['manifest'])
write_bytes_atomic(output / name, package['content'])
print(output / name)
if any(tool['readOnly'] for tool in package['manifest'].get('ai', {}).get('tools', [])):
    portable = portable_archive(root, root / 'sdk/toolbench')
    destination = output / (package['manifest']['id'] + '-' + package['manifest']['version'] + '-dsh.zip')
    write_bytes_atomic(destination, portable)
    print(destination)
