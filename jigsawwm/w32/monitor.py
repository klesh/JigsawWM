from ctypes import *
from ctypes.wintypes import *
from typing import List, Iterator, Optional


user32 = WinDLL("user32", use_last_error=True)
_current_pos_ptr = POINT()

# Ref: https://learn.microsoft.com/en-us/windows/win32/gdi/multiple-display-monitors-functions


def get_cursor_pos() -> POINT:
    """Retrieves the position of the mouse cursor, in screen coordinates.

    :return: mouse position
    :rtype: POINT
    """
    if not user32.GetCursorPos(pointer(_current_pos_ptr)):
        raise Exception("failed to get cursor position")
    return _current_pos_ptr


def enum_display_monitors() -> List[HMONITOR]:
    """Returns a List of all monitors.

    :return: list of monitor handles
    :rtype: List[]
    """
    hmons = []

    @WINFUNCTYPE(BOOL, HMONITOR, HDC, LPRECT, LPARAM)
    def monitor_enum_proc(
        hmon: HMONITOR, hdc: HDC, lprc: LPRECT, lParam: LPARAM
    ) -> BOOL:
        hmons.append(hmon)
        return True

    if not user32.EnumDisplayMonitors(None, None, monitor_enum_proc, None):
        raise WinError(get_last_error())
    return hmons


def monitor_from_point(x: int, y: int) -> HMONITOR:
    return user32.MonitorFromPoint(POINT(x=x, y=y), 0)


def monitor_from_window(hwnd: HWND) -> HMONITOR:
    return user32.MonitorFromWindow(hwnd, 0)


class MONITORINFO(Structure):
    cbSize: int
    rcMonitor: RECT
    rcWork: RECT
    dwFlags: int

    _fields_ = (
        ("cbSize", DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", DWORD),
    )


class Monitor:
    """Represents a Display Monitor

    :param hmon: HMONITOR the monitor handle
    """

    _hmon: HMONITOR

    def __init__(self, hmon: HMONITOR):
        self._hmon = hmon

    def __eq__(self, other):
        return isinstance(other, Monitor) and self._hmon == other._hmon

    def __hash_(self):
        return hash(self._hmon)

    def get_info(self) -> MONITORINFO:
        monitor_info = MONITORINFO()
        monitor_info.cbSize = sizeof(monitor_info)
        if not user32.GetMonitorInfoA(self._hmon, pointer(monitor_info)):
            raise WinError(get_last_error())
        return monitor_info


def get_monitors() -> Iterator[Monitor]:
    return map(Monitor, enum_display_monitors())


if __name__ == "__main__":
    for monitor in get_monitors():
        monitor_info = monitor.get_info()
        m = monitor_info.rcMonitor
        print(m.left, m.top, m.right, m.bottom)
        m = monitor_info.rcWork
        print(m.left, m.top, m.right, m.bottom)
