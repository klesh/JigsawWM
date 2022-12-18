from ctypes import *
from ctypes.wintypes import *
import enum
import time
import threading

user32 = WinDLL("user32", use_last_error=True)

HC_ACTION = 0
# incoming message
WM_QUIT = 0x0012


# types for the hook including input parameter and return result

ULONG_PTR = WPARAM
LRESULT = LPARAM
# LPMSG = POINTER(MSG)

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

# keyboard hook definition


class KBDLLHOOKMSGID(enum.IntEnum):
    """Keyboard even msgid"""

    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SYSKEYDOWN = 0x0104
    WM_SYSKEYUP = 0x0105


class KBDLLHOOKDATA(Structure):
    """Keyboard even data"""

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

    _fields_ = (
        ("pt", POINT),
        ("mouseData", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


# wrap them all inside Hook class


class Hook(threading.Thread):
    """Hook low level keyboard/mouse event

    Usage:
    ```
    def swallow_keyboard_a_key_event(msgid KBDLLHOOKMSGID, data KBDLLHOOKDATA) -> bool:
        return data.vkCode == VirtualKey.VK_A:

    def swallow_mouse_middle_btn_event(msgid MSLLHOOKMSGID, data MSLLHOOKDATA) -> bool:
        return msgid == MSLLHOOKMSGID.WM_MBUTTONUP or msgid == MSLLHOOKMSGID.WM_MBUTTONDOWN:
    Hook(keyboard=swallow_keyboard_a_key_event, mouse=swallow_mouse_middle_btn_event)
    ```

    :param **kwargs:
    """

    SUPPORTED_HOOKS = {
        # hook_name: (idHook, wParamMsgId lParamStruct)
        "keyboard": (13, KBDLLHOOKMSGID, KBDLLHOOKDATA),
        "mouse": (14, MSLLHOOKMSGID, MSLLHOOKDATA),
    }

    def __init__(
        self,
        **kwargs,
    ):
        for hook_name in kwargs.keys():
            if hook_name not in self.SUPPORTED_HOOKS:
                raise Exception(f"unsupported hook {hook_name}")
        self._specified_hooks = kwargs
        super().__init__()

    def _install_hook(self, hook_id, wparam_type, lparam_type, handler):
        @HOOKPROC
        def proc(nCode, wParam, lParam):
            if nCode == HC_ACTION:
                wparam = wparam_type(wParam)
                lparam = cast(lParam, lparam_type)[0]
                if handler(wparam, lparam):
                    return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        hhook = user32.SetWindowsHookExW(hook_id, proc, None, 0)
        return proc, hhook

    def _install_hooks(self):
        self._installed_procs = {}
        self._installed_hooks = {}
        for name, handler in self._specified_hooks.items():
            hook_id, wparam_type, lparam_type = self.SUPPORTED_HOOKS[name]
            proc, hook = self._install_hook(
                hook_id,
                wparam_type,
                POINTER(lparam_type),
                handler,
            )
            # hold the references for the hook to work properly
            self._installed_procs[name] = proc
            self._installed_hooks[name] = hook

    def run(self):
        self._install_hooks()
        # for the hooks to work, note that only low level keyboard/mouse work this way
        # while others require DLL injection
        msg = MSG()
        while True:
            bRet = user32.GetMessageW(byref(msg), None, 0, 0)
            if not bRet:
                break
            if bRet == -1:
                raise WinError(get_last_error())
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))


if __name__ == "__main__":
    from vk import VirtualKey

    def keyboard(msgid: KBDLLHOOKMSGID, msg: KBDLLHOOKDATA) -> bool:
        print(
            "{:15s} {:15s}: vkCode {:3x} scanCode {:3x} flags: {:3d}, time: {} extra: {}".format(
                VirtualKey(msg.vkCode).name,
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

    hook = Hook(
        keyboard=keyboard,
        mouse=mouse,
    )
    hook.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            user32.PostThreadMessageW(hook.ident, WM_QUIT, 0, 0)
            break
