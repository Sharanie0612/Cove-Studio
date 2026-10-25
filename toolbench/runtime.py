"""Independent plugin subprocess transport and resource lifecycle."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from toolbench.plugin_framework.policy import POLICY
from toolbench.plugin_framework.diagnostics import Diagnostics
from toolbench.plugin_framework.framing import FrameTooLarge, RUNTIME_FRAME_BYTES, read_frames
from toolbench.plugin_framework.interpreter import select_interpreter


class PluginFailure(Exception):
    def __init__(self, response):
        super().__init__(response.get("error", "插件执行失败"))
        self.response = response


class Worker:
    def __init__(self, folder: Path, manifest: dict, data_dir: Path, emit,
                 interpreter: str | None = None, host_call=None, *, root: Path | None = None,
                 policy=None):
        ROOT = root or Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
        self.manifest = manifest
        self.emit = emit
        self.host_call = host_call
        self.policy = policy or POLICY
        self.diagnostics = Diagnostics(data_dir / 'runtime-diagnostics.json')
        self.startup_waits = 0
        self.closed = threading.Event()
        self.pending: dict[str, dict] = {}
        self.lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.ready = threading.Event()
        self.started = False
        self.last_used = time.monotonic()
        interpreter_choice = select_interpreter(folder, interpreter)
        sdk_path = ROOT / "sdk-runtime" if getattr(sys, "frozen", False) else ROOT
        env = dict(os.environ, PYTHONPATH=str(sdk_path), PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        if interpreter_choice.frozen_worker:
            command = [str(interpreter_choice.executable), "--worker", str(folder), str(data_dir)]
        else:
            command = [str(interpreter_choice.executable), "-m", "toolbench.worker", str(folder), str(data_dir)]
        try:
            self.process = subprocess.Popen(
                command,
                cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except OSError as exc:
            self.diagnostics.add('exception', type=type(exc).__name__)
            report = self.diagnostics.save('launch')
            raise PluginFailure({'ok': False, 'code': 'STARTUP_FAILED',
                                 'error': '无法启动 Python 运行环境，请检查解释器路径。',
                                 'details': {'diagnosticId': report['id']}}) from None
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.stderr_reader = threading.Thread(target=self._stderr, daemon=True)
        self.stderr_reader.start()
        self.reader.start()
        self.policy.wait(self.ready, lambda: self.startup_waits, startup=True)
        if not self.started:
            self.close()
            report = self.diagnostics.save('startup', self.process.poll())
            failures = [item for item in report['records'] if item['kind'] == 'exception']
            reason = (failures[-1].get('module') or failures[-1]['type']) if failures else '进程未能就绪'
            raise PluginFailure({'ok': False, 'code': 'STARTUP_FAILED',
                                 'error': f'插件启动失败：{reason}。请查看启动诊断或设置独立 Python 环境。',
                                 'details': {'diagnosticId': report['id']}})

    def _read(self):
        failure = None
        try:
            for line in read_frames(self.process.stdout, RUNTIME_FRAME_BYTES):
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(message, dict):
                    self.diagnostics.add('protocol', type='InvalidMessage')
                    continue
                if 'hostCall' in message:
                    with self.lock:
                        parent = self.pending.get(message.get('requestId'))
                        if parent is None and len(self.pending) == 1:
                            parent = next(iter(self.pending.values()))
                        if parent is not None:
                            parent['host_waits'] += 1
                        elif not self.started:
                            self.startup_waits += 1
                    message['_parent'] = parent
                    threading.Thread(target=self._host_request, args=(message,), daemon=True).start()
                elif message.get("event") == "ready":
                    self.started = True
                    self.ready.set()
                elif "id" in message:
                    with self.lock:
                        pending = self.pending.get(message["id"])
                        if pending:
                            pending["response"] = message
                            pending["ready"].set()
                elif "event" in message:
                    self.emit(self.manifest["id"], message)
        except FrameTooLarge as exc:
            self.diagnostics.add('protocol', type='FrameTooLarge', limitBytes=exc.limit_bytes)
            failure = {'ok': False, 'code': exc.code, 'error': str(exc), 'details': exc.details()}
            # The frame cannot be safely resynchronized. End only this worker;
            # the normal failure event cancels its outstanding approvals.
            if self.process.poll() is None:
                try:
                    self.process.kill()
                except OSError:
                    pass
        finally:
            self.ready.set()
            with self.lock:
                for pending in self.pending.values():
                    if not pending["ready"].is_set():
                        pending["response"] = failure or {"ok": False, "error": "插件进程已退出，请重试以重新启动"}
                        pending["ready"].set()
            if not self.closed.is_set():
                self.stderr_reader.join(timeout=.5)
                try:
                    exit_code = self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    exit_code = self.process.poll()
                report = self.diagnostics.save('exit', exit_code)
                self.emit(self.manifest['id'], {'event': 'runtime_failure', 'data': {'diagnosticId': report['id']}})
            self.emit(self.manifest["id"], {"event": "activity", "data": {"active": False}})
            self.emit(self.manifest["id"], {"event": "status", "data": {"connected": False, "message": "插件进程已停止"}})

    def _host_request(self, message):
        try:
            if not self.host_call:
                raise ValueError('宿主没有启用工具桥接')
            if self.closed.is_set():
                raise ValueError('调用方已停止')
            reply = {'ok': True, 'result': self.host_call(self.manifest['id'], message['operation'], message.get('payload', {}))}
        except Exception as exc:
            reply = {'ok': False, 'error': str(exc)}
        try:
            with self.write_lock:
                self.process.stdin.write(json.dumps({'hostResponse': message['hostCall'], **reply}) + '\n')
                self.process.stdin.flush()
        except (OSError, ValueError):
            pass
        finally:
            with self.lock:
                if message.get('_parent') is not None:
                    message['_parent']['host_waits'] -= 1
                elif self.startup_waits:
                    self.startup_waits -= 1

    def _stderr(self):
        while line := self.process.stderr.readline(2048):
            self.diagnostics.stderr(line)

    def invoke(self, command: str, payload: dict):
        self.last_used = time.monotonic()
        request_id = uuid.uuid4().hex
        pending = {"ready": threading.Event(), 'host_waits': 0}
        with self.lock:
            self.pending[request_id] = pending
        try:
            with self.write_lock:
                self.process.stdin.write(json.dumps({"id": request_id, "command": command, "payload": payload}) + "\n")
                self.process.stdin.flush()
            if not self.policy.wait(pending['ready'], lambda: pending['host_waits']):
                self.emit(self.manifest['id'], {'event': 'runtime_failure', 'data': {'reason': 'timeout'}})
                self.diagnostics.add('timeout', command=command)
                self.close()
                self.diagnostics.save('timeout', self.process.poll())
                raise TimeoutError("插件响应超时，已释放该插件进程；可以重试")
            response = pending["response"]
            if not response.get("ok"):
                raise PluginFailure(response)
            return response.get("result")
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def close(self):
        self.closed.set()
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait(timeout=2)
        for thread in (self.reader, self.stderr_reader):
            if thread is not threading.current_thread():
                thread.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream and not stream.closed:
                stream.close()
