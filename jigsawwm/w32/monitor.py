from ctypes import *
from ctypes.wintypes import *
from typing import List, Iterator, Optional
import enum

user32 = WinDLL("user32", use_last_error=True)
shcore = WinDLL("shcore", use_last_error=True)
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


def set_cursor_pos(x: int, y: int):
    """Moves the cursor to the specified screen coordinates

    :param x: int
    :param y: int
    """
    if not user32.SetCursorPos(int(x), int(y)):
        raise Exception("failed to set cursor position")


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


class DEVICE_SCALE_FACTOR(enum.IntEnum):
    DEVICE_SCALE_FACTOR_INVALID = 0
    SCALE_100_PERCENT = 100
    SCALE_120_PERCENT = 120
    SCALE_125_PERCENT = 125
    SCALE_140_PERCENT = 140
    SCALE_150_PERCENT = 150
    SCALE_160_PERCENT = 160
    SCALE_175_PERCENT = 175
    SCALE_180_PERCENT = 180
    SCALE_200_PERCENT = 200
    SCALE_225_PERCENT = 225
    SCALE_250_PERCENT = 250
    SCALE_300_PERCENT = 300
    SCALE_350_PERCENT = 350
    SCALE_400_PERCENT = 400
    SCALE_450_PERCENT = 450
    SCALE_500_PERCENT = 500


class Monitor:
    """Represents a Display Monitor

    :param hmon: HMONITOR the monitor handle
    """

    _hmon: HMONITOR

    def __init__(self, hmon: HMONITOR):
        self._hmon = hmon

    def __eq__(self, other):
        return isinstance(other, Monitor) and self._hmon == other._hmon

    def __hash__(self):
        return hash(self._hmon)

    def get_info(self) -> MONITORINFO:
        monitor_info = MONITORINFO()
        monitor_info.cbSize = sizeof(monitor_info)
        if not user32.GetMonitorInfoA(self._hmon, pointer(monitor_info)):
            raise WinError(get_last_error())
        return monitor_info

    def get_scale_factor(self) -> DEVICE_SCALE_FACTOR:
        scale_factor = ULONG()
        if shcore.GetScaleFactorForMonitor(self._hmon, byref(scale_factor)) != 0:
            raise WinError(get_last_error())
        return DEVICE_SCALE_FACTOR(scale_factor.value)


def get_monitors() -> Iterator[Monitor]:
    return map(Monitor, enum_display_monitors())


def get_monitor_from_point(x: int, y: int) -> Monitor:
    return Monitor(monitor_from_point(x, y))


def get_monitor_from_cursor() -> Monitor:
    pt = get_cursor_pos()
    return Monitor(monitor_from_point(pt.x, pt.y))


def get_monitor_from_window(hwnd: HWND) -> Monitor:
    return Monitor(monitor_from_window(hwnd))


if __name__ == "__main__":
    for monitor in get_monitors():
        print("scale factor     :", monitor.get_scale_factor())
        monitor_info = monitor.get_info()
        m = monitor_info.rcMonitor
        print("monitor rect     :", m.left, m.top, m.right, m.bottom)
        m = monitor_info.rcWork
        print("monitor workarea :", m.left, m.top, m.right, m.bottom)
