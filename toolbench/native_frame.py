"""Native sizing/Snap semantics behind Cove's custom Windows chrome."""
import ctypes
from ctypes import wintypes
import logging


def install_sizing_frame(window):
    """Keep the system sizing frame while making the entire surface client area.

    https://learn.microsoft.com/windows/win32/dwm/customframe
    Called on the WinForms UI thread after its HWND has been created.
    """
    if getattr(window, '_cove_native_frame', None):
        return
    user = ctypes.WinDLL('user32', use_last_error=True)
    handle = int(window.native.Handle.ToInt64())
    result_type = ctypes.c_ssize_t
    proc_type = ctypes.WINFUNCTYPE(result_type, wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM)
    get_long = user.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.GetWindowLongW
    set_long = user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.SetWindowLongW
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_long.restype = result_type
    set_long.argtypes = [wintypes.HWND, ctypes.c_int, result_type]
    set_long.restype = result_type
    user.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                   wintypes.WPARAM, wintypes.LPARAM]
    user.CallWindowProcW.restype = result_type
    user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user.MonitorFromWindow.restype = wintypes.HANDLE

    class MonitorInfo(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                    ('work', wintypes.RECT), ('flags', wintypes.DWORD)]

    class MinMaxInfo(ctypes.Structure):
        _fields_ = [('reserved', wintypes.POINT), ('maxSize', wintypes.POINT),
                    ('maxPosition', wintypes.POINT), ('minTrack', wintypes.POINT),
                    ('maxTrack', wintypes.POINT)]

    user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    user.IsZoomed.argtypes = [wintypes.HWND]
    previous = get_long(handle, -4)  # GWLP_WNDPROC

    @proc_type
    def window_proc(hwnd, message, wparam, lparam):
        if message == 0x83:  # WM_NCCALCSIZE: retain style semantics, hide system chrome
            if wparam and lparam and user.IsZoomed(hwnd):
                monitor = MonitorInfo()
                monitor.size = ctypes.sizeof(monitor)
                if user.GetMonitorInfoW(user.MonitorFromWindow(hwnd, 2), ctypes.byref(monitor)):
                    # Maximized sizing frames extend past the monitor by design.
                    # Keep that invisible frame, but put all client pixels inside
                    # the work area, including on monitors with negative coordinates.
                    client = ctypes.cast(lparam, ctypes.POINTER(wintypes.RECT)).contents
                    client.left, client.top = monitor.work.left, monitor.work.top
                    client.right, client.bottom = monitor.work.right, monitor.work.bottom
            return 0
        result = user.CallWindowProcW(previous, hwnd, message, wparam, lparam)
        if message in (0x47, 0x232) and getattr(window, '_cove_layout_changed', None):
            window._cove_layout_changed()  # WINDOWPOSCHANGED / EXITSIZEMOVE: Snap can stay Normal.
        if lparam and message == 0x24:
            try:
                monitor = MonitorInfo()
                monitor.size = ctypes.sizeof(monitor)
                if user.GetMonitorInfoW(user.MonitorFromWindow(hwnd, 2), ctypes.byref(monitor)):
                    width = monitor.work.right - monitor.work.left
                    height = monitor.work.bottom - monitor.work.top
                    info = ctypes.cast(lparam, ctypes.POINTER(MinMaxInfo)).contents
                    info.maxPosition.x = monitor.work.left - monitor.monitor.left
                    info.maxPosition.y = monitor.work.top - monitor.monitor.top
                    info.maxSize.x, info.maxSize.y = width, height
            except Exception:
                logging.getLogger(__name__).exception('Unable to set native maximize bounds')
        return result

    # Keep the callback alive for the HWND lifetime, including its destroy messages.
    window._cove_native_frame = (window_proc, previous, user)
    ctypes.set_last_error(0)
    set_long(handle, -4, ctypes.cast(window_proc, ctypes.c_void_p).value)
    if ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    # FormBorderStyle.None otherwise removes the eligibility flags Windows Snap
    # requires. WM_NCCALCSIZE above prevents a second visible title bar.
    style = get_long(handle, -16)
    set_long(handle, -16, style | 0x00CF0000)  # WS_OVERLAPPEDWINDOW
    user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user.SetWindowPos(handle, None, 0, 0, 0, 0, 0x37)  # FRAMECHANGED, no move/size/activate/z-order
