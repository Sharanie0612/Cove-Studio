"""Run execution/lifecycle regressions against the shipped worker executable."""
import argparse
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_runtime_lifecycle import RuntimeLifecycleTests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation', type=Path)
    installation = parser.parse_args().installation.resolve()
    assert (installation / 'Cove-worker.exe').is_file()
    with patch('toolbench.host.ROOT', installation / '_internal'), \
         patch.object(sys, 'frozen', True, create=True), \
         patch.object(sys, 'executable', str(installation / 'Cove.exe')):
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeLifecycleTests))
    report = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'worker': str(installation / 'Cove-worker.exe')}
    (ROOT / 'artifacts/validation').mkdir(parents=True, exist_ok=True)
    (ROOT / 'artifacts/validation/frozen-runtime.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
