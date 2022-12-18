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
    _iid_ = GUID('{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}')

    _methods_ = [
        COMMETHOD(
            [], HRESULT, 'SetWallpaper',
            (['in'], LPCWSTR, 'monitorID'),
            (['in'], LPCWSTR, 'wallpaper'),
        ),
        COMMETHOD(
            [], HRESULT, 'GetWallpaper',
            (['in'], LPCWSTR, 'monitorID'),
            (['out'], POINTER(LPWSTR), 'wallpaper'),
        ),
        COMMETHOD(
            [], HRESULT, 'GetMonitorDevicePathAt',
            (['in'], UINT, 'monitorIndex'),
            (['out'], POINTER(LPWSTR), 'monitorID'),
        ),
        COMMETHOD(
            [], HRESULT, 'GetMonitorDevicePathCount',
            (['out'], POINTER(UINT), 'count'),
        ),
        COMMETHOD(
            [], HRESULT, 'GetMonitorRECT',
            (['in'], LPCWSTR, 'monitorID'),
            (['out'], POINTER(RECT), 'displayRect'),
        ),
    ]

    def SetWallpaper(self, monitorId: str, wallpaper: str):
        self.__com_SetWallpaper(LPCWSTR(monitorId), LPCWSTR(wallpaper))

    def GetWallpaper(self, monitorId: Optional[str] = None) -> str:
        wallpaper = LPWSTR()
        self.__com_GetWallpaper(LPCWSTR(monitorId), pointer(wallpaper))
        return wallpaper.value

    def GetMonitorDevicePathAt(self, monitorIndex: int) -> str:
        monitorId = LPWSTR()
        self.__com_GetMonitorDevicePathAt(UINT(monitorIndex), pointer(monitorId))
        return monitorId.value

    def GetMonitorDevicePathCount(self) -> int:
        count = UINT()
        self.__com_GetMonitorDevicePathCount(pointer(count))
        return count.value

    def GetMonitorRECT(self, monitorId: str) -> RECT:
        rect = RECT()
        self.__com_GetMonitorRECT(LPCWSTR(monitorId), pointer(rect))
        return rect

def NewDesktopWallpaperCom() -> IDesktopWallpaper:
    # Search `Desktop Wallpaper` in `\HKEY_CLASSES_ROOT\CLSID` to obtain the magic string
    class_id = GUID('{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}')
    return comtypes.CoCreateInstance(class_id, interface=IDesktopWallpaper)

def set_wallpaper(wallpaper_path: str, monitor_id: Optional[str] = None):
    desktop_wallpaper = NewDesktopWallpaperCom()
    desktop_wallpaper.SetWallpaper(monitor_id, wallpaper_path)

def get_wallpaper(monitor_id: Optional[str] = None) -> str:
    desktop_wallpaper = NewDesktopWallpaperCom()
    return desktop_wallpaper.GetWallpaper(monitor_id)


if __name__ == "__main__":
    print("hello")
    desktop_wallpaper = NewDesktopWallpaperCom()
    # desktop_wallpaper = IDesktopWallpaper.CoCreateInstance()
    # desktop_wallpaper.Enable(False)
    # desktop_wallpaper.SetWallpaper(0, r"D:\Documents\wallpapers\IMG_20220806_151544.jpg")
    # desktop_wallpaper.SetWallpaper(0, "")
    # print(desktop_wallpaper.GetWallpaper(None))
    monitor0_path = desktop_wallpaper.GetMonitorDevicePathAt(0)
    # print(monitor0_path)
    monitor0_rect = desktop_wallpaper.GetMonitorRECT(monitor0_path)
    print(monitor0_path, monitor0_rect.top, monitor0_rect.bottom, monitor0_rect.left, monitor0_rect.right)

