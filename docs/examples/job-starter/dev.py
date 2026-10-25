"""Run with the downloaded SDK, or directly inside the Cove source checkout."""
import json
from pathlib import Path
import sys
import threading

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'sdk' if (root / 'sdk').is_dir() else root.parents[2]))
from toolbench.sdk import Context
from toolbench.manifest import validate_manifest
from plugin import Tool

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
validate_manifest(json.loads((root / 'manifest.json').read_text(encoding='utf-8')))
finished = threading.Event()


def publish(event):
    if event['event'] == 'activity' and not event['data']['active']:
        finished.set()


tool = Tool(Context(publish, str(root / '.local')))
try:
    tool.run(batches=3)
    if not finished.wait(5):
        raise RuntimeError('Example did not finish')
    print(json.dumps(tool.snapshot(), ensure_ascii=False, indent=2))
finally:
    tool.close()
