from pathlib import Path
import hashlib, json, sys
root = Path(__file__).resolve().parent
manifest = root / "plugin/manifest.json" if (root / "plugin/manifest.json").exists() else root / "manifest.json"
identity = json.loads(manifest.read_text(encoding="utf-8-sig"))["id"]
namespace = hashlib.sha256(identity.encode()).hexdigest()[:10]
config = [{"insert": [{"id": "cove-portable-" + namespace, "name": "@deepseek-ai/dsh-mcp-client", "config": {
    "serverName": "cove_" + namespace, "transport": "stdio", "command": sys.executable,
    "args": [str(root / "serve.py")], "toolCallTimeoutMs": 240000}}]}]
path = root / "cove.dsh.yml"
path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
print(path)
print('dsh web --patch "' + str(path) + '"')
