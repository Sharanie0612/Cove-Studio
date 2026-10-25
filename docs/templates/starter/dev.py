import json, sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'sdk'))
from toolbench.sdk import Context
from toolbench.manifest import validate_manifest
from plugin import Tool
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
validate_manifest(manifest)
command = sys.argv[1] if len(sys.argv) > 1 else manifest['ui']['actions'][0]['command']
if command not in manifest['commands']: raise SystemExit('Command is not declared')
arguments = sys.argv[2:]
payload = json.loads(arguments[0]) if arguments and arguments[0].startswith('{') else dict(item.split('=', 1) for item in arguments)
context = Context(lambda event: print(json.dumps(event), file=sys.stderr), str(root / '.local'))
tool = Tool(context)
try:
    print(json.dumps(getattr(tool, command)(**payload), ensure_ascii=False, indent=2))
finally:
    tool.close()
