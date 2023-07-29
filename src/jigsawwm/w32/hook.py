import enum
import logging
import threading
import time
from ctypes import *
from ctypes.wintypes import *
from typing import Callable

from .vk import Vk
from .winevent import HWINEVENTHOOK, WINEVENTHOOKPROC, WinEvent

logger = logging.getLogger(__name__)

user32 = WinDLL("user32", use_last_error=True)

HC_ACTION = 0
# incoming message
WM_QUIT = 0x0012


# types for the hook including input parameter and return result

ULONG_PTR = WPARAM
LRESULT = LPARAM
# LPMSG = POINTER(MSG)

# Hook
HOOKPROC = WINFUNCTYPE(LRESULT, c_int, WPARAM, LPARAM)


# setup api


def _errcheck_bool(result, func, args):
    if not result:
        raise WinError(get_last_error())
    return args


user32.SetWindowsHookExW.errcheck = _errcheck_bool
user32.SetWindowsHookExW.restype = HHOOK
user32.SetWindowsHookExW.argtypes = (
    c_int,  # _In_ idHook
    HOOKPROC,  # _In_ lpfn
    HINSTANCE,  # _In_ hMod
    DWORD,
)  # _In_ dwThreadId

user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = (
    HHOOK,  # _In_opt_ hhk
    c_int,  # _In_     nCode
    WPARAM,  # _In_     wParam
    LPARAM,
)  # _In_     lParam

user32.GetMessageW.argtypes = (
    LPMSG,  # _Out_    lpMsg
    HWND,  # _In_opt_ hWnd
    UINT,  # _In_     wMsgFilterMin
    UINT,
)  # _In_     wMsgFilterMax

user32.TranslateMessage.argtypes = (LPMSG,)
user32.DispatchMessageW.argtypes = (LPMSG,)

user32.SetWinEventHook.restype = HWINEVENTHOOK

# keyboard hook definition


class KBDLLHOOKMSGID(enum.IntEnum):
    """Keyboard event msgid"""

    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SYSKEYDOWN = 0x0104
    WM_SYSKEYUP = 0x0105


