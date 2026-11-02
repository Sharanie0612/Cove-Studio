import argparse
from pathlib import Path
import sys
import os

from toolbench.host import Host, ROOT
from toolbench.desktop import bind_window_frame, window_frame_options
from toolbench.bridge import DesktopBridge
from toolbench.identity import PRODUCT_NAME


def main():
    from toolbench.maintenance import installation_in_progress
    if installation_in_progress():
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, 'Cove 安装器正在运行。请完成或取消安装后，再重新打开 Cove。', 'Cove', 0x40)
        sys.exit(1618)
    if getattr(sys, 'frozen', False):
        from toolbench.paths import installation_root, active_runtime
        current = active_runtime(installation_root())
        if current and current != Path(sys.executable).resolve().parent:
            import subprocess
            subprocess.Popen([str(current / 'Cove.exe'), *sys.argv[1:]], cwd=current)
            return
    parser = argparse.ArgumentParser(description="Cove 桌面工具工作台")
    parser.add_argument("--dev", action="store_true", help="使用 Vite 开发服务器")
    parser.add_argument("--debug", action="store_true", help="开启开发者工具")
    parser.add_argument("--port", type=int, default=18274)
    args = parser.parse_args()
    page = ROOT / "dist" / "index.html"
    if not args.dev and not page.exists():
        sys.exit("请先运行 npm install 和 npm run build，再启动桌面版。")
    import webview
    from toolbench.storage import StorageBusy
    try:
        host = Host()
    except StorageBusy:
        from toolbench.native_messages import t, show_notice
        show_notice(t('旧数据目录仍在使用。请先正常退出相关 Cove 窗口和插件任务，再重新打开以迁移数据。'))
        return
    # Scope temporary/cache paths to this process; never change Windows settings.
    from toolbench.plugin_framework.environment import worker_environment
    import tempfile
    environment = worker_environment(host.data_dir)
    for key in ('TEMP', 'TMP', 'TMPDIR', 'XDG_CACHE_HOME', 'PIP_CACHE_DIR', 'PYTHONDONTWRITEBYTECODE'):
        os.environ[key] = environment[key]
    tempfile.tempdir = environment['TMP']
    window = webview.create_window(
        PRODUCT_NAME, "http://127.0.0.1:5173" if args.dev else str(page),
        js_api=DesktopBridge(host), width=1380, height=900, min_size=(960, 660),
        text_select=True, frameless=True, easy_drag=False, **window_frame_options())
    host._window = window
    host._maximized = False
    def closing():
        if host._work_summary()['activePlugins'] and not getattr(host, "_closing_confirmed", False):
            # Closing runs on the UI thread; dispatch asynchronously so JS can respond.
            import threading
            def request_close():
                try:
                    window.evaluate_js("window.dispatchEvent(new Event('cove-close-request'))")
                except Exception:
                    pass
            threading.Thread(target=request_close, daemon=True).start()
            return False
        return True
    window.events.closing += closing
    bind_window_frame(window, host)
    # Cove hands a single gesture to native capture; disable pywebview's JS
    # mousemove-based mover to avoid two competing position controllers.
    webview.settings["DRAG_REGION_SELECTOR"] = ".cove-unused-drag-region"
    window.events.closed += host.close
    try:
        webview.start(debug=args.debug, private_mode=False,
                      storage_path=str(host.data_dir / "webview"), http_port=args.port,
                      icon=str(ROOT / "assets/cove.ico"))
    finally:
        host.close()


if __name__ == "__main__":
    main()
