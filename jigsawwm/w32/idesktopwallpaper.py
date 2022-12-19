from typing import Optional
from ctypes import HRESULT, POINTER, pointer
from ctypes.wintypes import LPCWSTR, UINT, LPWSTR, RECT

import comtypes
from comtypes import IUnknown, GUID, COMMETHOD


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
    ]

    def SetWallpaper(self, monitorId: str, wallpaper: str):
        self.__com_SetWallpaper(LPCWSTR(monitorId), LPCWSTR(wallpaper))

    def GetWallpaper(self, monitorId: Optional[str] = None) -> str:
        """Gets the current desktop wallpaper.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getwallpaper
        """
        wallpaper = LPWSTR()
        self.__com_GetWallpaper(LPCWSTR(monitorId), pointer(wallpaper))
        return wallpaper.value

    def GetMonitorDevicePathAt(self, monitorIndex: int) -> str:
        """Retrieves the unique ID of one of the system's monitors.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getmonitordevicepathat
        """
        monitorId = LPWSTR()
        self.__com_GetMonitorDevicePathAt(UINT(monitorIndex), pointer(monitorId))
        return monitorId.value

    def GetMonitorDevicePathCount(self) -> int:
        """Retrieves the number of monitors that are associated with the system.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getmonitordevicepathcount
        """
        count = UINT()
        self.__com_GetMonitorDevicePathCount(pointer(count))
        return count.value

    def GetMonitorRECT(self, monitorId: str) -> RECT:
        """Retrieves the display rectangle of the specified monitor.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-idesktopwallpaper-getmonitorrect
        """
        rect = RECT()
        self.__com_GetMonitorRECT(LPCWSTR(monitorId), pointer(rect))
        return rect


# Search `Desktop Wallpaper` in `\HKEY_CLASSES_ROOT\CLSID` to obtain the magic string
desktop_wallpaper = comtypes.CoCreateInstance(
    GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}"), interface=IDesktopWallpaper
)


if __name__ == "__main__":
    # set_wallpaper(r"D:\Documents\wallpapers\IMG_20220806_151544.jpg")
    # set_wallpaper("")
    # print(get_wallpaper())
    monitor0_path = desktop_wallpaper.GetMonitorDevicePathAt(0)
    # print(monitor0_path)
    monitor0_rect = desktop_wallpaper.GetMonitorRECT(monitor0_path)
    print(
        monitor0_path,
        monitor0_rect.top,
        monitor0_rect.bottom,
        monitor0_rect.left,
        monitor0_rect.right,
    )
