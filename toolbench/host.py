from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import sys
import threading
import time
from toolbench.management import PluginManager
from toolbench.desktop import DesktopApi
from toolbench.developer import DeveloperApi
from toolbench.runtime import Worker, PluginFailure
from toolbench.manifest import validate_manifest  # Compatibility for older host importers.
from toolbench.assistance import AssistanceApi
from toolbench.views import ViewApi, PluginViews
from toolbench.contracts import require_compatible
from toolbench.plugin_framework.lifecycle import work_state, work_summary

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


class Host(PluginManager, DesktopApi, DeveloperApi, AssistanceApi, ViewApi):
    def __init__(self, plugins_dir: Path | None = None, data_dir: Path | None = None):
        default_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Cove" if getattr(sys, "frozen", False) else ROOT / ".local"
        self.data_dir = data_dir or Path(os.environ.get("TOOLBENCH_DATA_DIR", str(default_data)))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.plugins = {}
        self.issues = []
        self.workers: dict[str, Worker] = {}
        self.events = deque(maxlen=2000)
        self.lock = threading.RLock()
        self._starting = set()
        self._closing = False
        self._views = PluginViews(self)
        self._setup_management(plugins_dir)
        self._setup_assistance()

    def _emit(self, plugin_id, message):
        if message.get('event') == 'runtime_failure' and hasattr(self, '_assistant_broker'):
            self._assistant_broker.cancel_owner(plugin_id)
        with self.lock:
            if message.get("event") == "status":
                self._connected[plugin_id] = bool(message.get("data", {}).get("connected"))
                self._status_messages[plugin_id] = str(message.get('data', {}).get('message', ''))
            if message.get("event") == "activity":
                self._active_tasks[plugin_id] = bool(message.get("data", {}).get("active"))
            self.events.append({"pluginId": plugin_id, "time": time.time(), **message})

    def _work_state(self, plugin_id):
        return work_state(self, plugin_id)

    def _work_summary(self, plugin_id=None):
        return work_summary(self, plugin_id)

    def _ensure_worker(self, plugin_id):
        if self._closing:
            raise ValueError('工作台正在关闭')
        require_compatible(self.plugins[plugin_id][1])
        if plugin_id in self._preferences["disabled"]:
            raise ValueError("插件已停用，请先在插件管理中启用")
        with self.lock:
            worker = self.workers.get(plugin_id)
        if worker and worker.process.poll() is None:
            return worker
        if worker:
            worker.close()
        folder, manifest = self.plugins[plugin_id]
        with self.lock:
            self._starting.add(plugin_id)
        try:
            worker = Worker(folder, manifest, self.data_dir / plugin_id, self._emit,
                            self._preferences["interpreters"].get(plugin_id), self._host_tool_call, root=ROOT)
            with self.lock:
                closing = self._closing
                if not closing:
                    self.workers[plugin_id] = worker
            if closing:
                worker.close()
                raise ValueError('工作台正在关闭')
            return worker
        finally:
            with self.lock:
                self._starting.discard(plugin_id)

    def invoke(self, plugin_id: str, command: str, payload: dict | None = None):
        return self._invoke(plugin_id, command, payload)

    def _invoke(self, plugin_id, command, payload=None, admission=None):
        try:
            if plugin_id not in self.plugins:
                raise ValueError("工具不存在")
            if command not in self.plugins[plugin_id][1]["commands"]:
                raise ValueError("工具未声明此命令")
            if not isinstance(payload or {}, dict):
                raise ValueError("参数必须为对象")
            if len(json.dumps(payload or {})) > 900_000:
                raise ValueError("命令参数过大")
            with self._management_lock:
                if admission:
                    admission()
                worker = self._ensure_worker(plugin_id)
                self._invocations[plugin_id] = self._invocations.get(plugin_id, 0) + 1
            try:
                return {"ok": True, "result": worker.invoke(command, payload or {})}
            finally:
                with self._management_lock:
                    self._invocations[plugin_id] -= 1
        except PluginFailure as exc:
            return {key: value for key, value in exc.response.items() if key != "id"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def drain_events(self):
        with self.lock:
            result = list(self.events)
            self.events.clear()
        return result

    def close(self):
        with self.lock:
            self._closing = True
        for ticket in list(self._views.sessions):
            self._views.close(ticket)
        self._assistant_broker.close()
        if getattr(self, '_assistant_gateway', None):
            self._assistant_gateway.close()
        with self.lock:
            workers = list(self.workers.values())
        for worker in workers:
            worker.close()
