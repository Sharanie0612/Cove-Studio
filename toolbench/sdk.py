"""The small API shared by all plugins. No frontend dependencies required."""
from __future__ import annotations

import threading
from typing import Any, Callable
from toolbench.plugin_framework.persistence import atomic_json  # Public SDK v1 import remains stable.
from toolbench.plugin_framework.jobs import BackgroundJob, JobControl, JobCancelled


class CommandError(Exception):
    def __init__(self, message: str, code: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class Context:
    def __init__(self, publish: Callable[[dict], None], data_dir: str, host_call=None, *, localization=None):
        self._publish = publish
        self.data_dir = data_dir
        self._host_call = host_call
        self._localization = localization or {}

    @property
    def locale(self):
        """Read the host's current language without restarting a running plugin."""
        if self._host_call:
            return self._host_call('host.locale', {})
        return self._localization.get('defaultLocale', 'en-US')

    def t(self, message: str, **values) -> str:
        """Resolve this plugin's own messages; never changes returned/user data."""
        from toolbench.plugin_framework.localization import translate
        return translate(self._localization, self.locale, message, values)

    def tools(self):
        if not self._host_call:
            raise RuntimeError('此环境没有工作台工具桥接，请在 Cove 中运行')
        return self._host_call('tools.list', {})

    def call_tool(self, name: str, arguments: dict):
        if not self._host_call:
            raise RuntimeError('此环境没有工作台工具桥接，请在 Cove 中运行')
        return self._host_call('tools.call', {'name': name, 'arguments': arguments})

    def emit(self, event: str, **data: Any) -> None:
        self._publish({"event": event, "data": data})

    def status(self, connected: bool, message: str = "") -> None:
        self.emit("status", connected=connected, message=message)

    def received(self, data: bytes) -> None:
        self.emit("data", direction="rx", text=data.decode("utf-8", errors="replace"),
                  hex=data.hex(" ").upper(), size=len(data))

    def sent(self, data: bytes) -> None:
        self.emit("data", direction="tx", text=data.decode("utf-8", errors="replace"),
                  hex=data.hex(" ").upper(), size=len(data))


class Plugin:
    def __init__(self, context: Context):
        self.context = context
        self.lock = threading.RLock()

    def close(self) -> None:
        """Release all resources. Called when the host shuts down."""


def encode_payload(text: str, mode: str = "text", newline: str = "none") -> bytes:
    if mode == "hex":
        try:
            data = bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("十六进制内容无效，请按完整字节输入，例如 48 65 6C 6C 6F") from exc
    elif mode == "text":
        data = text.encode("utf-8")
    else:
        raise ValueError("不支持的数据编码")
    endings = {"none": b"", "lf": b"\n", "crlf": b"\r\n", "cr": b"\r"}
    if newline not in endings:
        raise ValueError("不支持的换行符")
    data += endings[newline]
    if not data:
        raise ValueError("请输入要发送的数据")
    if len(data) > 65507:
        raise ValueError("单次发送不能超过 65507 字节")
    return data
