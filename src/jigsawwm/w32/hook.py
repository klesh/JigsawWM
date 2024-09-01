"""Windows hook"""

# pylint: disable=invalid-name
import enum
import logging
import signal
from ctypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from typing import Callable

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


def _errcheck_bool(result, _func, args):
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

    _fields_ = (
        ("vkCode", DWORD),
        ("scanCode", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )

    def __repr__(self):
        return (
            f"KBDLLHOOKDATA(vkCode={self.vkCode}, scanCode={self.scanCode},"
            f" flags={self.flags}, time={self.time}, dwExtraInfo={self.dwExtraInfo})"
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
        """Get high word of mouseData"""
        return WORD(self.mouseData >> 16).value

    def loword(self) -> int:
        """Get low word of mouseData"""
        return WORD(self.mouseData & 0xFFFF).value

    def __repr__(self) -> str:
        return (
            f"MSLLHOOKDATA(pt={self.pt}, mouseData={self.mouseData}, flags={self.flags},"
            f" time={self.time}, dwExtraInfo={self.dwExtraInfo})"
        )


_hooks = {}


def hook(
    hook_id, wparam_type, lparam_type, cb, n_code=HC_ACTION, n_code_type=int
) -> HANDLE:
    """Install hook by calling SetWindowsHookExW"""

    # for the hooks to work, note that only low level keyboard/mouse work this way
    # while others require DLL injection
    @HOOKPROC
    def proc(nCode, wParam, lParam):  # pylint: disable=invalid-name
        if n_code is None or nCode == n_code:
            ncode = n_code_type(nCode)
            wparam = wparam_type(wParam)
            lparam = cast(lParam, POINTER(lparam_type))[0]
            if cb(ncode, wparam, lparam):
                return 1
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    handle = user32.SetWindowsHookExW(hook_id, proc, None, 0)
    # keep a reference to the callback to prevent it from being garbage collected
    _hooks[handle] = proc
    return handle


def unhook(handle: HANDLE):
    """Unhook"""
    if handle in _hooks:
        _hooks.pop(handle)
        user32.UnhookWindowsHookEx(handle)


def hook_keyboard(cb: Callable[[int, KBDLLHOOKMSGID, KBDLLHOOKDATA], bool]) -> HANDLE:
    """Install keyboard hook

    Usage:

    .. code-block:: python

        def swallow_keyboard_a_key_event(msgid: KBDLLHOOKMSGID, data: KBDLLHOOKDATA) -> bool:
            return data.vkCode == VirtualKey.VK_A:

        hook_keyboard(swallow_keyboard_a_key_event)

    :param callback: function to be called when key press/release, return ``True`` to stop
                     propagation
    :return: hook handle (for unhook) and callback function(must be reference somewhere
             or it will be GCed),
    :rtype: Tuple[HANDLE, Callable]
    """
    return hook(13, KBDLLHOOKMSGID, KBDLLHOOKDATA, cb)


def hook_mouse(cb: Callable[[int, MSLLHOOKMSGID, MSLLHOOKDATA], bool]) -> HANDLE:
    """Install mouse hook

    Usage:

    .. code-block:: python

        def swallow_mouse_middle_btn_event(msgid: MSLLHOOKMSGID, data: MSLLHOOKDATA) -> bool:
            return msgid == MSLLHOOKMSGID.WM_MBUTTONUP or msgid == MSLLHOOKMSGID.WM_MBUTTONDOWN:

        hook_mouse(swallow_mouse_middle_btn_event)

    :param callback: function to be called when mouse moved, bth pressed/release and scroll,
                        return ``True`` to stop propagation
    :return: hook handle (for unhook) and callback function(must be reference somewhere
             or it will be GCed),
    :rtype: Tuple[HANDLE, Callable]
    """
    return hook(14, MSLLHOOKMSGID, MSLLHOOKDATA, cb)


class SHELL_CODE(enum.IntEnum):
    """Shell hook code"""

    HSHELL_ACCESSIBILITYSTATE = 11  # The accessibility state has changed.
    HSHELL_ACTIVATESHELLWINDOW = 3  # The shell should activate its main window.
    HSHELL_APPCOMMAND = 12  # The user completed an input event (for example, pressed an application command button on the mouse or an application command key on the keyboard), and the application did not handle the WM_APPCOMMAND message generated by that input. If the Shell procedure handles the WM_COMMAND message, it should not call CallNextHookEx. See the Return Value section for more information.
    HSHELL_GETMINRECT = 5  # A window is being minimized or maximized. The system needs the coordinates of the minimized rectangle for the window.
    HSHELL_LANGUAGE = (
        8  # Keyboard language was changed or a new keyboard layout was loaded.
    )
    HSHELL_REDRAW = 6  # The title of a window in the task bar has been redrawn.
    HSHELL_TASKMAN = 7  # The user has selected the task list. A shell application that provides a task list should return TRUE to prevent Windows from starting its task list.
    HSHELL_WINDOWACTIVATED = (
        4  # The activation has changed to a different top-level, unowned window.
    )
    HSHELL_WINDOWCREATED = 1  # A top-level, unowned window has been created. The window exists when the system calls this hook.
    HSHELL_WINDOWDESTROYED = 2  # A top-level, unowned window is about to be destroyed. The window still exists when the system calls this hook.
    HSHELL_WINDOWREPLACED = 13


def hook_shell(cb: Callable[[SHELL_CODE, WPARAM, LPARAM], bool]) -> HANDLE:
    """Install shell hook, unfortunately this only works for DLL module

    Usage:

    .. code-block:: python

        def swallow_shell_event(nCode: int, wParam: WPARAM, lParam: LPARAM) -> bool:
            return True

        hook_shell(swallow_shell_event)

    :param callback: function to be called when shell event, return ``True`` to stop propagation
    :return: hook handle (for unhook) and callback function(must be reference somewhere or it will be GCed),
    :rtype: Tuple[HANDLE, Callable]
    """
    return hook(10, WPARAM, LPARAM, cb, n_code_type=SHELL_CODE)


def register_window_message_shellhook():
    """Register window message for shell hook"""
    return user32.RegisterWindowMessageW("SHELLHOOK")


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
    def proc(_hhook, event, hwnd, id_obj, id_chd, id_evt_thread, dwms_evt_time):
        cb(WinEvent(event), hwnd, id_obj, id_chd, id_evt_thread, dwms_evt_time)

    handle = user32.SetWinEventHook(
        DWORD(event_min.value),
        DWORD(event_max.value),
        HMODULE(None),
        proc,
        0,
        0,
        0,  # WINEVENT_OUTOFCONTEXT
    )
    # keep a reference to the callback to prevent it from being garbage collected
    _winevent_hooks[handle] = proc
    return handle


def unhook_winevent(handle: HANDLE):
    """Unhook"""
    if handle in _winevent_hooks:
        _winevent_hooks.pop(handle)
        user32.UnhookWinEvent(handle)


def message_loop():
    """For debugging purpose"""
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    msg = byref(MSG())
    while True:
        bRet = user32.GetMessageW(msg, None, 0, 0)
        if not bRet:
            break
        if bRet == -1:
            raise WinError(get_last_error())
        user32.TranslateMessage(msg)
        print(msg.WParam)
        user32.DispatchMessageW(msg)
