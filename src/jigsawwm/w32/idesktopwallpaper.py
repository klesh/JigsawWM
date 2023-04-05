import enum
from ctypes import HRESULT, POINTER, pointer
from ctypes.wintypes import *
from typing import Optional

import comtypes
from comtypes import COMMETHOD, GUID, IUnknown


class DESKTOP_WALLPAPER_POSITION(enum.IntEnum):
    DWPOS_CENTER = 0
    DWPOS_TILE = 1
    DWPOS_STRETCH = 2
    DWPOS_FIT = 3
    DWPOS_FILL = 4
    DWPOS_SPAN = 5


# from https://stackoverflow.com/a/74203777/20763223
# noinspection PyPep8Naming
class IDesktopWallpaper(IUnknown):
    # Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-idesktopwallpaper

    # Search `IDesktopWallpaper` in `\HKEY_CLASSES_ROOT\Interface` to obtain the magic string
    _iid_ = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")

    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "SetWallpaper",
            (["in"], LPCWSTR, "monitorID"),
            (["in"], LPCWSTR, "wallpaper"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetWallpaper",
            (["in"], LPCWSTR, "monitorID"),
            (["out"], POINTER(LPWSTR), "wallpaper"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetMonitorDevicePathAt",
            (["in"], UINT, "monitorIndex"),
            (["out"], POINTER(LPWSTR), "monitorID"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetMonitorDevicePathCount",
            (["out"], POINTER(UINT), "count"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetMonitorRECT",
            (["in"], LPCWSTR, "monitorID"),
            (["out"], POINTER(RECT), "displayRect"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetBackgroundColor",
            (["in"], COLORREF, "color"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetBackgroundColor",
            (["OUT"], POINTER(COLORREF), "color"),
        ),
    ]

    def SetWallpaper(self, monitor_path: str, wallpaper: str):
        self.__com_SetWallpaper(LPCWSTR(monitor_path), LPCWSTR(wallpaper))

    def GetWallpaper(self, monitorId: Optional[str] = None) -> str:
        """Retrieves wallpaper image path 

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getwallpaper

        :param str monitor_path: optional, the string returned by GetMonitorDevicePathAt, return desktop wallpaper if omitted
        :returns: wallpaper image path
        :rtype: str
        """
        wallpaper = LPWSTR()
        self.__com_GetWallpaper(LPCWSTR(monitorId), pointer(wallpaper))
        return wallpaper.value

    def GetMonitorDevicePathAt(self, monitor_index: int) -> str:
        """Retrieves the unique ID of one of the system's monitors.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getmonitordevicepathat
        :param int monitor_index: monitor index
        :returns: monitor path
        :rtype: str
        """
        monitorId = LPWSTR()
        self.__com_GetMonitorDevicePathAt(UINT(monitor_index), pointer(monitorId))
        return monitorId.value

    def GetMonitorDevicePathCount(self) -> int:
        """Retrieves the number of monitors that are associated with the system.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getmonitordevicepathcount

        :returns: total number of available monitor (mirrored monitors excluded)
        """
        count = UINT()
        self.__com_GetMonitorDevicePathCount(pointer(count))
        return count.value

    def GetMonitorRECT(self, monitor_path: str) -> RECT:
        """Retrieves the display rectangle of the specified monitor.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getmonitorrect

        :param str monitor_path: monitor path returned by GetMonitorDevicePathAt
        :returns: display rectangle
        :rtype: RECT
        """
        rect = RECT()
        self.__com_GetMonitorRECT(LPCWSTR(monitor_path), pointer(rect))
        return rect

    def SetBackgroundColor(self, color: COLORREF):
        """Sets the background color
        
        :param COLORREF color:  background color
        """
        self.__com_SetBackgroundColor(color)

    def GetBackgroundColor(self) -> COLORREF:
        """Retrieves current background color
        
        :returns: current desktop background color
        :rtype: COLORREF
        """
        color = COLORREF()
        self.__com_GetBackgroundColor(pointer(color))
        return color


# Search `Desktop Wallpaper` in `\HKEY_CLASSES_ROOT\CLSID` to obtain the magic string
desktop_wallpaper: IDesktopWallpaper = comtypes.CoCreateInstance(
    GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}"), interface=IDesktopWallpaper
)


def hexstr2colorref(hexstr: str) -> COLORREF:
    """Converts html color to Win32 COLORREF struct
    
    :param str hexstr: html color string
    :returns: Win32 color struct
    :rtype: COLORREF
    """
    color = int(hexstr[1:], 16)
    return COLORREF(color & 0xFF00 | (color >> 16 & 0xFF) | ((color & 0xFF) << 16))


def colorref2hexstr(color: COLORREF) -> str:
    """Converts Win32 COLORREF struct to html color

    :param COLORREF color: Win32 color struct
    :returns: html color string
    :rtype: str
    """
    color = int(color.value)
    return "#%x%x%x" % (color & 0xFF, color >> 8 & 0xFF, color >> 16 & 0xFF)


if __name__ == "__main__":
    # set_wallpaper(r"D:\Documents\wallpapers\IMG_20220806_151544.jpg")
    # set_wallpaper("")
    # print(get_wallpaper())
    # print(monitor0_path)
    # monitor0_path = desktop_wallpaper.GetMonitorDevicePathAt(0)
    # monitor0_rect = desktop_wallpaper.GetMonitorRECT(monitor0_path)
    # print(
    #     monitor0_path,
    #     monitor0_rect.left,
    #     monitor0_rect.top,
    #     monitor0_rect.right,
    #     monitor0_rect.bottom,
    # )

    hexstr = "#121314"
    colorref = hexstr2colorref(hexstr)
    print("hexstr", hexstr)
    print("colorref: %x" % colorref.value)
    print("backto hexstr: %s" % colorref2hexstr(colorref))
