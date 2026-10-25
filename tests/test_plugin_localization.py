import copy
import json
from pathlib import Path
import tempfile
import unittest

from toolbench.host import Host, ROOT
from toolbench.manifest import validate_manifest


class PluginLocalizationTests(unittest.TestCase):
    def test_live_locale_read_and_translations_keep_worker_and_data(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder:
            root = Path(folder)
            plugin = root/'plugins/hello'; plugin.mkdir(parents=True)
            manifest = json.loads((ROOT/'docs/templates/starter/manifest.json').read_text(encoding='utf-8'))
            (plugin/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            (plugin/'plugin.py').write_text((ROOT/'docs/templates/starter/plugin.py').read_text(encoding='utf-8'), encoding='utf-8')
            original = (plugin/'manifest.json').read_bytes()
            host = Host(plugins_dir=root/'plugins', data_dir=root/'data')
            try:
                host.set_locale('zh-CN')
                a=host.invoke('community.hello','greet',{'name':'Keep / 原文'})
                worker=host.workers['community.hello']; pid=worker.process.pid
                self.assertEqual(a['result']['message'],'你好，Keep / 原文！')
                host.set_locale('en-US')
                b=host.invoke('community.hello','greet',{'name':'Keep / 原文'})
                self.assertEqual(b['result']['message'],'Hello, Keep / 原文!')
                self.assertEqual(host.workers['community.hello'].process.pid,pid)
                host.set_locale('zh-CN')
                self.assertEqual(host.invoke('community.hello','greet',{'name':'Z'})['result']['message'],'你好，Z！')
                self.assertEqual((plugin/'manifest.json').read_bytes(),original)
                self.assertEqual(host._host_tool_call('community.hello','host.locale',{}),'zh-CN')
                with self.assertRaises(ValueError): host._host_tool_call('unknown','host.locale',{})
                with self.assertRaises(ValueError): host._host_tool_call('community.hello','tools.list',{})
            finally: host.close()

    def test_catalog_validation_rejects_invalid_messages_without_execution(self):
        manifest=json.loads((ROOT/'docs/templates/starter/manifest.json').read_text(encoding='utf-8'))
        validate_manifest(manifest)
        for value in ({'defaultLocale':'fr','messages':{}},
                      {'defaultLocale':'zh-CN','messages':{'en-US':{'{name}':'{other}'}}},
                      {'defaultLocale':'zh-CN','messages':{'en-US':{'Name':3}}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_manifest({**manifest,'localization':value})
