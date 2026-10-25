"""Validate a source project or .cove-plugin archive without executing it."""
import argparse
import json
from pathlib import Path
import sys
from zipfile import BadZipFile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from toolbench.contracts import compatibility_report
from toolbench.packages import build_package, inspect_archive


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--doctor', action='store_true', help='Probe the selected Python for read-only environment diagnostics')
    parser.add_argument('--python', dest='interpreter', help='Explicit Python executable for --doctor (same precedence as a configured runtime)')
    args = parser.parse_args()
    if args.interpreter and not args.doctor:
        parser.error('--python requires --doctor; default validation does not start an interpreter')
    if args.doctor:
        from toolbench.plugin_framework.doctor import diagnose_plugin
        if not args.path.is_dir():
            print(json.dumps({'ok': False, 'pluginCodeExecuted': False,
                              'error': '--doctor requires a source directory; omit it to inspect an archive'}))
            return 1
        report = diagnose_plugin(args.path, args.interpreter)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['ok'] else 1
    try:
        result = build_package(args.path) if args.path.is_dir() else inspect_archive(args.path.read_bytes())
        manifest = result['manifest']
        compatibility = compatibility_report(manifest)
        print(json.dumps({'id': manifest['id'], 'version': manifest['version'],
                          'sdkVersion': manifest['sdkVersion'], 'compatibility': compatibility,
                          'pluginCodeExecuted': False}, ensure_ascii=False, indent=2))
        return 0 if compatibility['supported'] else 1
    except (ValueError, OSError, KeyError, BadZipFile) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
