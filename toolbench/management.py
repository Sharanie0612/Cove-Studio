"""Plugin discovery, transactional package import and explicit lifecycle operations."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import time
import uuid
import zipfile

import psutil
from toolbench.dialogs import PLUGIN_FILTERS, PYTHON_FILTERS
from toolbench.sdk import atomic_json
from toolbench import __version__
from toolbench.paths import installation_root
from toolbench.contracts import CAPABILITIES, SDK_VERSION, compatibility_report, require_compatible
from toolbench.plugin_framework.builtins import MCP_ID, is_host_service
from toolbench.plugin_framework.diagnostics import load_diagnostics
from toolbench.plugin_framework.lifecycle import confirmation
from toolbench.plugin_framework.transactions import rename_directory


def remove_inside(path: Path, root: Path):
    if path.is_symlink() or path.resolve() == root.resolve() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("操作目录超出插件管理范围")
    if path.exists():
        shutil.rmtree(path)


class PluginManager:
    def _setup_management(self, plugins_dir):
        from toolbench.host import ROOT
        self._builtin_root = plugins_dir if plugins_dir is not None else (ROOT / "builtin-plugins" if (ROOT / "builtin-plugins").exists() else ROOT / "plugins/projects")
        self._managed_root = self.data_dir / "installed"
        self._managed_root.mkdir(parents=True, exist_ok=True)
        self._plugin_drop_root = installation_root() / "plugins" if getattr(__import__("sys"), "frozen", False) else ROOT / "plugins"
        self._preferences_path = self.data_dir / "plugin-preferences.json"
        self._preferences = {"disabled": [], "interpreters": {}, "removed": []}
        if self._preferences_path.exists():
            try:
                saved = json.loads(self._preferences_path.read_text(encoding="utf-8"))
                if isinstance(saved.get("disabled"), list) and isinstance(saved.get("interpreters", {}), dict) and isinstance(saved.get('removed', []), list):
                    self._preferences.update(saved)
            except (ValueError, OSError):
                # Do not silently overwrite an unreadable preference file.
                raise RuntimeError("插件设置无法读取，请先恢复 plugin-preferences.json")
        self._connected = {}
        self._status_messages = {}
        self._active_tasks = {}
        self._invocations = {}
        self._package_tickets = {}
        self._export_tickets = {}
        self._management_lock = __import__("threading").RLock()
        self._scan_plugins()

    def _scan_plugins(self):
        from toolbench.registry import discover_plugins
        plugins, issues, available = discover_plugins(
            self._builtin_root, self._managed_root, self._plugin_drop_root,
            self._preferences['removed'])
        with self.lock:
            self.plugins, self.issues, self.available_plugins = plugins, issues, available

    def catalog(self):
        tools = []
        with self.lock:
            entries = list(self.plugins.items())
        for plugin_id, (folder, manifest) in entries:
            worker = self.workers.get(plugin_id)
            running = bool(worker and worker.process.poll() is None)
            memory = 0
            if running:
                try:
                    memory = psutil.Process(worker.process.pid).memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            tools.append({**manifest, "compatibilityStatus": compatibility_report(manifest), "enabled": plugin_id not in self._preferences["disabled"],
                          "builtin": folder.parent.resolve() == self._builtin_root.resolve(),
                          "runtime": {"running": running, "connected": self._connected.get(plugin_id, False),
                                      "activity": self._work_state(plugin_id),
                                      "memoryBytes": memory, "pid": worker.process.pid if running else None,
                                      "message": self._status_messages.get(plugin_id, '')},
                          "customRuntime": bool(self._preferences["interpreters"].get(plugin_id))})
        return {"tools": tools, "available": self.available_plugins, "issues": self.issues, "hostVersion": __version__, "sdkVersion": SDK_VERSION, "capabilities": sorted(CAPABILITIES),
                "dataPath": str(self.data_dir), "pluginsPath": str(self._plugin_drop_root), "packaged": bool(getattr(__import__('sys'), 'frozen', False)),
                "windowState": {"maximized": getattr(self, '_maximized', False)}}

    def _stop_plugin(self, plugin_id):
        if hasattr(self, '_assistant_broker'):
            self._assistant_broker.cancel_owner(plugin_id)
        with self.lock:
            worker = self.workers.pop(plugin_id, None)
        if worker:
            worker.close()
        self._connected[plugin_id] = False
        self._active_tasks[plugin_id] = False
        self._emit(plugin_id, {"event": "status", "data": {"connected": False, "message": "插件已停止"}})

    def plugin_diagnostics(self, plugin_id: str):
        if plugin_id not in self.plugins:
            return {'ok': False, 'error': '插件不存在'}
        return {'ok': True, 'result': load_diagnostics(self.data_dir / plugin_id / 'runtime-diagnostics.json')}

    def plugin_action(self, plugin_id: str, action: str, confirmed: bool = False):
        try:
            if not isinstance(confirmed, bool):
                raise ValueError('无效的确认结果')
            with self._management_lock:
                if action == "stop_idle":
                    stopped = 0
                    for current, worker in list(self.workers.items()):
                        if not self._work_state(current)['active']:
                            self._stop_plugin(current)
                            stopped += 1
                    return {"ok": True, "result": {"stopped": stopped}}
                if action == 'restore':
                    if not any(item['id'] == plugin_id for item in self.available_plugins):
                        raise ValueError('没有可恢复的预置插件')
                    self._preferences['removed'] = [item for item in self._preferences['removed'] if item != plugin_id]
                    self._preferences['disabled'] = [item for item in self._preferences['disabled'] if item != plugin_id]
                    atomic_json(self._preferences_path, self._preferences)
                    self._scan_plugins()
                    return {'ok': True, 'result': self.catalog()}
                if plugin_id not in self.plugins:
                    raise ValueError("插件不存在")
                folder, _ = self.plugins[plugin_id]
                if action == "remove" and is_host_service(plugin_id):
                    raise ValueError("MCP 是预装内置插件，可停用但不能移除")
                if is_host_service(plugin_id) and action in {"stop", "restart", "start"}:
                    raise ValueError("请使用启用或停用控制 MCP 连接插件")
                if action in {"stop", "restart", "disable", "remove"}:
                    protection = confirmation(self, plugin_id)
                    if protection['needsConfirmation'] and not confirmed:
                        return {'ok': True, 'result': protection}
                    self._stop_plugin(plugin_id)
                if action in {"start", "restart"}:
                    if plugin_id in self._preferences["disabled"]:
                        raise ValueError("请先启用插件")
                    self._ensure_worker(plugin_id)
                elif action in {"enable", "disable"}:
                    disabled = set(self._preferences["disabled"])
                    disabled.add(plugin_id) if action == "disable" else disabled.discard(plugin_id)
                    self._preferences["disabled"] = sorted(disabled)
                    atomic_json(self._preferences_path, self._preferences)
                    if plugin_id == MCP_ID:
                        self._sync_mcp_service()
                elif action == "remove":
                    if folder.parent.resolve() == self._builtin_root.resolve():
                        # Bundled source stays intact so the user can add it again.
                        self._preferences['removed'] = sorted(set(self._preferences['removed']) | {plugin_id})
                    else:
                        remove_inside(folder, self._plugin_drop_root if folder.parent.resolve() == self._plugin_drop_root.resolve() else self._managed_root)
                    self._preferences["disabled"] = [item for item in self._preferences["disabled"] if item != plugin_id]
                    self._preferences["interpreters"].pop(plugin_id, None)
                    atomic_json(self._preferences_path, self._preferences)
                    self._scan_plugins()
                elif action not in {"stop", "start", "restart", "enable", "disable"}:
                    raise ValueError("不支持的插件操作")
                return {"ok": True, "result": self.catalog()}
        except Exception as exc:
            return getattr(exc, 'response', {"ok": False, "error": str(exc)})

    def _inspect_package(self, path: Path):
        from toolbench.packages import inspect_archive
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("插件包不能超过 20 MB")
        content = path.read_bytes()
        inspected = inspect_archive(content)
        manifest, relative = inspected["manifest"], inspected["files"]
        require_compatible(manifest)
        if any(item['id'] == manifest['id'] for item in self.available_plugins):
            raise ValueError('此插件随 Cove 提供，请在“可添加的插件”中重新添加')
        previous = self.plugins.get(manifest["id"])
        if previous and previous[0].parent.resolve() == self._builtin_root.resolve():
            raise ValueError("该 id 属于内置插件，不能覆盖；请使用独立的插件 id")
        token = uuid.uuid4().hex
        # A ticket binds installation to immutable inspected bytes, not a mutable file path.
        self._package_tickets = {token: {"content": content, "manifest": manifest, "files": relative, "time": time.monotonic()}}
        return {"ticket": token, "manifest": manifest, "sha256": hashlib.sha256(content).hexdigest(),
                "fileCount": len(relative), "sizeBytes": len(content),
                "previousVersion": previous[1]["version"] if previous else None,
                "requirements": inspected["requirements"]}

    def open_plugins_folder(self):
        try:
            self._plugin_drop_root.mkdir(parents=True, exist_ok=True)
            os.startfile(self._plugin_drop_root)
            return {'ok': True}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def rescan_plugins(self):
        try:
            with self._management_lock:
                self._scan_plugins()
            return {'ok': True, 'result': self.catalog()}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def inspect_plugin_package(self):
        try:
            import webview
            chosen = self._window.create_file_dialog(webview.FileDialog.OPEN,
                file_types=PLUGIN_FILTERS, allow_multiple=False, directory=str(self._plugin_drop_root))
            return {"ok": True, "result": self._inspect_package(Path(chosen[0])) if chosen else None}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def install_plugin(self, ticket: str):
        staging = None
        backup = None
        try:
            with self._management_lock:
                package = self._package_tickets.pop(ticket, None)
                if not package or time.monotonic() - package["time"] > 600:
                    raise ValueError("导入预览已过期，请重新选择插件包")
                manifest = package["manifest"]
                plugin_id = manifest["id"]
                if self._work_state(plugin_id)['active']:
                    raise ValueError('插件还有活动工作，请先停止任务或关闭连接，再重新预览并更新')
                staging = self._managed_root / (".staging-" + uuid.uuid4().hex)
                staging.mkdir()
                with zipfile.ZipFile(io.BytesIO(package["content"])) as archive:
                    for relative, original in package["files"].items():
                        target = staging / relative
                        if not target.resolve().is_relative_to(staging.resolve()):
                            raise ValueError("插件路径超出目标目录")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(archive.read(original))
                destination = self._managed_root / plugin_id
                if destination.exists():
                    self._stop_plugin(plugin_id)
                    previous = self._managed_root / (".backup-" + uuid.uuid4().hex)
                    rename_directory(destination, previous)
                    backup = previous
                try:
                    rename_directory(staging, destination)
                    staging = None
                except OSError as install_error:
                    if backup:
                        try:
                            rename_directory(backup, destination)
                        except OSError as restore_error:
                            self._scan_plugins()
                            return {"ok": False, "error": "插件更新与自动恢复均被文件占用阻止。原插件已保留，请关闭占用后重试恢复。",
                                    "recoveryPath": str(backup), "details": str(restore_error)}
                        backup = None
                    raise install_error
                if backup:
                    try:
                        remove_inside(backup, self._managed_root)
                    except OSError:
                        # New code is already committed; retain the original for recovery.
                        self._scan_plugins()
                        return {"ok": True, "result": {"id": plugin_id, "catalog": self.catalog(),
                                "warning": "新版已安装，旧版备份暂被占用，已保留。", "backupPath": str(backup)}}
                self._scan_plugins()
                return {"ok": True, "result": {"id": plugin_id, "catalog": self.catalog()}}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            if staging and staging.exists():
                try:
                    remove_inside(staging, self._managed_root)
                except OSError:
                    # A cleanup lock must not hide the transaction's actual outcome.
                    pass

    def configure_plugin_runtime(self, plugin_id: str):
        try:
            if plugin_id not in self.plugins:
                raise ValueError("插件不存在")
            if self._work_state(plugin_id)['active']:
                raise ValueError('插件还有活动工作，请先停止任务或关闭连接，再更改运行环境')
            import webview
            chosen = self._window.create_file_dialog(webview.FileDialog.OPEN,
                file_types=PYTHON_FILTERS, allow_multiple=False)
            if not chosen:
                return {"ok": True, "result": None}
            python = Path(chosen[0]).resolve()
            if python.name.lower() != "python.exe":
                raise ValueError("请选择虚拟环境或 Python 安装目录中的 python.exe")
            self._stop_plugin(plugin_id)
            self._preferences["interpreters"][plugin_id] = str(python)
            atomic_json(self._preferences_path, self._preferences)
            return {"ok": True, "result": self.catalog()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
