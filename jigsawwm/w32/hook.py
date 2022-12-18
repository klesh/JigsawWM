from ctypes import *
from ctypes.wintypes import *
import time
import threading

user32 = WinDLL("user32", use_last_error=True)

# incoming action: the hook should process when code == HC_ACTION

HC_ACTION = 0
# incoming message
WM_QUIT = 0x0012
# keyboard messages
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
# mouse messages
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_MOUSEHWHEEL = 0x020E

MSG_TEXT = {
    # keyboard
    WM_KEYDOWN: "WM_KEYDOWN",
    WM_KEYUP: "WM_KEYUP",
    WM_SYSKEYDOWN: "WM_SYSKEYDOWN",
    WM_SYSKEYUP: "WM_SYSKEYUP",
    # mouse
    WM_MOUSEMOVE: "WM_MOUSEMOVE",
    WM_LBUTTONDOWN: "WM_LBUTTONDOWN",
    WM_LBUTTONUP: "WM_LBUTTONUP",
    WM_RBUTTONDOWN: "WM_RBUTTONDOWN",
    WM_RBUTTONUP: "WM_RBUTTONUP",
    WM_MBUTTONDOWN: "WM_MBUTTONDOWN",
    WM_MBUTTONUP: "WM_MBUTTONUP",
    WM_MOUSEWHEEL: "WM_MOUSEWHEEL",
    WM_MOUSEHWHEEL: "WM_MOUSEHWHEEL",
}

# types for the hook including input parameter and return result

ULONG_PTR = WPARAM
LRESULT = LPARAM
LPMSG = POINTER(MSG)

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

# callwndproc hook definition
HCBT_ACTIVATE = 5
HCBT_CLICKSKIPPED = 6
HCBT_CREATEWND = 3
HCBT_DESTROYWND = 4
HCBT_KEYSKIPPED = 7
HCBT_MINMAX = 1
HCBT_MOVESIZE = 0
HCBT_QS = 2
HCBT_SETFOCUS = 9
HCBT_SYSCOMMAND = 8

# keyboard hook definition


class KBDLLHOOKSTRUCT(Structure):
    _fields_ = (
        ("vkCode", DWORD),
        ("scanCode", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


# mouse hook definition


class MSLLHOOKSTRUCT(Structure):
    _fields_ = (
        ("pt", POINT),
        ("mouseData", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


# wrap them all inside Hook class


class Hook(threading.Thread):
    SUPPORTED_HOOKS = {
        # hook_name: (idHook, WPARAMSTRUCT)
        "keyboard": (13, KBDLLHOOKSTRUCT),
        "mouse": (14, MSLLHOOKSTRUCT),
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

    def _install_hook(self, hook_id, lparam_type, handler):
        @HOOKPROC
        def proc(nCode, wParam, lParam):
            if nCode == HC_ACTION:
                lp = lParam
                if lparam_type is not None:
                    lp = cast(lParam, lparam_type)[0]
                # try:
                if handler(wParam, lp):
                    return 1
                # except Exception as e:
                #   print(e)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        hhook = user32.SetWindowsHookExW(hook_id, proc, None, 0)
        return proc, hhook

    def _install_hooks(self):
        self._installed_procs = {}
        self._installed_hooks = {}
        for name, handler in self._specified_hooks.items():
            idHook, WPARAMSTRUCT = self.SUPPORTED_HOOKS[name]
            proc, hook = self._install_hook(
                idHook,
                POINTER(WPARAMSTRUCT),
                handler,
            )
            self._installed_procs[name] = proc
            self._installed_hooks[name] = hook

    def run(self):
        self._install_hooks()
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

    def keyboard(msg_id: int, msg: KBDLLHOOKSTRUCT) -> bool:
        msgid = MSG_TEXT.get(msg_id, str(msg_id))
        print(
            "{:15s} {:15s}: vkCode {:3x} scanCode {:3x} flags: {:3d}, time: {} extra: {}".format(
                VirtualKey(msg.vkCode).name,
                msgid,
                msg.vkCode,
                msg.scanCode,
                msg.flags,
                msg.time,
                msg.dwExtraInfo,
            )
        )

    def mouse(msg_id: int, msg: MSLLHOOKSTRUCT) -> bool:
        msgid = MSG_TEXT.get(msg_id, str(msg_id))
        msg = (
            (msg.pt.x, msg.pt.y),
            msg.mouseData,
            msg.flags,
            msg.time,
            msg.dwExtraInfo,
        )
        print("{:15s}: {}".format(msgid, msg))

    hook = Hook(
        keyboard=keyboard,
        # mouse=mouse,
    )
    hook.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            user32.PostThreadMessageW(hook.ident, WM_QUIT, 0, 0)
            break

    # CBT(listen to move/resize/create/destroy of windows)
    # https://www.experts-exchange.com/questions/21772590/WH-CBT-Callback-does-not-seem-to-want-to-fire-Python-C-SWIG.html
