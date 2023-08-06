import enum
from ctypes import *
from ctypes.wintypes import *
from functools import cached_property
from typing import Iterator, List, Tuple

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
    """Returns a List of all monitors. THIS DO NOT RETURN MIRRORING MONITORS

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
    """Retrieves monitor from the specified coordinate

    :param int x: X
    :param int y: Y
    :returns: monitor handle
    :rtype: HMONITOR
    """
    return user32.MonitorFromPoint(POINT(x=x, y=y), 0)


def monitor_from_window(hwnd: HWND) -> HMONITOR:
    """Retrieves monitor from the specified window

    :param HWND hwn: window handle
    :returns: monitor handle
    :rtype: HMONITOR
    """
    return user32.MonitorFromWindow(hwnd, 0)


CCHDEVICENAME = 32


class MONITORINFOEX(Structure):
    cbSize: int
    rcMonitor: RECT
    rcWork: RECT
    dwFlags: int
    szDevice: CHAR * CCHDEVICENAME

    _fields_ = (
        ("cbSize", DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", DWORD),
        ("szDevice", CHAR * CCHDEVICENAME),
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

    def __repr__(self):
        return f"<Monitor: {self.name} {self.get_rect()} {self.get_scale_factor()}>"

    @cached_property
    def name(self) -> str:
        return self.get_info().szDevice.decode("utf-8")

    def get_rect(self) -> RECT:
        """Retrieves monitor rectangle

        :returns: monitor rectangle
        :rtype: RECT
        """
        return self.get_info().rcMonitor

    def get_info(self) -> MONITORINFOEX:
        """Retrieves monitor information

        :returns: monitor information
        :rtype: MONITORINFOEX
        """
        monitor_info = MONITORINFOEX()
        monitor_info.cbSize = sizeof(monitor_info)
        if not user32.GetMonitorInfoA(self._hmon, pointer(monitor_info)):
            raise WinError(get_last_error())
        return monitor_info

    def get_scale_factor(self) -> DEVICE_SCALE_FACTOR:
        """Retrieves monitor scale factor

        :returns: scale factor
        :rtype: DEVICE_SCALE_FACTOR
        """
        scale_factor = ULONG()
        if shcore.GetScaleFactorForMonitor(self._hmon, byref(scale_factor)) != 0:
            raise WinError(get_last_error())
        return DEVICE_SCALE_FACTOR(scale_factor.value)


def get_monitors() -> Iterator[Monitor]:
    """Retrieves all display monitors(mirroring monitors are excluded)

    :returns: system monitors
    :rtype: Iterator[Monitor]
    """
    return map(Monitor, enum_display_monitors())


def get_monitor_central(monitor: Monitor) -> Tuple[int, int]:
    """Retrieves coordinates of the center of specified monitor

    :param Monitor monitor: monitor
    :returns: X/Y coorindates
    :rtype: Tuple[int, int]
    """
    rect = monitor.get_info().rcMonitor
    return (
        rect.left + (rect.right - rect.left) / 2,
        rect.top + (rect.bottom - rect.top) / 2,
    )


def get_topo_sorted_monitors() -> List[Monitor]:
    """Sort monitor from left to right, top to bottom by Central Points

    :returns: list of monitors ordered by their central point, X and then Y
    :rtype: List[Monitor]
    """
    return sorted(get_monitors(), key=get_monitor_central)


def get_monitor_from_point(x: int, y: int) -> Monitor:
    """Retrieves monitor from X/Y coordinates

    :param int x: X coordinate
    :param int y: Y coordinate
    :returns: Monitor from specified point
    :rtype: Monitor
    """
    return Monitor(monitor_from_point(x, y))


def get_monitor_from_cursor() -> Monitor:
    """Retrieves monitor from cursor

    :returns: Monitor from current cursor
    :rtype: Monitor
    """
    pt = get_cursor_pos()
    return Monitor(monitor_from_point(pt.x, pt.y))


def get_monitor_from_window(hwnd: HWND) -> Monitor:
    """Retrieves monitor from window handle

    :param HWND hwnd: window handle
    :returns: Monitor that owns specified window
    :rtype: Monitor
    """
    if hwnd:
        return Monitor(monitor_from_window(hwnd))


if __name__ == "__main__":
    p = get_cursor_pos()
    print(f"cursor pos       :  x {p.x} y {p.y}")
    for monitor in get_topo_sorted_monitors():
        print()
        print("scale factor     :", monitor.get_scale_factor())
        monitor_info = monitor.get_info()
        print("device           :", monitor_info.szDevice)
        m = monitor_info.rcWork
        print(
            f"monitor workarea : left {m.left} top {m.top}  right {m.right}  bottom {m.bottom}"
        )
        m = monitor_info.rcMonitor
        print(
            f"monitor react    : left {m.left} top {m.top}  right {m.right}  bottom {m.bottom}"
        )
