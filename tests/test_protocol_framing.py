from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from toolbench.plugin_framework.framing import (
    FrameTooLarge, MCP_FRAME_BYTES, READ_CHUNK_BYTES, RUNTIME_FRAME_BYTES, read_frames,
)
from toolbench.protocol import serve_rpc
from toolbench.runtime import PluginFailure, Worker


ROOT = Path(__file__).resolve().parents[1]


class RepeatingInput:
    """A huge unfinished frame without allocating that frame in the fixture."""
    def __init__(self, binary=False):
        self.binary = binary
        self.consumed = 0
        self.requests = []

    def readline(self, size=-1):
        if not 0 < size <= READ_CHUNK_BYTES:
            raise AssertionError('Unbounded input read')
        self.requests.append(size)
        self.consumed += size
        return (b'x' if self.binary else 'x') * size


class FrameReaderTests(unittest.TestCase):
    def test_oversize_without_newline_does_not_read_or_allocate_the_whole_input(self):
        for binary in (False, True):
            with self.subTest(binary=binary):
                incoming = RepeatingInput(binary)
                with self.assertRaises(FrameTooLarge) as caught:
                    next(read_frames(incoming, 128))
                self.assertEqual(caught.exception.details(), {'code': 'FRAME_TOO_LARGE', 'limitBytes': 128})
                self.assertLessEqual(incoming.consumed, 130)

    def test_exact_utf8_byte_boundary_for_text_and_binary_streams(self):
        value = '汉😀'
        self.assertEqual(len(value.encode('utf-8')), 7)
        for ending in ('\n', '\r\n', ''):
            for binary in (False, True):
                with self.subTest(ending=ending, binary=binary):
                    content = value + ending
                    incoming = io.BytesIO(content.encode()) if binary else io.StringIO(content)
                    self.assertEqual(list(read_frames(incoming, 7)), [value.encode() if binary else value])
                    incoming = io.BytesIO(content.encode()) if binary else io.StringIO(content)
                    with self.assertRaises(FrameTooLarge):
                        list(read_frames(incoming, 6))

    def test_crlf_split_across_chunks_and_next_valid_frame(self):
        for binary in (False, True):
            with self.subTest(binary=binary), patch('toolbench.plugin_framework.framing.READ_CHUNK_BYTES', 5):
                incoming = io.BytesIO(b'abcd\r\n{}\n') if binary else io.StringIO('abcd\r\n{}\n')
                self.assertEqual(list(read_frames(incoming, 4)), [b'abcd', b'{}'] if binary else ['abcd', '{}'])

    def test_oversize_ends_session_without_interpreting_remainder_as_new_frame(self):
        incoming = io.StringIO('x' * 100 + '\n{"safe":true}\n')
        frames = read_frames(incoming, 8)
        with self.assertRaises(FrameTooLarge):
            next(frames)
        self.assertEqual(list(frames), [])
        self.assertLessEqual(incoming.tell(), 10)

    def test_mcp_oversize_returns_structured_error_and_never_dispatches_next_request(self):
        request = {'id': 2, 'method': 'tools/call', 'params': {'name': 'must_not_run'}}
        incoming = io.StringIO('private-input' + 'x' * MCP_FRAME_BYTES + '\n' + json.dumps(request) + '\n')
        outgoing, calls = io.StringIO(), []
        serve_rpc(incoming, outgoing, lambda: [], lambda *args: calls.append(args))
        replies = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]['error']['data'], {'code': 'FRAME_TOO_LARGE', 'limitBytes': MCP_FRAME_BYTES})
        self.assertIsNone(replies[0]['id'])
        self.assertEqual(calls, [])
        self.assertNotIn('private-input', outgoing.getvalue())

    def test_mcp_keeps_next_request_after_bounded_invalid_json(self):
        outgoing = io.StringIO()
        serve_rpc(io.StringIO('not-json\n{"id":2,"method":"ping"}\n'), outgoing, lambda: [], lambda *_: None)
        replies = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual(replies[0]['error']['code'], -32700)
        self.assertEqual(replies[1]['result'], {})


