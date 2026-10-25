"""Package a Cove plugin using only Python's standard library."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from toolbench.packages import build_package, package_filename, write_bytes_atomic

def main():
    parser = argparse.ArgumentParser(description='打包插件源码和资源；不会运行插件或安装依赖')
    parser.add_argument('folder', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts')
    args = parser.parse_args()
    package = build_package(args.folder)
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / package_filename(package['manifest'])
    write_bytes_atomic(target, package['content'])
    print(f"{target}\n{package['fileCount']} files, {len(package['content'])} bytes")
    if package['excluded']: print('Excluded: ' + ', '.join(package['excluded']))

if __name__ == '__main__': main()
