from typing import Optional
from ctypes import *
from ctypes.wintypes import *
from comtypes import *

# Ref: https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ivirtualdesktopmanager


def _check(hresult: HRESULT):
    if hresult:
        raise Exception(f"HRESULT: {hresult}")


class IVirtualDesktopManager(IUnknown):
    _iid_ = GUID("{A5CD92FF-29BE-454C-8D04-D82879FB3F1B}")

    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "IsWindowOnCurrentVirtualDesktop",
            (["in"], HWND, "topLevelWindow"),
            (["out"], LPBOOL, "onCurrentDesktop"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetWindowDesktopId",
            (["in"], HWND, "topLevelWindow"),
            (["out"], POINTER(GUID), "desktopId"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "MoveWindowToDesktop",
            (["in"], HWND, "topLevelWindow"),
            (["in"], POINTER(GUID), "desktopId"),
        ),
    ]

    def GetWindowDesktopId(self, hwnd: HWND) -> GUID:
        desktop_id = GUID()
        _check(self.__com_GetWindowDesktopId(hwnd, pointer(desktop_id)))
        return desktop_id

    def IsWindowOnCurrentVirtualDesktop(self, hwnd: HWND) -> bool:
        value = BOOL()
        _check(self.__com_IsWindowOnCurrentVirtualDesktop(hwnd, pointer(value)))
        return value.value

    def MoveWindowToDesktop(self, hwnd: HWND, desktop_id: GUID):
        _check(self.__com_MoveWindowToDesktop(hwnd, pointer(desktop_id)))


virtual_desktop_manager: IVirtualDesktopManager = CoCreateInstance(
    GUID("{AA509086-5CA9-4C25-8F95-589D3C07B48A}"), interface=IVirtualDesktopManager
)


if __name__ == "__main__":
    import time

    time.sleep(2)
    virtual_desktop_manager.GetWindowDesktopId(windll.user32.GetForegroundWindow())
    # print(virtual_desktop_manager.IsWindowOnCurrentVirtualDesktop(HWND(131352)))
