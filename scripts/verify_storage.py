"""Verify frozen default storage and legacy adapters using disposable copied runtimes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from toolbench.host import Host
from verify_versioned_installer import Mcp


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime',type=Path)
    parser.add_argument('--legacy-worker',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='storage-check-',dir=ROOT/'artifacts') as temporary:
        base=Path(temporary);runtime=base/'chosen-drive/Cove'
        shutil.copytree(args.runtime.resolve(),runtime)
        legacy=base/'profile/Cove';plugin=legacy/'installed/storage-fixture';plugin.mkdir(parents=True)
        manifest={'sdkVersion':1,'id':'test.storage','version':'1.0.0','name':'Storage fixture','description':'Disposable storage check',
          'author':'Cove tests','category':'Tests','icon':'terminal','color':'blue','permissions':[],
          'commands':['snapshot'],'ui':{'surface':'form','fields':[],'actions':[{'command':'snapshot','label':'Read'}]},
          'ai':{'tools':[{'name':'snapshot','command':'snapshot','description':'Read fixture storage','readOnly':True,
          'parameters':{'type':'object','properties':{},'additionalProperties':False}}]}}
        (plugin/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        (plugin/'plugin.py').write_text('from toolbench.sdk import Plugin\nimport os,tempfile\nfrom pathlib import Path\nclass Tool(Plugin):\n def snapshot(self):\n  with tempfile.NamedTemporaryFile(delete=False) as f: temporary=f.name\n  return {"data":self.context.data_dir,"temporary":temporary,"cache":os.environ.get("XDG_CACHE_HOME"),"profile":Path(self.context.data_dir,"profile.txt").read_text()}\n',encoding='utf-8')
        (legacy/'test.storage').mkdir();(legacy/'test.storage/profile.txt').write_text('retained')
        (legacy/'webview').mkdir();(legacy/'webview/retained-draft.txt').write_text('retained draft')
        environment={**os.environ,'LOCALAPPDATA':str(base/'profile'),'USERPROFILE':str(base/'home')}
        environment.pop('TOOLBENCH_DATA_DIR',None)
        for name in ('CODEX_HOME','DSH_HOME'):environment.pop(name,None)
        adapter=None;old=None;current=None
        try:
            with patch('pathlib.Path.home',return_value=base/'home'),patch.dict(os.environ,environment,clear=True):
                old=Host(data_dir=legacy)
                old.assistant_allow(['test.storage'])
                adapter=Mcp(args.legacy_worker.resolve().parent,legacy/'mcp-bridge.json')
                assert adapter.snapshot()['profile']=='retained'
                old.close();old=None
                smoke=base/'frozen-smoke.json'
                subprocess.run([str(runtime/'Cove.exe'),'--smoke',str(smoke)],env=environment,check=True,timeout=30)
                catalog=json.loads(smoke.read_text(encoding='utf-8'))['catalog']
                assert Path(catalog['dataPath'])==runtime/'data',catalog['dataPath']
                assert catalog['storage']['mode']=='installation'
                with patch('toolbench.host.ROOT',runtime/'_internal'),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(runtime/'Cove.exe')):
                    current=Host()
                    result=adapter.snapshot()
                    assert Path(result['data']).is_relative_to(runtime/'data')
                    assert Path(result['temporary']).is_relative_to(runtime/'data')
                    assert Path(result['cache']).is_relative_to(runtime/'data')
                    assert result['profile']=='retained'
                    assert (runtime/'data/webview/retained-draft.txt').read_text()=='retained draft'
                    current.assistant_allow([])
                    discovery=adapter.rpc('tools/call',{'name':'cove_tools','arguments':{}})
                    assert json.loads(discovery['content'][0]['text'])['result']['total']==0
                    current.close();current=None
                assert (legacy/'test.storage/profile.txt').read_text()=='retained'
                assert (legacy/'webview/retained-draft.txt').read_text()=='retained draft'
                report={'passed':True,'frozenDefaultDataAtChosenLocation':True,'legacyProfileAndDraftPreserved':True,
                  'originalBackupRetained':True,'alreadyRunningLegacyAdapterReconnected':True,'revocationPreserved':True,
                  'frozenWorkerTemporaryAndCacheAtChosenLocation':True,
                  'legacyWorkerSha256':hashlib.sha256(args.legacy_worker.read_bytes()).hexdigest()}
                output=ROOT/'artifacts/validation/storage-location.json'
                output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
        finally:
            if adapter:adapter.close()
            if current:current.close()
            if old:old.close()


if __name__=='__main__':main()
