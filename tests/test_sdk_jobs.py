"""Public job helper, actual worker lifecycle, and exported stdlib-only SDK."""
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from toolbench.host import Host, ROOT
from toolbench.manifest import validate_manifest
from toolbench.sdk import BackgroundJob, CommandError, Context


EXAMPLE = ROOT / 'docs/examples/job-starter'


class JobHelperTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.finished = threading.Event()

        def publish(event):
            self.events.append(copy.deepcopy(event))
            if event == {'event': 'activity', 'data': {'active': False}}:
                self.finished.set()

        self.job = BackgroundJob(Context(publish, 'unused'))

    def tearDown(self):
        self.job.close()

    def finish(self):
        self.assertTrue(self.finished.wait(3), 'Task did not finish')
        self.job._thread.join(timeout=1)
        return self.job.snapshot()

    def test_progress_results_and_snapshots_are_isolated_and_ordered(self):
        release = threading.Event()
        result = {'message': 'done', 'files': [{'name': 'report', 'path': 'report.txt', 'size': 12}]}

        def work(control):
            if not release.wait(3):
                raise RuntimeError('Test did not release task')
            control.update(completed=1, message='half')
            control.update(completed=2)
            return result

        started = self.job.start(work, total=2)
        started['state'] = 'changed'
        self.assertEqual(self.job.snapshot()['state'], 'running')
        release.set()
        final = self.finish()
        self.assertEqual((final['state'], final['completed'], final['total']), ('completed', 2, 2))
        result['files'][0]['size'] = 999
        final['files'].clear()
        self.assertEqual(self.job.snapshot()['files'][0]['size'], 12)
        revisions = [event['data']['result']['revision'] for event in self.events if event['event'] == 'job']
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(self.events[0], {'event': 'activity', 'data': {'active': True}})
        self.assertEqual(self.events[-1], {'event': 'activity', 'data': {'active': False}})

    def test_cancel_and_close_keep_activity_until_callback_cleanup_finishes(self):
        entered = threading.Event()
        cleaning = threading.Event()
        release_cleanup = threading.Event()

        def work(control):
            entered.set()
            try:
                control.wait(3)
            finally:
                cleaning.set()
                if not release_cleanup.wait(3):
                    raise RuntimeError('Test did not release cleanup')

        self.job.start(work)
        try:
            self.assertTrue(entered.wait(3))
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                self.job.start(lambda _: None)
            first = self.job.cancel()
            self.assertEqual(self.job.cancel()['revision'], first['revision'])
            self.assertTrue(cleaning.wait(3))
            self.job.close(timeout=0)
            self.assertEqual(self.job.snapshot()['state'], 'running')
            self.assertFalse(self.finished.is_set())
        finally:
            release_cleanup.set()
        self.assertEqual(self.finish()['state'], 'cancelled')
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            self.job.start(lambda _: None)

    def test_failure_is_terminal_and_does_not_expose_unexpected_exception_values(self):
        def fail(_):
            failure = RuntimeError('private-key-internal-value')
            failure.code = 'SOME_LIBRARY_CODE'
            raise failure
        self.job.start(fail)
        final = self.finish()
        self.assertEqual(final['state'], 'failed')
        self.assertIn('RuntimeError', final['message'])
        self.assertNotIn('private-key', json.dumps(self.events))
        self.finished.clear()

        def public_failure(_):
            raise CommandError('Choose a different output directory', 'INVALID_OUTPUT')
        self.job.start(public_failure)
        self.assertEqual(self.finish()['message'], 'Choose a different output directory')

    def test_invalid_result_cannot_forge_revision_and_partial_results_are_supported(self):
        self.job.start(lambda _: {'revision': 999})
        failed = self.finish()
        self.assertEqual(failed['state'], 'failed')
        self.assertLess(failed['revision'], 999)
        self.finished.clear()
        self.job.start(lambda _: {'state': 'partial', 'warnings': ['One item skipped']})
        final = self.finish()
        self.assertEqual(final['state'], 'partial')
        self.assertNotIn('total', final)
        self.assertGreater(final['revision'], failed['revision'])

    def test_invalid_progress_and_start_failure_release_activity(self):
        with self.assertRaises(ValueError):
            self.job.start(lambda _: None, total=-1)
        self.assertEqual(self.events, [])
        self.job.start(lambda control: control.update(completed=2), total=1)
        self.assertEqual(self.finish()['state'], 'failed')
        self.finished.clear()
        with patch('toolbench.plugin_framework.jobs.threading.Thread.start', side_effect=RuntimeError('not started')):
            with self.assertRaises(RuntimeError):
                self.job.start(lambda _: None)
        self.assertTrue(self.finished.is_set())
        self.assertEqual(self.job.snapshot()['state'], 'failed')
        self.job.close()


class JobWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        self.host = Host(plugins_dir=self.root / 'plugins', data_dir=self.root / 'data')

    def tearDown(self):
        self.host.close()
        self.temp.cleanup()

    def test_real_worker_job_guards_lifecycle_and_cancel_releases_it(self):
        folder = self.root / 'plugins/job'
        shutil.copytree(EXAMPLE, folder)
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        validate_manifest(manifest)
        # Reuse the example's real implementation with Event-based waiting so
        # the test never races a short demo task completing before cancellation.
        source = (folder / 'plugin.py').read_text(encoding='utf-8').replace('control.wait(0.02)', 'control.wait(10)')
        (folder / 'plugin.py').write_text(source, encoding='utf-8')
        self.host.rescan_plugins()
        identity = manifest['id']
        ended = threading.Event()
        original_emit = self.host._emit

        def emit(plugin_id, message):
            original_emit(plugin_id, message)
            if plugin_id == identity and message == {'event': 'activity', 'data': {'active': False}}:
                ended.set()

        with patch.object(self.host, '_emit', side_effect=emit):
            started = self.host.invoke(identity, 'run', {'text': 'test', 'batches': 2})
            self.assertTrue(started['ok'], started)
            self.assertEqual(started['result']['state'], 'running')
            self.assertTrue(self.host._work_state(identity)['background'])
            protected = self.host.plugin_action(identity, 'stop')
            self.assertTrue(protected['result']['needsConfirmation'], protected)
            self.assertFalse(self.host.invoke(identity, 'run', {'batches': 2})['ok'])
            self.assertTrue(self.host.invoke(identity, 'cancel')['ok'])
            self.assertTrue(ended.wait(3))
            self.assertEqual(self.host.invoke(identity, 'snapshot')['result']['state'], 'cancelled')
            self.assertFalse(self.host._work_state(identity)['background'])
            self.assertTrue(self.host.plugin_action(identity, 'stop')['ok'])

    def test_downloaded_sdk_runs_job_example_without_site_packages(self):
        with zipfile.ZipFile(io.BytesIO(self.host._starter_bytes())) as archive:
            self.assertIn('cove-plugin-starter/sdk/toolbench/plugin_framework/jobs.py', archive.namelist())
            archive.extractall(self.root / 'download')
        project = self.root / 'download/cove-plugin-starter'
        for name in ('plugin.py', 'manifest.json', 'dev.py'):
            shutil.copyfile(EXAMPLE / name, project / name)
        result = subprocess.run([sys.executable, '-S', str(project / 'dev.py')], cwd=project,
                                capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual((value['state'], value['completed'], value['total']), ('completed', 3, 3))
        self.assertIn('SHA-256', value['message'])


if __name__ == '__main__':
    unittest.main()
