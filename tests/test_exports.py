import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from toolbench.bridge import API_METHODS, DesktopBridge
from toolbench.host import Host, ROOT
from toolbench.packages import build_package, inspect_archive, package_filename
from unittest.mock import patch

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        self.host = Host(plugins_dir=ROOT / "plugins/projects", data_dir=self.root / 'data')
        self.source = self.root / 'project'
        shutil.copytree(ROOT / 'docs/templates/starter', self.source)

    def tearDown(self):
        self.host.close(); self.temp.cleanup()

    def test_export_roundtrip_keeps_resources_and_excludes_local_files(self):
        for name in ('assets/sample.csv', 'assets/icon.svg', 'assets/archive.zip', 'vendor/library/manifest.json', 'vendor/library/__init__.py'):
            target = self.source / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('{}')
        for name in ('.venv/Scripts/python.exe', '.env.local', 'profiles.json', 'test.key', '__pycache__/cache.pyc'):
            target = self.source / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('secret')
        preview = self.host._prepare_export(self.source)
        self.assertFalse(self.host.workers)
        self.assertIn('assets/archive.zip', preview['files'])
        self.assertIn('vendor/library/manifest.json', preview['files'])
        self.assertNotIn('.env.local', preview['files'])
        self.assertNotIn('profiles.json', preview['files'])
        self.assertIn('test.key', preview['excluded'])
        output = self.root / 'exported'
        saved = self.host._save_export(preview['ticket'], output)
        package = Path(saved['path'])
        self.assertEqual(package.suffix, '.cove-plugin')
        imported = self.host._inspect_package(package)
        installed = self.host.install_plugin(imported['ticket'])
        self.assertTrue(installed['ok'], installed)
        result = self.host.invoke('community.hello', 'greet', {'name': 'export'})
        self.assertTrue(result['ok'], result)

    def test_preview_is_immutable_and_failed_save_can_retry(self):
        preview = self.host._prepare_export(self.source)
        (self.source / 'plugin.py').write_text('raise RuntimeError("changed")')
        with self.assertRaises(OSError):
            self.host._save_export(preview['ticket'], self.root / 'missing/target.cove-plugin')
        saved = self.host._save_export(preview['ticket'], self.root / 'retry.cove-plugin')
        with zipfile.ZipFile(saved['path']) as archive:
            self.assertNotIn(b'changed', archive.read('plugin.py'))
        with self.assertRaises(ValueError):
            self.host._save_export(preview['ticket'], self.root / 'again.cove-plugin')

    def test_ignore_rules_and_required_files(self):
        (self.source / 'debug.log').write_text('debug')
        (self.source / '.coveignore').write_text('*.log\n')
        self.assertNotIn('debug.log', build_package(self.source)['files'])
        (self.source / '.coveignore').write_text('plugin.py\n')
        with self.assertRaisesRegex(ValueError, 'plugin.py'):
            build_package(self.source)

    def test_filename_cannot_escape_output_directory(self):
        manifest = {'id': 'community.hello', 'version': '../../bad/version'}
        self.assertNotIn('/', package_filename(manifest))
        self.assertNotIn('\\', package_filename(manifest))

    def test_export_ticket_expires(self):
        preview = self.host._prepare_export(self.source)
        self.host._export_tickets[preview['ticket']]['time'] = time.monotonic() - 601
        with self.assertRaisesRegex(ValueError, '过期'):
            self.host._save_export(preview['ticket'], self.root / 'late.cove-plugin')

    def test_cancel_save_keeps_preview_available(self):
        preview = self.host._prepare_export(self.source)
        class Window:
            def create_file_dialog(self, *args, **kwargs): return None
        self.host._window = Window()
        result = self.host.save_plugin_export(preview['ticket'])
        self.assertTrue(result['ok'])
        self.assertIsNone(result['result'])
        self.assertIn(preview['ticket'], self.host._export_tickets)

    def test_dialog_uses_own_window(self):
        package = self.root / 'source.cove-plugin'
        package.write_bytes(build_package(self.source)['content'])
        class Window:
            def create_file_dialog(self, *args, **kwargs): return [str(package)]
        self.host._window = Window()
        with patch('webview.windows', []):
            result = self.host.inspect_plugin_package()
        self.assertTrue(result['ok'], result)

    def test_starter_runs_and_packages_without_site_packages(self):
        content = self.host._starter_bytes()
        with zipfile.ZipFile(io.BytesIO(content)) as archive: archive.extractall(self.root / 'starter')
        project = self.root / 'starter/cove-plugin-starter'
        dev = subprocess.run([sys.executable, '-S', str(project / 'dev.py')], cwd=project, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(dev.returncode, 0, dev.stderr)
        self.assertIn('message', json.loads(dev.stdout))
        packaged = subprocess.run([sys.executable, '-S', str(project / 'package.py')], cwd=project, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(packaged.returncode, 0, packaged.stderr)
        exported = next((project / 'exports').glob('*.cove-plugin'))
        inspected = inspect_archive(exported.read_bytes())
        self.assertIn('plugin.py', inspected['files'])
        self.assertFalse(any(name.startswith('sdk/') for name in inspected['files']))
        self.assertNotIn('dev.py', inspected['files'])

    def test_bridge_exposes_methods_without_host_object_graph(self):
        bridge = DesktopBridge(self.host)
        public = [name for name in dir(bridge) if not name.startswith('_')]
        self.assertEqual(set(public), set(API_METHODS))
        self.assertTrue(all(callable(getattr(bridge, name)) for name in public))
        self.assertNotIn('data_dir', public)
        self.assertNotIn('close', public)

    def test_downloaded_result_example_is_independent_and_excluded_from_hello_package(self):
        with zipfile.ZipFile(io.BytesIO(self.host._starter_bytes())) as archive:
            archive.extractall(self.root / 'download')
        starter = self.root / 'download/cove-plugin-starter'
        project = starter / 'examples/result-starter'
        command = [sys.executable, '-S', str(project / 'dev.py'), 'analyze', 'text=one two one']
        reply = subprocess.run(command, cwd=self.root, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertEqual(json.loads(reply.stdout)['unique'], 2)
        package = build_package(starter)
        self.assertFalse(any(path.startswith('examples/') for path in package['files']))
        self.assertIn('plugin_framework/result_contract.py',
                      [path.relative_to(project / 'sdk/toolbench').as_posix()
                       for path in (project / 'sdk/toolbench').rglob('*.py')])
