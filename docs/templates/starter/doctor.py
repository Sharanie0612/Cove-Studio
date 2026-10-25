"""Inspect this project's metadata and Python environment without importing plugin.py."""
import argparse
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'sdk'))
from toolbench.plugin_framework.doctor import diagnose_plugin

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--python', dest='interpreter', help='Explicit Python executable; otherwise use .venv or the current Python')
arguments = parser.parse_args()
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
report = diagnose_plugin(root, arguments.interpreter)
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report['ok'] else 1)
