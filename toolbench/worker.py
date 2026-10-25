"""One process per plugin. stdout is reserved for NDJSON protocol messages."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import threading
import traceback
import uuid

from toolbench.sdk import Context
from toolbench.plugin_framework.policy import POLICY
from toolbench.plugin_framework.framing import FrameTooLarge, RUNTIME_FRAME_BYTES, read_frames


def main() -> None:
    folder = Path(sys.argv[1]).resolve()
    data_dir = Path(sys.argv[2]).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    protocol = sys.stdout
    sys.stdout = sys.stderr  # A plugin's print() must never corrupt the protocol.
    write_lock = threading.Lock()

    def publish(value: dict) -> None:
        with write_lock:
            protocol.write(json.dumps(value, ensure_ascii=True) + "\n")
            protocol.flush()

    spec = importlib.util.spec_from_file_location(
        f"toolbench_plugin_{manifest['id'].replace('.', '_')}", folder / "plugin.py",
        submodule_search_locations=[str(folder)])
    if spec is None or spec.loader is None:
        raise RuntimeError("无法载入插件")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    if (folder / "vendor").is_dir():
        sys.path.insert(0, str(folder / "vendor"))
    spec.loader.exec_module(module)
    request_context = threading.local()
    host_pending = {}
    host_lock = threading.Lock()

    def host_call(operation, payload):
        ticket = uuid.uuid4().hex
        waiting = {'ready': threading.Event()}
        with host_lock:
            host_pending[ticket] = waiting
        try:
            publish({'hostCall': ticket, 'requestId': getattr(request_context, 'id', None),
                     'operation': operation, 'payload': payload})
            if not waiting['ready'].wait(POLICY.host_call):
                raise TimeoutError('工作台工具调用或操作确认超时')
            response = waiting['response']
            if not response.get('ok'):
                raise RuntimeError(response.get('error', '工具调用失败'))
            return response['result']
        finally:
            with host_lock:
                host_pending.pop(ticket, None)

    plugin = None
    constructed = threading.Event()
    input_closed = threading.Event()
    commands = set(manifest["commands"])

    def dispatch(request: dict) -> None:
        request_id = request.get("id")
        request_context.id = request_id
        try:
            constructed.wait()
            if plugin is None:
                raise RuntimeError("运行时初始化失败")
            command = request["command"]
            if command not in commands or command.startswith("_"):
                raise ValueError("插件未声明此命令")
            payload = request.get("payload", {})
            if not isinstance(payload, dict):
                raise ValueError("命令参数必须为对象")
            result = getattr(plugin, command)(**payload)
            publish({"id": request_id, "ok": True, "result": result})
        except Exception as exc:
            publish({"id": request_id, "ok": False, "error": str(exc) or type(exc).__name__,
                     "code": getattr(exc, "code", "PLUGIN_ERROR"),
                     "details": getattr(exc, "details", {})})

    def read_input():
        try:
            for line in read_frames(sys.stdin, RUNTIME_FRAME_BYTES):
                try:
                    request = json.loads(line)
                    if 'hostResponse' in request:
                        with host_lock:
                            waiting = host_pending.get(request['hostResponse'])
                            if waiting:
                                waiting['response'] = request
                                waiting['ready'].set()
                    else:
                        threading.Thread(target=dispatch, args=(request,), daemon=True).start()
                except Exception:
                    traceback.print_exc(file=sys.stderr)
        except FrameTooLarge as exc:
            publish({'event': 'runtime_failure', 'data': exc.details()})
        finally:
            input_closed.set()
            with host_lock:
                for waiting in host_pending.values():
                    waiting['response'] = {'ok': False, 'error': '宿主连接已关闭'}
                    waiting['ready'].set()

    threading.Thread(target=read_input, daemon=True).start()
    try:
        plugin = module.Tool(Context(publish, str(data_dir), host_call,
                                     localization=manifest.get('localization')))
        constructed.set()
        publish({'event': 'ready', 'data': {}})
        input_closed.wait()
    finally:
        constructed.set()
        if plugin is not None:
            plugin.close()


if __name__ == '__main__':
    main()