class KBDLLHOOKDATA(Structure):
    """Keyboard event data"""

    vkCode: int
    scanCode: int
    flags: int
    time: int
    dwExtraInfo: int

    _fields_ = (
        ("vkCode", DWORD),
        ("scanCode", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


# mouse hook definition


class MSLLHOOKMSGID(enum.IntEnum):
    """Mouse event msgid

    Ref: https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-xbuttondown
    """

    WM_MOUSEMOVE = 0x0200
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    WM_MBUTTONDOWN = 0x0207
    WM_MBUTTONUP = 0x0208
    WM_MOUSEWHEEL = 0x020A
    WM_MOUSEHWHEEL = 0x020E
    WM_XBUTTONDOWN = 0x020B
    WM_XBUTTONUP = 0x020C


class MSLLHOOKDATA(Structure):
    """Mouse event data"""

    pt: POINT
    mouseData: int
    flags: int
    time: int
    dwExtraInfo: int

    _fields_ = (
        ("pt", POINT),
        ("mouseData", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )

    def get_wheel_delta(self) -> int:
        """Get mouse wheel delta

        Ref: https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-mousewheel
        """
        return SHORT(self.mouseData >> 16).value

    def hiword(self) -> int:
        return WORD(self.mouseData >> 16).value

    def loword(self) -> int:
        return WORD(self.mouseData & 0xFFFF).value


_hooks = {}


def hook(hook_id, wparam_type, lparam_type, cb) -> HANDLE:
    # for the hooks to work, note that only low level keyboard/mouse work this way
    # while others require DLL injection
    @HOOKPROC
    def proc(nCode, wParam, lParam):
        if nCode == HC_ACTION:
            wparam = wparam_type(wParam)
            lparam = cast(lParam, POINTER(lparam_type))[0]
            if cb(wparam, lparam):
                return 1
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    hook = user32.SetWindowsHookExW(hook_id, proc, None, 0)
    # keep a reference to the callback to prevent it from being garbage collected
    global _hooks
    _hooks[hook] = proc
    return hook


def unhook(hook: HANDLE):
    """Unhook"""
    global _hooks
    if hook in _hooks:
        _hooks.pop(hook)
        user32.UnhookWindowsHookEx(hook)


_winevent_hooks = {}


def hook_winevent(
    event_min: WinEvent,
    event_max: WinEvent,
    cb: Callable[[WinEvent, HWND, LONG, LONG, DWORD, DWORD], None],
) -> HANDLE:
    """Hook window events

    Usage:

    .. code-block:: python
        def winevent_callback(
            event: WinEvent,
            hwnd: HWND,
            id_obj: LONG,
            id_chd: LONG,
            id_evt_thread: DWORD,
            time: DWORD,
        ):
            pass

        hook_winevent(winevent_callback)
    """

    @WINEVENTHOOKPROC
    def proc(hhook, event, hwnd, id_obj, id_chd, id_evt_thread, dwms_evt_time):
        cb(WinEvent(event), hwnd, id_obj, id_chd, id_evt_thread, dwms_evt_time)

    hook = user32.SetWinEventHook(
        DWORD(event_min.value),
        DWORD(event_max.value),
        HMODULE(None),
        proc,
        0,
        0,
        0,  # WINEVENT_OUTOFCONTEXT
    )
    # keep a reference to the callback to prevent it from being garbage collected
    global _hooks
    _winevent_hooks[hook] = proc
    return hook


def unhook_winevent(hook: HANDLE):
    """Unhook"""
    global _winevent_hooks
    if hook in _winevent_hooks:
        _winevent_hooks.pop(hook)
        user32.UnhookWinEvent(hook)


def hook_keyboard(cb: Callable[[KBDLLHOOKMSGID, KBDLLHOOKDATA], bool]) -> HANDLE:
    """Install keyboard hook

    Usage:

    .. code-block:: python

        def swallow_keyboard_a_key_event(msgid: KBDLLHOOKMSGID, data: KBDLLHOOKDATA) -> bool:
            return data.vkCode == VirtualKey.VK_A:

        hook_keyboard(swallow_keyboard_a_key_event)

    :param callback: function to be called when key press/release, return ``True`` to stop
                     propagation
    :return: hook handle (for unhook) and callback function(must be reference somewhere or it will be GCed),
    :rtype: Tuple[HANDLE, Callable]
    """
    return hook(13, KBDLLHOOKMSGID, KBDLLHOOKDATA, cb)


def hook_mouse(cb: Callable[[MSLLHOOKMSGID, MSLLHOOKDATA], bool]) -> HANDLE:
    """Install mouse hook

    Usage:

    .. code-block:: python

        def swallow_mouse_middle_btn_event(msgid: MSLLHOOKMSGID, data: MSLLHOOKDATA) -> bool:
            return msgid == MSLLHOOKMSGID.WM_MBUTTONUP or msgid == MSLLHOOKMSGID.WM_MBUTTONDOWN:

        hook_mouse(swallow_mouse_middle_btn_event)

    :param callback: function to be called when mouse moved, bth pressed/release and scroll,
                        return ``True`` to stop propagation
    :return: hook handle (for unhook) and callback function(must be reference somewhere or it will be GCed),
    :rtype: Tuple[HANDLE, Callable]
    """
    return hook(14, MSLLHOOKMSGID, MSLLHOOKDATA, cb)


def message_loop():
    """For debugging purpose"""
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    msg = byref(MSG())
    while True:
        bRet = user32.GetMessageW(msg, None, 0, 0)
        if not bRet:
            break
        if bRet == -1:
            raise WinError(get_last_error())
        user32.TranslateMessage(msg)
        user32.DispatchMessageW(msg)


if __name__ == "__main__":
    import sys
    from datetime import datetime

    from . import window

    logging.basicConfig(level=logging.DEBUG)

    def keyboard(msgid: KBDLLHOOKMSGID, msg: KBDLLHOOKDATA) -> bool:
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

    def mouse(msgid: MSLLHOOKMSGID, msg: MSLLHOOKDATA) -> bool:
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

    def winevent(
        event: WinEvent,
        hwnd: HWND,
        id_obj: LONG,
        id_chd: LONG,
        id_evt_thread: DWORD,
        time: DWORD,
    ):
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

    kb_hook = hook_keyboard(keyboard)
    ms_hook = hook_mouse(mouse)
    we_hook = hook_winevent(
        WinEvent.EVENT_MIN,
        WinEvent.EVENT_MAX,
        winevent
        # WinEvent.EVENT_SYSTEM_MINIMIZESTART, WinEvent.EVENT_SYSTEM_MINIMIZEEND, winevent
    )

    def unhook_mouse_after_10s():
        time.sleep(10)
        unhook(ms_hook)
        print("mouse unhooked")

    threading.Thread(target=unhook_mouse_after_10s).start()

    message_loop()
