"""Check the frozen core and independently imported disposable SDK fixtures."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from toolbench.host import Host
from fixtures_runtime import TERMINAL, write_terminal_fixture
def main():
    parser=argparse.ArgumentParser();parser.add_argument('installation',type=Path)
    installation=parser.parse_args().installation.resolve()
    with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as temporary:
        data=Path(temporary)
        with patch('toolbench.host.ROOT',installation/'_internal'),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(installation/'Cove.exe')):
            host=Host(data_dir=data/'data')
            try:
                assert set(host.plugins)=={'dev.cove.mcp'}
                host._plugin_drop_root=data/'fixtures'
                write_terminal_fixture(host._plugin_drop_root/'terminal');host.rescan_plugins()
                challenge=host.invoke(TERMINAL,'connect',{'host':'fixture','username':'test'})
                assert challenge['code']=='CONFIRM_TEST_SESSION',challenge
                assert host.invoke(TERMINAL,'connect',{'trust_fingerprint':'fixture'})['ok']
                assert host.invoke(TERMINAL,'snapshot')['result']['connected']
                assert host.invoke(TERMINAL,'disconnect')['ok']
            finally:host.close()
    print(json.dumps({'mcpOnlyBuiltin':True,'frozenImportedFixture':True,'connectionLifecycle':True}))
if __name__=='__main__':main()