class WorkerFrameTests(unittest.TestCase):
    def setUp(self):
        test_root = ROOT / 'artifacts' / 'tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='protocol-', dir=test_root)
        self.root = Path(self.temporary.name)
        self.folder = self.root / 'plugin'
        self.folder.mkdir()
        self.manifest = {'id': 'test.framing', 'commands': ['run']}
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def tearDown(self):
        self.temporary.cleanup()

    def source(self, body):
        (self.folder / 'plugin.py').write_text('from toolbench.sdk import Plugin\n' + body, encoding='utf-8')

    def test_worker_stdout_oversize_without_newline_fails_promptly_and_keeps_diagnostics_private(self):
        self.source('import sys, threading\nclass Tool(Plugin):\n'
                    ' def run(self):\n'
                    '  sys.__stdout__.write("private-input" * 100)\n'
                    '  sys.__stdout__.flush()\n'
                    '  threading.Event().wait(30)\n')
        with patch('toolbench.runtime.RUNTIME_FRAME_BYTES', 256):
            worker = Worker(self.folder, self.manifest, self.root / 'data', lambda *_: None, root=ROOT)
        try:
            with ThreadPoolExecutor() as pool:
                future = pool.submit(worker.invoke, 'run', {})
                try:
                    with self.assertRaises(PluginFailure) as caught:
                        future.result(timeout=4)
                finally:
                    # Also makes failure of the timing assertion bounded.
                    worker.close()
            self.assertEqual(caught.exception.response['code'], 'FRAME_TOO_LARGE')
            self.assertIsNotNone(worker.process.poll())
            report = worker.diagnostics.save('test', worker.process.poll())
            self.assertNotIn('private-input', json.dumps(report))
            self.assertTrue(any(item.get('type') == 'FrameTooLarge' for item in report['records']))
        finally:
            worker.close()

    def test_worker_input_oversize_closes_session_before_following_command(self):
        self.source('from pathlib import Path\nclass Tool(Plugin):\n'
                    ' def run(self):\n'
                    '  Path(self.context.data_dir, "executed").write_text("unexpected")\n'
                    '  return True\n')
        command = [sys.executable, '-c',
                   'from toolbench import worker; worker.RUNTIME_FRAME_BYTES = 256; worker.main()',
                   str(self.folder), str(self.root / 'data')]
        following = json.dumps({'id': 3, 'command': 'run', 'payload': {}})
        result = subprocess.run(command, input='private-input' * 100 + '\n' + following + '\n',
                                cwd=ROOT, text=True, encoding='utf-8', capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        messages = [json.loads(line) for line in result.stdout.splitlines()]
        failure = next(message for message in messages if message.get('event') == 'runtime_failure')
        self.assertEqual(failure['data'], {'code': 'FRAME_TOO_LARGE', 'limitBytes': 256})
        self.assertFalse((self.root / 'data' / 'executed').exists())
        self.assertNotIn('private-input', result.stdout + result.stderr)

    def test_worker_preserves_existing_sixteen_mib_result_support(self):
        self.source('class Tool(Plugin):\n def run(self): return "x" * (16 * 1024 * 1024)\n')
        worker = Worker(self.folder, self.manifest, self.root / 'data', lambda *_: None, root=ROOT)
        try:
            self.assertEqual(len(worker.invoke('run', {})), 16 * 1024 * 1024)
            self.assertGreater(RUNTIME_FRAME_BYTES, 16 * 1024 * 1024)
        finally:
            worker.close()

    def test_worker_accepts_large_sdk_host_response_on_the_input_channel(self):
        self.source('class Tool(Plugin):\n'
                    ' def run(self): return len(self.context.call_tool("large_result", {}))\n')
        worker = Worker(self.folder, self.manifest, self.root / 'data', lambda *_: None,
                        host_call=lambda *_: 'x' * (16 * 1024 * 1024), root=ROOT)
        try:
            self.assertEqual(worker.invoke('run', {}), 16 * 1024 * 1024)
        finally:
            worker.close()


if __name__ == '__main__':
    unittest.main()
