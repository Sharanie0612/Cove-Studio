import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from toolbench.windows_shortcuts import repair_shortcuts, create_desktop_shortcut


@unittest.skipUnless(os.name == 'nt', 'Windows Shell Link metadata')
class ShortcutTests(unittest.TestCase):
    def test_opted_in_shortcut_is_idempotent_and_never_overwrites_other_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=root/'app';app.mkdir();links=root/'links'
            create_desktop_shortcut(app,links)
            original=(links/'Cove.lnk').read_bytes()
            create_desktop_shortcut(app,links)
            self.assertEqual((links/'Cove.lnk').read_bytes(),original)
            with self.assertRaises(OSError):create_desktop_shortcut(root/'other',links)
            self.assertEqual((links/'Cove.lnk').read_bytes(),original)
    def test_only_owned_targets_are_repaired_and_arguments_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); app = root/'app'; links = root/'links'
            app.mkdir(); links.mkdir()
            script = r'''
$shell=New-Object -ComObject WScript.Shell
$root=$env:COVE_LINK_TEST
foreach($name in @('Owned','Other')){
 $link=$shell.CreateShortcut((Join-Path $root "links\$name.lnk"))
 if($name -eq 'Owned'){$link.TargetPath=Join-Path $root 'app\versions\0.12.9\Cove.exe'}else{$link.TargetPath=Join-Path $root 'other\Cove.exe'}
 $link.Arguments='--port 18549';$link.Save()
}
'''
            command = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
            def run(source):
                result = subprocess.run([command,'-NoProfile','-NonInteractive','-EncodedCommand',
                    base64.b64encode(source.encode('utf-16-le')).decode()],
                    env={**os.environ,'COVE_LINK_TEST':str(root)},capture_output=True,text=True,encoding='utf-8',timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                return result.stdout
            run(script)
            changed = repair_shortcuts(app,[links])
            self.assertEqual([Path(item).resolve() for item in changed],[(links/'Owned.lnk').resolve()])
            actual=json.loads(run(r'''
$shell=New-Object -ComObject WScript.Shell
$result=@()
foreach($name in @('Owned','Other')){
 $link=$shell.CreateShortcut((Join-Path $env:COVE_LINK_TEST "links\$name.lnk"))
 $result+=@{target=$link.TargetPath;arguments=$link.Arguments}
}
ConvertTo-Json -InputObject @($result) -Compress
'''))
            self.assertEqual(Path(actual[0]['target']).resolve(),(app/'Cove.exe').resolve())
            self.assertEqual(actual[0]['arguments'],'--port 18549')
            self.assertEqual(Path(actual[1]['target']).resolve(),(root/'other/Cove.exe').resolve())
