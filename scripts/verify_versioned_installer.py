"""Upgrade with a live disposable MCP adapter and independent in-memory fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import base64
import shutil
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from toolbench.host import Host
from fixtures_runtime import TERMINAL, write_terminal_fixture

class Mcp:
    def __init__(self,runtime,connection):
        self.process=subprocess.Popen([str(runtime/'Cove-worker.exe'),'--mcp','--compact','--connection',str(connection)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        self.messages=queue.Queue();self.sequence=0
        def read():
            for line in self.process.stdout:self.messages.put(json.loads(line))
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        self.rpc('initialize',{'protocolVersion':'2025-11-25'})
    def rpc(self,method,params=None):
        self.sequence+=1
        self.process.stdin.write(json.dumps({'jsonrpc':'2.0','id':self.sequence,'method':method,'params':params or {}})+'\n');self.process.stdin.flush()
        while True:
            result=self.messages.get(timeout=15)
            if result.get('id')==self.sequence:
                assert 'error' not in result,result
                return result['result']
    def snapshot(self):
        discovery=self.rpc('tools/call',{'name':'cove_tools','arguments':{}})
        assert not discovery.get('isError'),discovery
        tools=json.loads(discovery['content'][0]['text'])['result']['tools']
        tool=next(t for t in tools if t['readOnly'])
        result=self.rpc('tools/call',{'name':'cove_read','arguments':{'tool':tool['name'],'arguments':{}}})
        assert not result.get('isError'),result
        return json.loads(result['content'][0]['text'])['result']
    def close(self):
        self.process.stdin.close();self.process.wait(timeout=8);self.reader.join(timeout=2)
        self.process.stdout.close();self.process.stderr.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--candidate',type=Path)
    parser.add_argument('--language', choices=('1033', '2052'), default='1033')
    parser.add_argument('--desktop-check', action='store_true', help='Exercise real disposable old/new desktop shutdown gates')
    args=parser.parse_args()
    version=json.loads((ROOT/'package.json').read_text())['version']
    original=ROOT/f'artifacts/Cove-{version}-setup.exe'
    candidate=(args.candidate or original).resolve()
    assert hashlib.sha256(candidate.read_bytes()).digest()==hashlib.sha256(original.read_bytes()).digest()
    base=Path(tempfile.mkdtemp(prefix='cove-core-upgrade-'))
    installation=base/'app';data=base/'data';report={};host=None;adapter=None;desktop=None
    def install(package=candidate):
        result=subprocess.run([str(package),'/S','/TESTMODE',f'/LANGUAGE={args.language}',f'/D={installation}'],capture_output=True,timeout=90)
        print(f'{package.name}: {result.returncode}',flush=True)
        return result.returncode
    def make_host(runtime):
        with patch('toolbench.host.ROOT',runtime/'_internal'),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(runtime/'Cove.exe')):
            return Host(data_dir=data)
    def fixture(current):
        current._plugin_drop_root=base/'fixtures'
        write_terminal_fixture(current._plugin_drop_root/'terminal');current.rescan_plugins()
        current.assistant_allow([TERMINAL])
        assert current.invoke(TERMINAL,'connect',{'trust_fingerprint':'fixture'})['ok']
    def start_desktop(executable, suffix):
        web_port = 18542 if suffix == 'old' else 18544
        process = subprocess.Popen([str(executable), '--port', str(web_port)],
            env={**os.environ, 'TOOLBENCH_DATA_DIR':str(base/f'gui-{suffix}'),
                 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS':f'--remote-debugging-port={web_port + 1} --remote-debugging-address=127.0.0.1'})
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{web_port + 1}/json',timeout=1) as response:
                    if any(str(web_port) in page.get('url','') for page in json.load(response)):
                        return process
            except (OSError,ValueError):pass
            if process.poll() is not None:raise AssertionError(f'Desktop exited: {process.returncode}')
            time.sleep(.2)
        raise AssertionError('Disposable desktop did not load')
    def close_desktop(process):
        worker=ROOT/f'artifacts/desktop-{version}/Cove/Cove-worker.exe'
        result=subprocess.run([str(worker),'--maintenance','--install',str(installation),'--version',version,'--request-close'],
                              capture_output=True,text=True,encoding='utf-8',timeout=30)
        assert result.returncode in (0,30),result.stdout+result.stderr
        process.wait(timeout=10)
    def shortcuts(paths, seed=False):
        script=r'''
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$shell=New-Object -ComObject WScript.Shell
$paths=ConvertFrom-Json $env:COVE_TEST_LINKS
$result=@()
foreach($path in $paths){
 $link=$shell.CreateShortcut($path)
 if($env:COVE_TEST_SEED -eq '1'){
  if($path.EndsWith('Other.lnk')){$link.TargetPath=$env:COVE_TEST_OTHER}else{$link.Arguments='--port 18549'}
  $link.Save()
 }
 $result+=@{path=$path;target=$link.TargetPath;arguments=$link.Arguments}
}
ConvertTo-Json -InputObject @($result) -Compress
'''
        for path in paths:assert path.resolve().is_relative_to(base.resolve())
        result=subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()],
            env={**os.environ,'COVE_TEST_LINKS':json.dumps([str(p) for p in paths]),'COVE_TEST_SEED':'1' if seed else '0','COVE_TEST_OTHER':str(base/'another/Cove.exe')},capture_output=True,text=True,encoding='utf-8',timeout=15)
        assert result.returncode==0,result.stderr
        return json.loads(result.stdout)
    try:
        assert install(args.baseline.resolve())==0
        old=next((installation/'versions').glob('*/Cove-worker.exe')).parent
        old_hash=hashlib.sha256((old/'Cove-worker.exe').read_bytes()).hexdigest()
        host=make_host(old);fixture(host);adapter=Mcp(old,data/'mcp-bridge.json')
        assert adapter.snapshot()['connected']
        link_folder=installation/'_shortcuts/StartMenu'
        pinned=link_folder/'Pinned old Cove.lnk';unrelated=link_folder/'Other.lnk'
        for link in (pinned,unrelated):shutil.copyfile(link_folder/'Cove.lnk',link)
        shortcuts([pinned,unrelated],seed=True)
        if args.desktop_check:
            desktop=start_desktop(old/'Cove.exe','old')
            assert install()==1618
            assert not (installation/'versions'/version).exists()
            assert desktop.poll() is None
            close_desktop(desktop);desktop=None
            report['oldDesktopMustExitBeforeUpgrade']=True
        assert install()==0
        assert (installation/'.cove-current').read_text()==version
        links=shortcuts([installation/'_shortcuts/Desktop/Cove.lnk',link_folder/'Cove.lnk',pinned,unrelated])
        assert all(Path(link['target'])==installation/'Cove.exe' for link in links[:3]),links
        assert links[2]['arguments']=='--port 18549'
        assert Path(links[3]['target'])==base/'another/Cove.exe'
        report['stableEntryAndOwnedShortcutRepair']=True
        smoke=base/'stable-launch.json'
        launched=subprocess.run([str(installation/'Cove.exe'),'--smoke',str(smoke)],
            env={**os.environ,'TOOLBENCH_DATA_DIR':str(base/'launcher-data')},timeout=30)
        assert launched.returncode==0
        assert json.loads(smoke.read_text('utf-8'))['catalog']['hostVersion']==version
        report['stableEntryLaunchesCandidateVersion']=True
        assert (installation/'.cove-test-language').read_text().strip()==args.language
        assert adapter.snapshot()['connected']
        assert hashlib.sha256((old/'Cove-worker.exe').read_bytes()).hexdigest()==old_hash
        report['liveOldMcpAndFixtureSurviveUpgrade']=True
        adapter.close();adapter=None;host.close();host=None
        runtime=installation/'versions'/version
        host=make_host(runtime)
        assert set(host.plugins)=={'dev.cove.mcp'}
        fixture(host);adapter=Mcp(runtime,data/'mcp-bridge.json')
        assert adapter.snapshot()['connected']
        timestamp=(runtime/'Cove-worker.exe').stat().st_mtime_ns
        if args.desktop_check:
            desktop=start_desktop(installation/'Cove.exe','current')
            assert install()==1618
            close_desktop(desktop);desktop=None
            report['identicalReinstallAlsoRequiresDesktopExit']=True
        assert install()==0
        assert (runtime/'Cove-worker.exe').stat().st_mtime_ns==timestamp
        assert adapter.snapshot()['connected']
        report['identicalReinstallKeepsLiveRuntime']=True
        uninstall=installation/'Uninstall.exe'
        assert subprocess.run([str(uninstall),'/S',f'_?={installation}'],capture_output=True,timeout=40).returncode==1618
        assert adapter.snapshot()['connected']
        report['uninstallProtectsActiveWork']=True
        adapter.close();adapter=None;host.close();host=None
        retained=installation/'user-note.txt';retained.write_text('retain')
        assert subprocess.run([str(uninstall),'/S',f'_?={installation}'],capture_output=True,timeout=40).returncode==0
        assert retained.read_text()=='retain'
        assert not runtime.exists()
        assert not (installation/'Cove.exe').exists()
        assert not (installation/'.cove-current').exists()
        report.update(mcpOnlyBuiltin=True,uninstallPreservesUserFiles=True,version=version,installerLanguage=args.language,installerSha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
        (ROOT/'artifacts/validation').mkdir(parents=True,exist_ok=True)
        (ROOT/'artifacts/validation/installer.json').write_text(json.dumps(report,indent=2))
        (ROOT/f'artifacts/validation/installer-{args.language}.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report))
    finally:
        if desktop and desktop.poll() is None:
            close_desktop(desktop)
        if adapter:adapter.close()
        if host:host.close()
if __name__=='__main__':main()
