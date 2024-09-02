"""Windows API for monitor management"""

import enum
import math
import sys
from ctypes import (
    WinDLL,
    WinError,
    pointer,
    get_last_error,
    WINFUNCTYPE,
    byref,
    Structure,
    sizeof,
)
from ctypes.wintypes import (
    POINT,
    HMONITOR,
    BOOL,
    HDC,
    LPRECT,
    LPARAM,
    HWND,
    ULONG,
    RECT,
    DWORD,
    CHAR,
)
from functools import cached_property
from typing import Tuple, Set
from dataclasses import dataclass
import screeninfo

from .window_structs import Rect

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
        raise WinError(get_last_error())
    return _current_pos_ptr


def set_cursor_pos(x: int, y: int):
    """Moves the cursor to the specified screen coordinates

    :param x: int
    :param y: int
    """
    if not user32.SetCursorPos(int(x), int(y)):
        raise WinError(get_last_error())


def enum_display_monitors() -> Set[HMONITOR]:
    """Returns a List of all monitors. THIS DO NOT RETURN MIRRORING MONITORS

    :return: list of monitor handles
    :rtype: List[]
    """
    hmons = set()

    @WINFUNCTYPE(BOOL, HMONITOR, HDC, LPRECT, LPARAM)
    def monitor_enum_proc(
        hmon: HMONITOR,
        _hdc: HDC,
        _lprc: LPRECT,
        _lparam: LPARAM,
    ) -> BOOL:
        hmons.add(hmon)
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


def monitor_from_cursor() -> HMONITOR:
    """Retrieves monitor from current cursor

    :returns: monitor handle
    :rtype: HMONITOR
    """
    pt = get_cursor_pos()
    return monitor_from_point(pt.x, pt.y)


CCHDEVICENAME = 32


class MONITORINFOEX(Structure):
    """Contains information about a display monitor"""

    cbSize: int
    rcMonitor: RECT
    rcWork: RECT
    dwFlags: int
    szDevice: CHAR

    _fields_ = (
        ("cbSize", DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", DWORD),
        ("szDevice", CHAR * CCHDEVICENAME),
    )


class DeviceScaleFactor(enum.IntEnum):
    """Device scale factor enum"""

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


@dataclass
class ScreenInfo:
    """Screen Information"""

    width_px: int
    height_px: int
    width_mm: int
    height_mm: int
    ratio: float
    is_primary: bool
    inch: int


class Monitor:
    """Represents a Display Monitor

    :param hmon: HMONITOR the monitor handle
    """

    handle: HMONITOR

    def __init__(self, hmon: HMONITOR):
        self.handle = hmon

    def __eq__(self, other):
        return isinstance(other, Monitor) and self.handle == other.handle

    def __hash__(self):
        return hash(self.handle)

    def __repr__(self):
        info = self.get_info()
        if info is None:
            return f"<Monitor: {self.name} {self.handle} gone>"
        rect = info.rcMonitor
        return f"<Monitor: {self.name} {self.handle} {rect.left} {rect.top} {rect.right-rect.left} {rect.bottom-rect.top} {self.get_scale_factor()/100}>"

    @cached_property
    def name(self) -> str:
        """Retrieves monitor name"""
        return self.get_info().szDevice.decode("utf-8")

    def get_rect(self) -> Rect:
        """Retrieves monitor rectangle

        :returns: monitor rectangle
        :rtype: Rect
        """
        return Rect.from_win_rect(self.get_info().rcMonitor)

    def get_work_rect(self) -> Rect:
        """Retrieves monitor rectangle

        :returns: monitor rectangle
        :rtype: Rect
        """
        return Rect.from_win_rect(self.get_info().rcWork)

    def get_info(self) -> MONITORINFOEX:
        """Retrieves monitor information

        :returns: monitor information
        :rtype: MONITORINFOEX
        """
        monitor_info = MONITORINFOEX()
        monitor_info.cbSize = sizeof(monitor_info)  # pylint: disable=invalid-name
        if not user32.GetMonitorInfoA(self.handle, pointer(monitor_info)):
            return None
        return monitor_info

    def get_scale_factor(self) -> DeviceScaleFactor:
        """Retrieves monitor scale factor

        :returns: scale factor
        :rtype: DEVICE_SCALE_FACTOR
        """
        scale_factor = ULONG()
        if shcore.GetScaleFactorForMonitor(self.handle, byref(scale_factor)) != 0:
            raise WinError(get_last_error())
        return DeviceScaleFactor(scale_factor.value)

    def get_screen_info(self) -> ScreenInfo:
        """Retrieves screen information"""
        for monitor in screeninfo.get_monitors():
            if monitor.name == self.name:
                return ScreenInfo(
                    monitor.width,
                    monitor.height,
                    monitor.width_mm,
                    monitor.height_mm,
                    ratio=max(monitor.width, monitor.height)
                    / min(monitor.width, monitor.height),
                    is_primary=monitor.is_primary,
                    inch=round(
                        math.sqrt(monitor.width_mm**2 + monitor.height_mm**2) / 25.4
                    ),
                )

    def get_monitor_central(self) -> Tuple[int, int]:
        """Retrieves coordinates of the center of specified monitor"""
        rect = self.get_info().rcMonitor
        return (
            rect.left + (rect.right - rect.left) / 2,
            rect.top + (rect.bottom - rect.top) / 2,
        )

    def inspect(self, file=sys.stdout):
        """Prints monitor information and cursor position"""
        print(file=file)
        print(self, file=file)
        print("scale factor     :", self.get_scale_factor())
        monitor_info = self.get_info()
        print("device           :", monitor_info.szDevice, file=file)
        print("screen info      :", self.get_screen_info(), file=file)
        m = monitor_info.rcWork
        print(
            f"monitor workarea : left {m.left} top {m.top}  right {m.right}  bottom {m.bottom}",
            file=file,
        )
        m = monitor_info.rcMonitor
        print(
            f"monitor react    : left {m.left} top {m.top}  right {m.right}  bottom {m.bottom}",
            file=file,
        )


def inspect_monitors():
    """Prints monitor information and cursor position"""
    p = get_cursor_pos()
    print(f"cursor pos       :  x {p.x} y {p.y}")
    for monitor in map(Monitor, enum_display_monitors()):
        monitor.inspect()


if __name__ == "__main__":
    inspect_monitors()
