import os
import sys
import logging


def uses_alpha_frame():
    """Windows 10 needs a composited surface; Windows 11 has native AA corners."""
    return os.name == 'nt' and sys.getwindowsversion().build < 22000


def window_frame_options():
    alpha = uses_alpha_frame()
    return {'transparent': alpha, 'shadow': not alpha,
            'background_color': '#000000' if alpha else '#f6f7f9'}


def set_maximized_bounds(native):
    from System.Windows.Forms import Screen
    native.MaximizedBounds = Screen.FromHandle(native.Handle).WorkingArea


class DesktopApi:
    def set_locale(self, locale):
        if locale not in ('zh-CN', 'en-US'):
            return {'ok': False, 'error': 'Unsupported interface language'}
        labels = {
            'zh-CN': ('确定', '退出', '取消', '保存文件', '所有文件', '其他文件类型'),
            'en-US': ('OK', 'Quit', 'Cancel', 'Save file', 'All files', 'Other file types'),
        }
        keys = ('global.ok', 'global.quit', 'global.cancel', 'global.saveFile',
                'windows.fileFilter.allFiles', 'windows.fileFilter.otherFiles')
        window = getattr(self, '_window', None)
        if window is not None and isinstance(getattr(window, 'localization', None), dict):
            window.localization.update(zip(keys, labels[locale]))
        self._ui_locale = locale
        return {'ok': True, 'result': {'locale': locale}}

    def _native_system_interaction(self, command):
        """Start the system move/size loop on its owning UI thread."""
        from System import Action
        import ctypes
        from ctypes import wintypes
        native = self._window.native
        def begin():
            user = ctypes.windll.user32
            user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user.GetAsyncKeyState.argtypes = [ctypes.c_int]
            user.GetAsyncKeyState.restype = ctypes.c_short
            # A delayed bridge request must never leave a window stuck to the mouse.
            if not user.GetAsyncKeyState(1) & 0x8000:
                return
            position = wintypes.POINT()
            user.GetCursorPos(ctypes.byref(position))
            user.ReleaseCapture()
            packed = (position.x & 0xffff) | ((position.y & 0xffff) << 16)
            user.PostMessageW(int(native.Handle.ToInt64()), 0x112, command, packed)
        native.BeginInvoke(Action(begin))

    def _native_drag(self):
        DesktopApi._native_system_interaction(self, 0xF012)  # SC_MOVE | HTCAPTION (fallback only).

    def resize_window(self, edge: str):
        try:
            edges = {"w": 1, "e": 2, "n": 3, "nw": 4, "ne": 5, "s": 6, "sw": 7, "se": 8}
            if os.name != "nt" or edge not in edges or getattr(self, "_maximized", False):
                return {"ok": True}
            self._native_system_interaction(0xF000 | edges[edge])
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def window_action(self, action: str, confirmed: bool = False):
        try:
            window = getattr(self, "_window", None)
            if not window:
                raise ValueError("窗口控制仅在桌面版可用")
            if action == "minimize":
                window.minimize()
            elif action == 'drag':
                if os.name == 'nt':
                    self._native_drag()
            elif action == "maximize":
                if os.name == 'nt' and getattr(window, 'native', None) is not None:
                    from System import Action
                    from System.Windows.Forms import FormWindowState
                    def toggle():
                        native = window.native
                        set_maximized_bounds(native)
                        native.WindowState = FormWindowState.Normal if native.WindowState == FormWindowState.Maximized else FormWindowState.Maximized
                        self._maximized = native.WindowState == FormWindowState.Maximized
                    window.native.Invoke(Action(toggle))
                    return {"ok": True, "result": {"maximized": self._maximized}}
                if getattr(self, "_maximized", False):
                    window.restore()
                    self._maximized = False
                else:
                    window.maximize()
                    self._maximized = True
            elif action == "close":
                work = self._work_summary()
                if work['activePlugins'] and not confirmed:
                    return {"ok": True, "result": {"needsConfirmation": True, **work}}
                self.close()
                self._closing_confirmed = True
                window.destroy()
            else:
                raise ValueError("不支持的窗口操作")
            return {"ok": True, "result": {"maximized": getattr(self, "_maximized", False)}}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def configure_native_frame(window):
    """Configure once on the WinForms UI thread, before the first visible frame.

    SetWindowRgn is a binary mask, so it must never draw the visible curve.
    Win11 lets DWM own it; Win10 composites Chromium's antialiased CSS curve.
    """
    if os.name != "nt" or window.native is None:
        return 'opaque'
    import ctypes
    from ctypes import wintypes
    native = window.native
    from .native_frame import install_sizing_frame
    install_sizing_frame(window)
    set_maximized_bounds(native)
    handle = int(native.Handle.ToInt64())
    user = ctypes.windll.user32
    gdi = ctypes.windll.gdi32
    user.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
    user.SetWindowRgn(handle, None, False)
    dwm = ctypes.windll.dwmapi
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwm.DwmSetWindowAttribute.restype = ctypes.c_long
    if not uses_alpha_frame():
        # Keep the native shadow, but suppress the contrasting non-client border.
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        border = wintypes.DWORD(0xFFFFFFFE)  # DWMWA_COLOR_NONE
        rounded = dwm.DwmSetWindowAttribute(handle, 33, ctypes.byref(preference), ctypes.sizeof(preference))
        dwm.DwmSetWindowAttribute(handle, 34, ctypes.byref(border), ctypes.sizeof(border))
        window._cove_frame = 'native' if rounded == 0 else 'opaque'
        return window._cove_frame

    class BlurBehind(ctypes.Structure):
        _fields_ = [('flags', wintypes.DWORD), ('enable', wintypes.BOOL),
                    ('region', wintypes.HRGN), ('transition', wintypes.BOOL)]

    class Margins(ctypes.Structure):
        _fields_ = [('left', ctypes.c_int), ('right', ctypes.c_int),
                    ('top', ctypes.c_int), ('bottom', ctypes.c_int)]

    # Black GDI pixels have zero alpha. The WebView supplies the opaque body and
    # fractional-alpha edge; no colour-keying, layered bitmap copy or resize mask.
    from System.Drawing import Color
    native.BackColor = Color.Black
    native.webview.DefaultBackgroundColor = Color.Transparent
    dwm.DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, ctypes.POINTER(Margins)]
    dwm.DwmExtendFrameIntoClientArea(handle, ctypes.byref(Margins(0, 0, 0, 0)))
    gdi.CreateRectRgn.argtypes = [ctypes.c_int] * 4
    gdi.CreateRectRgn.restype = wintypes.HRGN
    gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    dwm.DwmEnableBlurBehindWindow.argtypes = [wintypes.HWND, ctypes.POINTER(BlurBehind)]
    dwm.DwmEnableBlurBehindWindow.restype = ctypes.c_long
    # An empty blur region enables per-pixel compositing without blurring tools.
    region = gdi.CreateRectRgn(0, 0, -1, -1)
    try:
        result = dwm.DwmEnableBlurBehindWindow(handle, ctypes.byref(BlurBehind(3, True, region, False)))
    finally:
        gdi.DeleteObject(region)
    window._cove_frame = 'alpha' if result == 0 else 'opaque'
    if result != 0:
        logging.getLogger(__name__).warning('DWM alpha composition unavailable: %s', result)
        native.BackColor = Color.FromArgb(246, 247, 249)
    return window._cove_frame


