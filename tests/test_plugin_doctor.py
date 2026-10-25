import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv
import zipfile

from toolbench.developer import DeveloperApi
from toolbench.plugin_framework.doctor import diagnose_plugin
from toolbench.plugin_framework.interpreter import select_interpreter


ROOT = Path(__file__).resolve().parent.parent


class PluginDoctorTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='doctor-test-', dir=ROOT / 'artifacts')
        self.root = Path(self.temporary.name)
        self.project = self.root / 'plugin'
        shutil.copytree(ROOT / 'docs/templates/starter', self.project)
        self.executed = self.root / 'plugin-was-executed'
        (self.project / 'plugin.py').write_text(
            f'from pathlib import Path\nPath({str(self.executed)!r}).write_text("executed")\n'
            'raise RuntimeError("diagnostics must not import this plugin")\n', encoding='utf-8')

    def tearDown(self):
        self.assertFalse(self.executed.exists(), 'diagnostics executed plugin.py')
        self.temporary.cleanup()

    def make_environment(self):
        environment = self.project / '.venv'
        venv.EnvBuilder(with_pip=False).create(environment)
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        packages = environment / ('Lib/site-packages' if os.name == 'nt'
                                  else f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages')
        packages.mkdir(parents=True, exist_ok=True)
        return python, packages

    def test_probe_reports_real_environment_metadata_without_imports_or_startup_hooks(self):
        python, packages = self.make_environment()
        distribution = packages / 'doctor_fixture-1.2.3.dist-info'
        distribution.mkdir()
        (distribution / 'METADATA').write_text('Metadata-Version: 2.1\nName: doctor-fixture\nVersion: 1.2.3\n', encoding='utf-8')
        imported = self.root / 'dependency-was-imported'
        (packages / 'doctor_fixture.py').write_text(f'from pathlib import Path\nPath({str(imported)!r}).touch()\n')
        startup = self.root / 'startup-hook-was-executed'
        hook = f'import pathlib; pathlib.Path({str(startup)!r}).touch()\n'
        (packages / 'doctor-hook.pth').write_text(hook, encoding='utf-8')
        (packages / 'sitecustomize.py').write_text(hook, encoding='utf-8')
        (self.project / 'json.py').write_text(hook, encoding='utf-8')
        (self.project / 'requirements.txt').write_text('doctor-fixture>=99\n', encoding='utf-8')
        report = diagnose_plugin(self.project)
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['interpreter']['source'], 'project-venv')
        self.assertEqual(Path(report['interpreter']['executable']), python)
        self.assertEqual(report['interpreter']['version'], sys.version.split()[0])
        self.assertIn(report['interpreter']['architectureBits'], (32, 64))
        self.assertTrue(report['interpreter']['venv'])
        self.assertEqual(report['requirements'][0]['installedVersion'], '1.2.3')
        self.assertEqual(report['requirements'][0]['availability'], 'installed')
        self.assertEqual(report['requirements'][0]['constraints'], 'unverified')
        self.assertFalse(imported.exists())
        self.assertFalse(startup.exists())
        self.assertFalse(report['pluginCodeExecuted'])
        self.assertFalse(report['dependenciesInstalled'])

    def test_missing_dependency_is_an_error_but_conditional_missing_is_unverified(self):
        self.make_environment()
        requirements = self.project / 'requirements.txt'
        requirements.write_text('cove-doctor-fixture-not-installed>=1\n', encoding='utf-8')
        missing = diagnose_plugin(self.project)
        self.assertFalse(missing['ok'])
        self.assertEqual(missing['requirements'][0]['availability'], 'missing')
        self.assertIn('cove-doctor-fixture-not-installed', missing['errors'][0])
        requirements.write_text('cove-doctor-fixture-not-installed; python_version < "0"\n-r more.txt\n', encoding='utf-8')
        conditional = diagnose_plugin(self.project)
        self.assertTrue(conditional['ok'], conditional)
        self.assertEqual(conditional['status'], 'partial')
        self.assertTrue(all(item['constraints'] == 'unverified' for item in conditional['requirements']))
        self.assertIsNone(conditional['requirements'][1]['name'])

    def test_invalid_interpreter_and_timeout_are_actionable_without_plugin_execution(self):
        report = diagnose_plugin(self.project, str(self.root / 'missing-python.exe'))
        self.assertFalse(report['ok'])
        self.assertEqual(report['interpreter']['source'], 'configured')
        self.assertEqual(report['interpreter']['probeStatus'], 'error')
        with patch('toolbench.plugin_framework.doctor.subprocess.run',
                   side_effect=subprocess.TimeoutExpired('python', 0.01)):
            report = diagnose_plugin(self.project, timeout=0.01)
        self.assertFalse(report['ok'])
        self.assertIn('timed out', report['errors'][0])

    def test_explicit_relative_interpreter_is_resolved_from_the_callers_directory(self):
        relative = os.path.relpath(sys.executable, Path.cwd())
        report = diagnose_plugin(self.project, relative)
        self.assertTrue(report['ok'], report)
        self.assertEqual(Path(report['interpreter']['selectedPath']), Path(sys.executable).resolve())
        self.assertEqual(report['interpreter']['source'], 'configured')

    def test_invalid_manifest_is_reported_before_any_environment_probe(self):
        (self.project / 'manifest.json').write_text('{"sdkVersion":999}', encoding='utf-8')
        with patch('toolbench.plugin_framework.doctor.subprocess.run') as probe:
            report = diagnose_plugin(self.project)
        self.assertFalse(report['ok'])
        probe.assert_not_called()

    def test_older_python_is_not_reported_as_a_supported_sdk_environment(self):
        response = subprocess.CompletedProcess([], 0, json.dumps({
            'version': '3.10.1', 'versionInfo': [3, 10, 1], 'versions': {},
            'architectureBits': 64, 'implementation': 'cpython'}), '')
        with patch('toolbench.plugin_framework.doctor.subprocess.run', return_value=response):
            report = diagnose_plugin(self.project)
        self.assertFalse(report['ok'])
        self.assertIn('Python 3.11', report['errors'][0])
        self.assertEqual(report['interpreter']['minimumVersion'], '3.11')

    def test_selection_matches_configured_project_frozen_and_host_precedence(self):
        project_python = self.project / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        project_python.parent.mkdir(parents=True)
        project_python.write_bytes(b'diagnostic selection only')
        configured = self.root / 'selected-python.exe'
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(self.root / 'Cove.exe')):
            self.assertEqual(select_interpreter(self.project, configured).source, 'configured')
            self.assertEqual(select_interpreter(self.project).executable, project_python)
            project_python.unlink()
            selected = select_interpreter(self.project)
            self.assertTrue(selected.frozen_worker)
            self.assertEqual(selected.executable.name, 'Cove-worker.exe')
            with patch('toolbench.plugin_framework.doctor.subprocess.run') as probe:
                report = diagnose_plugin(self.project)
            probe.assert_not_called()
            self.assertFalse(report['ok'])
            self.assertIn('not a Python CLI', report['errors'][0])
        with patch.object(sys, 'executable', str(self.root / 'pythonw.exe')):
            selected = select_interpreter(self.project)
            self.assertEqual(selected.source, 'host-python')
            self.assertEqual(selected.executable.name, 'python.exe' if os.name == 'nt' else 'pythonw.exe')

    def test_default_checker_remains_metadata_only_and_doctor_is_explicit(self):
        project_python = self.project / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        project_python.parent.mkdir(parents=True)
        project_python.write_bytes(b'not an executable')
        command = [sys.executable, '-I', '-S', '-B', str(ROOT / 'scripts/check_plugin.py'), str(self.project)]
        metadata = subprocess.run(command, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(metadata.returncode, 0, metadata.stdout + metadata.stderr)
        self.assertFalse(json.loads(metadata.stdout)['pluginCodeExecuted'])
        doctor = subprocess.run([*command, '--doctor'], capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(doctor.returncode, 1, doctor.stdout + doctor.stderr)
        self.assertEqual(json.loads(doctor.stdout)['interpreter']['probeStatus'], 'error')

    def test_exported_starter_doctor_runs_without_site_packages(self):
        with zipfile.ZipFile(io.BytesIO(DeveloperApi()._starter_bytes())) as archive:
            archive.extractall(self.root / 'download')
        project = self.root / 'download/cove-plugin-starter'
        (project / 'plugin.py').write_bytes((self.project / 'plugin.py').read_bytes())
        result = subprocess.run([sys.executable, '-I', '-S', '-B', str(project / 'doctor.py')],
                                cwd=project, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['plugin']['id'], 'community.hello')
        self.assertTrue(report['compatibility']['supported'])
        self.assertEqual(report['interpreter']['probeStatus'], 'ok')
        self.assertFalse(report['pluginCodeExecuted'])


if __name__ == '__main__':
    unittest.main()
