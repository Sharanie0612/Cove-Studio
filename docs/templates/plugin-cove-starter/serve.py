from pathlib import Path
import sys
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'sdk'))
from toolbench.plugin_mcp import main
sys.argv = [sys.argv[0], '--plugin', str(root), *sys.argv[1:]]
main()