def sync_window_frame(window, host, force=False):
    """Sync only state transitions, not every resize pixel or plugin refresh."""
    maximized = bool(host._maximized)
    frame = getattr(window, '_cove_frame', 'opaque')
    snapped = getattr(host, '_snapped', False)
    native_drag = getattr(window, '_cove_native_drag', False)
    state = (frame, maximized, snapped, native_drag)
    if not force and getattr(window, '_cove_frame_state', None) == state:
        return
    script = (f"document.documentElement.dataset.windowFrame='{frame}';"
              f"document.documentElement.dataset.windowSnapped='{str(snapped).lower()}';"
              f"document.documentElement.dataset.windowDrag='{'native' if native_drag else 'bridge'}';"
              f"document.documentElement.dataset.windowMaximized='{str(maximized).lower()}';"
              f"window.dispatchEvent(new CustomEvent('cove-window-state',{{detail:{{maximized:{str(maximized).lower()}}}}}));")
    # NavigationCompleted/before_load runs on the UI thread. Never wait for an
    # ExecuteScriptAsync continuation there: that would deadlock the first load.
    from System import Action
    native = window.native
    if frame == 'native':
        import ctypes
        preference = ctypes.c_int(1 if snapped or maximized else 2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(native.Handle.ToInt64()), 33,
                                                  ctypes.byref(preference), ctypes.sizeof(preference))
    apply = lambda: native.webview.ExecuteScriptAsync(script)
    if native.InvokeRequired:
        native.BeginInvoke(Action(apply))
    else:
        apply()
    window._cove_frame_state = state


def bind_window_frame(window, host):
    if os.name != 'nt':
        window.events.maximized += lambda: setattr(host, '_maximized', True)
        window.events.restored += lambda: setattr(host, '_maximized', False)
        return
    def configure():
        configure_native_frame(window)
        from System.Windows.Forms import FormWindowState
        from System import Action
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL('user32')
        arranged = getattr(user, 'IsWindowArranged', None)
        if arranged:
            arranged.argtypes = [wintypes.HWND]
            arranged.restype = wintypes.BOOL
        # WinForms events run on the UI thread; pywebview events use independent
        # threads and can arrive out of order during rapid maximize/restore.
        def update():
            window._cove_sync_pending = False
            native = window.native
            if not native.IsDisposed and native.WindowState != FormWindowState.Minimized:
                host._maximized = native.WindowState == FormWindowState.Maximized
                host._snapped = bool(arranged(int(native.Handle.ToInt64()))) if arranged else False
                if window.events.loaded.is_set(): sync_window_frame(window, host)
        def resized(*_):
            if not getattr(window, '_cove_sync_pending', False) and not window.native.IsDisposed:
                window._cove_sync_pending = True
                window.native.BeginInvoke(Action(update))
        window._cove_layout_changed = resized
        window.native.Resize += resized
        window.native.LocationChanged += resized
        def initialized(sender, args):
            if args.IsSuccess:
                try:
                    window.native.webview.CoreWebView2.Settings.IsNonClientRegionSupportEnabled = True
                    window._cove_native_drag = True
                except Exception:
                    logging.getLogger(__name__).warning('Native WebView title regions unavailable; using system-command fallback')
                resized()
        window.native.webview.CoreWebView2InitializationCompleted += initialized
    window.events.before_show += configure
    window.events.before_load += lambda: sync_window_frame(window, host, force=True)
    window.events.loaded += lambda: sync_window_frame(window, host, force=True)
