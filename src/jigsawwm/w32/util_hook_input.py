"""Hook and inspect keyboard and mouse events"""
# pylint: disable=consider-using-f-string
import logging
import time
import threading
from ctypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from datetime import datetime

from . import window
from .vk import Vk
from .hook import * # pylint: disable=wildcard-import,unused-wildcard-import

logging.basicConfig(level=logging.DEBUG)

def keyboard_cb(_code: int, msgid: KBDLLHOOKMSGID, msg: KBDLLHOOKDATA) -> bool:
    """Keyboard hook callback"""
    print(
        "{:15s} {:15s}: vkCode {:3x} scanCode {:3x} flags: {:3d}, time: {} extra: {}".format(
            Vk(msg.vkCode).name,
            msgid.name,
            msg.vkCode,
            msg.scanCode,
            msg.flags,
            msg.time,
            msg.dwExtraInfo,
        )
    )

def mouse_cb(_code: int, msgid: MSLLHOOKMSGID, msg: MSLLHOOKDATA) -> bool:
    """Mouse hook callback"""
    print(
        "{:15s}  x: {:3d} y: {:3d} hi: {:5x} lo: {:5x} flags: {:3x} extra: {:6x} t: {:d}".format(
            msgid.name,
            msg.pt.x,
            msg.pt.y,
            int(msg.hiword()),
            int(msg.loword()),
            msg.flags,
            msg.dwExtraInfo,
            msg.time,
        )
    )
    if msgid == MSLLHOOKMSGID.WM_MOUSEWHEEL:
        print("delta: {}".format(msg.get_wheel_delta()))

def winevent_cb(
    event: WinEvent,
    hwnd: HWND,
    id_obj: LONG,
    id_chd: LONG,
    id_evt_thread: DWORD,
    time: DWORD,
):
    """Window event callback"""
    if event in (
        WinEvent.EVENT_OBJECT_LOCATIONCHANGE,
        WinEvent.EVENT_OBJECT_NAMECHANGE,
        WinEvent.EVENT_SYSTEM_CAPTURESTART,
        WinEvent.EVENT_SYSTEM_CAPTUREEND,
    ):
        return
    print("==================================")
    print(
        "[{now}] {event:30s} {hwnd:8d} ido: {id_obj:6d} idc: {id_chd:6d} {title}".format(
            now=datetime.now().strftime("%M:%S.%f"),
            event=event.name,
            hwnd=hwnd or 0,
            id_obj=id_obj,
            id_chd=id_chd,
            title=window.Window(hwnd).title,
        )
    )
    window.inspect_window(hwnd)
    print("==================================")

kb_hook = hook_keyboard(keyboard_cb)
ms_hook = hook_mouse(mouse_cb)
we_hook = hook_winevent(
    WinEvent.EVENT_MIN,
    WinEvent.EVENT_MAX,
    winevent_cb
    # WinEvent.EVENT_SYSTEM_MINIMIZESTART, WinEvent.EVENT_SYSTEM_MINIMIZEEND, winevent
)

def unhook_mouse_after_10s():
    """Unhook mouse after 10s"""
    time.sleep(10)
    unhook(ms_hook)
    print("mouse unhooked")

threading.Thread(target=unhook_mouse_after_10s).start()

message_loop()
