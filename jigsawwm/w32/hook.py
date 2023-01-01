import enum
import threading
import time
from ctypes import *
from ctypes.wintypes import *
from functools import partial
from typing import Callable, Optional, Tuple

from .winevent import HWINEVENTHOOK, WINEVENTHOOKPROC, WinEvent

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


def errcheck_bool(result, func, args):
    if not result:
        raise WinError(get_last_error())
    return args


user32.SetWindowsHookExW.errcheck = errcheck_bool
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
    """Mouse event msgid"""

    WM_MOUSEMOVE = 0x0200
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    WM_MBUTTONDOWN = 0x0207
    WM_MBUTTONUP = 0x0208
    WM_MOUSEWHEEL = 0x020A
    WM_MOUSEHWHEEL = 0x020E


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


# wrap them all inside Hook class


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


class Hook(threading.Thread):
    """Hook low level keyboard/mouse event

    Usage:
    ```
    def swallow_keyboard_a_key_event(msgid: KBDLLHOOKMSGID, data: KBDLLHOOKDATA) -> bool:
        return data.vkCode == VirtualKey.VK_A:

    def swallow_mouse_middle_btn_event(msgid: MSLLHOOKMSGID, data: MSLLHOOKDATA) -> bool:
        return msgid == MSLLHOOKMSGID.WM_MBUTTONUP or msgid == MSLLHOOKMSGID.WM_MBUTTONDOWN:

    def winevent(
        event: WinEvent,
        hwnd: HWND,
        id_obj: LONG,
        id_chd: LONG,
        id_evt_thread: DWORD,
        time: DWORD,
    ):
        pass


    hook = Hook()
    kbd_hook_id = hook.install_keyboard_hook(swallow_keyboard_a_key_event)
    mouse_hook_id = hook.install_mouse_hook(swallow_mouse_middle_btn_event)
    winevent_hook_id = hook.install_winevent_hook()
    hook.start()
    ```

    :param **kwargs:
    """

    def __init__(self):
        self._installed_hooks = {}
        self._queue = []
        super().__init__()

    def _install_hook(
        self, hook_id, wparam_type, lparam_type, handler
    ) -> Tuple[HANDLE, Callable]:
        # for the hooks to work, note that only low level keyboard/mouse work this way
        # while others require DLL injection
        @HOOKPROC
        def proc(nCode, wParam, lParam):
            if nCode == HC_ACTION:
                wparam = wparam_type(wParam)
                lparam = cast(lParam, POINTER(lparam_type))[0]
                if handler(wparam, lparam):
                    return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        hook = user32.SetWindowsHookExW(hook_id, proc, None, 0)
        return hook, proc

    def _install_winevent_hook(
        self,
        event_min: WinEvent,
        event_max: WinEvent,
        cb: Callable[[WinEvent, HWND, LONG, LONG, DWORD, DWORD], None],
    ) -> Tuple[HANDLE, Callable]:
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
        return hook, proc

    def install_keyboard_hook(
        self, callback: Callable[[KBDLLHOOKMSGID, KBDLLHOOKDATA], bool]
    ):
        self._queue.append(
            partial(self._install_hook, 13, KBDLLHOOKMSGID, KBDLLHOOKDATA, callback)
        )

    def install_mouse_hook(
        self, callback: Callable[[MSLLHOOKMSGID, MSLLHOOKDATA], bool]
    ):
        self._queue.append(
            partial(self._install_hook, 14, MSLLHOOKMSGID, MSLLHOOKDATA, callback)
        )

    def install_winevent_hook(
        self,
        callback: Callable[[WinEvent, HWND, LONG, LONG, DWORD, DWORD], None],
        event_min: WinEvent,
        event_max: Optional[WinEvent] = None,
    ):
        self._queue.append(
            partial(
                self._install_winevent_hook, event_min, event_max or event_min, callback
            )
        )

    def run(self):
        # IMPORTANT: the hook must be installed in the thread!
        msg = MSG()
        while True:
            # install pending hooks
            while self._queue:
                install_hook = self._queue.pop()
                hook, proc = install_hook()
                self._installed_hooks[hook] = proc

            bRet = user32.GetMessageW(byref(msg), None, 0, 0)
            if not bRet:
                break
            if bRet == -1:
                raise WinError(get_last_error())
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))

    def stop(self):
        user32.PostThreadMessageW(self.ident, WM_QUIT, 0, 0)


if __name__ == "__main__":
    from datetime import datetime

    from . import window
    from .vk import Vk

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
        msg = (
            (msg.pt.x, msg.pt.y),
            msg.mouseData,
            msg.flags,
            msg.time,
            msg.dwExtraInfo,
        )
        print("{:15s}: {}".format(msgid.name, msg))

    def winevent(
        event: WinEvent,
        hwnd: HWND,
        id_obj: LONG,
        id_chd: LONG,
        id_evt_thread: DWORD,
        time: DWORD,
    ):
        print("==================================")
        # print(
        #     hwnd is None,
        #     id_obj is None,
        #     id_chd is None,
        #     window.Window(hwnd).title is None,
        # )
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

    hook = Hook()
    # hook.install_winevent_hook(winevent, WinEvent.EVENT_SYSTEM_MOVESIZEEND)
    # hook.install_winevent_hook(winevent, WinEvent.EVENT_SYSTEM_MINIMIZESTART, WinEvent.EVENT_SYSTEM_MINIMIZEEND)
    # hook.install_winevent_hook(
    #     winevent, WinEvent.EVENT_OBJECT_SHOW, WinEvent.EVENT_OBJECT_HIDE
    # )
    # hook.install_winevent_hook(
    #     winevent, WinEvent.EVENT_OBJECT_CREATE, WinEvent.EVENT_OBJECT_DESTROY
    # )
    hook.install_winevent_hook(winevent, WinEvent.EVENT_MIN, WinEvent.EVENT_MAX)
    # hook.install_keyboard_hook(keyboard)
    hook.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            hook.stop()
            break
