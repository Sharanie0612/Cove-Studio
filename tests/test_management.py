import json
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from toolbench.host import Host, ROOT


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        self.host = Host(plugins_dir=ROOT / "plugins/projects", data_dir=self.root / 'data')
        self.manifest = json.loads((ROOT / 'docs/templates/starter/manifest.json').read_text(encoding='utf-8'))
        self.plugin = self.manifest['id']

    def tearDown(self):
        self.host.close()
        self.temp.cleanup()

    def package(self, extra=None):
        path = self.root / 'test.cove-plugin'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('hello/manifest.json', json.dumps(self.manifest))
            archive.write(ROOT / 'docs/templates/starter/plugin.py', 'hello/plugin.py')
            for name, content in (extra or {}).items():
                archive.writestr(name, content)
        return path

    def install(self):
        preview = self.host._inspect_package(self.package())
        self.assertNotIn(self.plugin, self.host.plugins)  # Inspection must not install or execute.
        self.assertFalse(self.host.workers)
        result = self.host.install_plugin(preview['ticket'])
        self.assertTrue(result['ok'], result)

    def test_install_update_and_remove_preserves_data(self):
        self.install()
        result = self.host.invoke(self.plugin, 'greet', {'name': 'Cove'})
        self.assertTrue(result['ok'], result)
        data = self.host.data_dir / self.plugin / 'keep.txt'
        data.parent.mkdir(exist_ok=True)
        data.write_text('keep')
        self.manifest['version'] = '0.2.0'
        preview = self.host._inspect_package(self.package())
        self.assertEqual(preview['previousVersion'], '0.1.0')
        self.assertTrue(self.host.install_plugin(preview['ticket'])['ok'])
        self.assertNotIn(self.plugin, self.host.workers)
        self.assertEqual(self.host.plugins[self.plugin][1]['version'], '0.2.0')
        self.assertTrue(self.host.plugin_action(self.plugin, 'remove')['ok'])
        self.assertEqual(data.read_text(), 'keep')
        self.assertNotIn(self.plugin, self.host.plugins)

    def test_ticket_uses_inspected_bytes_and_is_single_use(self):
        path = self.package()
        preview = self.host._inspect_package(path)
        path.write_bytes(b'changed after preview')
        self.assertTrue(self.host.install_plugin(preview['ticket'])['ok'])
        self.assertFalse(self.host.install_plugin(preview['ticket'])['ok'])

    def test_disable_persists_and_blocks_invocation(self):
        self.install()
        self.host.plugin_action(self.plugin, 'start')
        process = self.host.workers[self.plugin].process
        self.assertTrue(self.host.plugin_action(self.plugin, 'disable')['ok'])
        self.assertIsNotNone(process.poll())
        self.assertFalse(self.host.invoke(self.plugin, 'greet', {})['ok'])
        self.host.close()
        self.host = Host(plugins_dir=ROOT / "plugins/projects", data_dir=self.root / 'data')
        item = next(item for item in self.host.catalog()['tools'] if item['id'] == self.plugin)
        self.assertFalse(item['enabled'])
        self.assertTrue(self.host.plugin_action(self.plugin, 'enable')['ok'])
        self.assertTrue(self.host.invoke(self.plugin, 'greet', {})['ok'])


    def test_release_skips_connected_active_and_pending(self):
        self.install()
        self.host.plugin_action(self.plugin, 'start')
        for attribute in ('_connected', '_active_tasks'):
            getattr(self.host, attribute)[self.plugin] = True
            self.assertEqual(self.host.plugin_action('', 'stop_idle')['result']['stopped'], 0)
            getattr(self.host, attribute)[self.plugin] = False
        self.host.workers[self.plugin].pending['test'] = {}
        self.assertEqual(self.host.plugin_action('', 'stop_idle')['result']['stopped'], 0)
        self.host.workers[self.plugin].pending.clear()
        self.assertEqual(self.host.plugin_action('', 'stop_idle')['result']['stopped'], 1)
        self.assertFalse(next(item for item in self.host.catalog()['tools'] if item['id'] == self.plugin)['runtime']['running'])

    def test_rejects_unsafe_package_paths(self):
        for name in ('../escape.py', '/absolute.py', 'hello/NUL.txt', 'hello/.git/config', 'hello/unsafe:stream', 'hello/space. '):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.host._inspect_package(self.package({name: 'bad'}))
        self.assertFalse((self.root / 'escape.py').exists())

    def test_rejects_links_and_duplicate_names(self):
        path = self.package({'hello/PLUGIN.py': 'duplicate'})
        with self.assertRaises(ValueError):
            self.host._inspect_package(path)
        with self.assertRaises(ValueError):
            self.host._inspect_package(self.package({'hello/./plugin.py': 'duplicate-normalized-path'}))
        path = self.package()
        with zipfile.ZipFile(path, 'a') as archive:
            info = zipfile.ZipInfo('hello/link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, '../outside')
        with self.assertRaises(ValueError):
            self.host._inspect_package(path)

    def test_builtin_cannot_be_replaced_or_removed(self):
        self.manifest['id'] = 'dev.cove.mcp'
        with self.assertRaises(ValueError):
            self.host._inspect_package(self.package())
        self.assertFalse(self.host.plugin_action('dev.cove.mcp', 'remove')['ok'])
        self.assertIn('dev.cove.mcp', self.host.plugins)


    def test_drop_folder_rescan_discovers_projects_and_preserves_data_on_removal(self):
        import shutil
        drop = self.root / 'plugins'
        self.host._plugin_drop_root = drop
        shutil.copytree(ROOT / 'docs/templates/starter', drop / 'hello')
        self.assertTrue(self.host.rescan_plugins()['ok'])
        self.assertIn(self.plugin, self.host.plugins)
        self.assertTrue(self.host.invoke(self.plugin, 'greet', {'name': 'Cove'})['ok'])
        saved = self.host.data_dir / self.plugin / 'keep.txt'
        saved.write_text('retain')
        self.assertTrue(self.host.plugin_action(self.plugin, 'remove')['ok'])
        self.assertEqual(saved.read_text(), 'retain')
        self.assertFalse((drop / 'hello').exists())


    def test_release_cannot_interrupt_command_before_it_registers_pending(self):
        self.install()
        self.host.plugin_action(self.plugin, 'start')
        worker = self.host.workers[self.plugin]
        entered, release = threading.Event(), threading.Event()
        actual = worker.invoke
        responses = []
        def delayed(*args):
            entered.set()
            release.wait(3)
            return actual(*args)
        with patch.object(worker, 'invoke', delayed):
            request = threading.Thread(target=lambda: responses.append(self.host.invoke(self.plugin, 'greet', {})))
            request.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(worker.pending)
                self.assertEqual(self.host.plugin_action('', 'stop_idle')['result']['stopped'], 0)
            finally:
                release.set()
                request.join(4)
        self.assertTrue(responses[0]['ok'], responses)
