import enum
import time
from ctypes import *
from ctypes.wintypes import *
from dataclasses import dataclass
from typing import Iterator, List, Optional

from . import process
from .sendinput import *
from .vk import Vk

user32 = WinDLL("user32", use_last_error=True)
kernel32 = WinDLL("kernel32", use_last_error=True)
dwmapi = WinDLL("dwmapi", use_last_error=True)


def enum_windows() -> List[HWND]:
    """Returns a List of all top-level windows on the screen.

    :return: list of window handles
    :rtype: List[HWND]
    """
    hwnds = []

    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(hwnd: HWND, lParam: LPARAM) -> BOOL:
        hwnds.append(hwnd)
        return True

    if not user32.EnumWindows(enum_windows_proc, None):
        raise WinError(get_last_error())
    return hwnds


def enum_desktop_windows(hdst: Optional[HDESK] = None) -> List[HWND]:
    """Returns a List of all top-level windows associated with the specified desktop.

    Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdesktopwindows

    :param hdst: HDESK, optional. If this parameter is NULL, the current desktop is used.
    :return: list of window handles
    :rtype: List[HWND]
    """
    hwnds = []

    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(hwnd: HWND, lParam: LPARAM) -> BOOL:
        hwnds.append(hwnd)
        return True

    if not user32.EnumDesktopWindows(hdst, enum_windows_proc, None):
        raise WinError(get_last_error())
    return hwnds


def first_desktop_window(hdst: Optional[HDESK] = None) -> Optional[HWND]:
    hwnds = []

    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(hwnd: HWND, lParam: LPARAM) -> BOOL:
        hwnds.append(hwnd)
        return False

    user32.EnumDesktopWindows(hdst, enum_windows_proc, None)
    return hwnds[0]


def get_foreground_window() -> HWND:
    return user32.GetForegroundWindow()


class WindowStyle(enum.IntFlag):
    """The object that holds the window styles.

    Ref: https://docs.microsoft.com/en-us/windows/win32/winmsg/window-styles
    """

    BORDER = 0x00800000
    CAPTION = 0x00C00000
    CHILD = 0x40000000
    CHILDWINDOW = 0x40000000
    CLIPCHILDREN = 0x02000000
    CLIPSIBLINGS = 0x04000000
    DISABLED = 0x08000000
    DLGFRAME = 0x00400000
    GROUP = 0x00020000
    HSCROLL = 0x00100000
    ICONIC = 0x20000000
    MAXIMIZE = 0x01000000
    MAXIMIZEBOX = 0x00010000
    MINIMIZE = 0x20000000
    MINIMIZEBOX = 0x00020000
    OVERLAPPED = 0x00000000
    POPUP = 0x80000000
    SIZEBOX = 0x00040000
    SYSMENU = 0x00080000
    TABSTOP = 0x00010000
    THICKFRAME = 0x00040000
    TILED = 0x00000000
    TOOLWINDOW = 0x00000080
    VISIBLE = 0x10000000
    VSCROLL = 0x00200000
    OVERLAPPEDWINDOW = (
        OVERLAPPED | CAPTION | SYSMENU | THICKFRAME | MINIMIZEBOX | MAXIMIZEBOX
    )
    POPUPWINDOW = POPUP | BORDER | SYSMENU
    TILEDWINDOW = (
        OVERLAPPED | CAPTION | SYSMENU | THICKFRAME | MINIMIZEBOX | MAXIMIZEBOX
    )


class ExWindowStyle(enum.IntFlag):
    """The object that holds the extended window styles.

    Ref: https://docs.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles>
    """

    ACCEPTFILES = 0x00000010
    APPWINDOW = 0x00040000
    CLIENTEDGE = 0x00000200
    COMPOSITED = 0x02000000
    CONTEXTHELP = 0x00000400
    CONTROLPARENT = 0x00010000
    DLGMODALFRAME = 0x00000001
    LAYERED = 0x00080000
    LAYOUTRTL = 0x00400000
    LEFT = 0x00000000
    LEFTSCROLLBAR = 0x00004000
    LTRREADING = 0x00000000
    MDICHILD = 0x00000040
    NOACTIVATE = 0x08000000
    NOINHERITLAYOUT = 0x00100000
    NOPARENTNOTIFY = 0x00000004
    NOREDIRECTIONBITMAP = 0x00200000
    RIGHT = 0x00001000
    RIGHTSCROLLBAR = 0x00000000
    RTLREADING = 0x00002000
    STATICEDGE = 0x00020000
    TOOLWINDOW = 0x00000080
    TOPMOST = 0x00000008
    TRANSPARENT = 0x00000020
    WINDOWEDGE = 0x00000100
    OVERLAPPEDWINDOW = WINDOWEDGE | CLIENTEDGE
    PALETTEWINDOW = WINDOWEDGE | TOOLWINDOW | TOPMOST


class ShowWindowCmd(enum.IntFlag):
    """The object that holds the CmdShow for ShowWindow api

    Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindow
    """

    SW_HIDE = 0
    SW_MAXIMIZE = 3
    SW_MINIMIZE = 6
    SW_RESTORE = 9
    SW_SHOW = 5
    SW_SHOWMAXIMIZED = 3
    SW_SHOWMINIMIZED = 2
    SW_SHOWMINNOACTIVE = 7
    SW_SHOWNA = 8
    SW_SHOWNOACTIVATE = 4
    SW_SHOWNORMAL = 1


class DwmWindowAttribute(enum.IntEnum):
    """Options used by the DwmGetWindowAttribute and DwmSetWindowAttribute functions.

    Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
    """

    DWMWA_NCRENDERING_ENABLED = 1
    DWMWA_NCRENDERING_POLICY = 2
    DWMWA_TRANSITIONS_FORCEDISABLED = 3
    DWMWA_ALLOW_NCPAINT = 4
    DWMWA_CAPTION_BUTTON_BOUNDS = 5
    DWMWA_NONCLIENT_RTL_LAYOUT = 6
    DWMWA_FORCE_ICONIC_REPRESENTATION = 7
    DWMWA_FLIP3D_POLICY = 8
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    DWMWA_HAS_ICONIC_BITMAP = 10
    DWMWA_DISALLOW_PEEK = 11
    DWMWA_EXCLUDED_FROM_PEEK = 12
    DWMWA_CLOAK = 13
    DWMWA_CLOAKED = 14
    DWMWA_FREEZE_REPRESENTATION = 15
    DWMWA_PASSIVE_UPDATE_MODE = 16
    DWMWA_USE_HOSTBACKDROPBRUSH = 17
    DWMWA_USE_IMMERSIVE_DARK_MODE = (20,)
    DWMWA_WINDOW_CORNER_PREFERENCE = (33,)
    DWMWA_BORDER_COLOR = 34
    DWMWA_CAPTION_COLOR = 35
    DWMWA_TEXT_COLOR = 36
    DWMWA_VISIBLE_FRAME_BORDER_THICKNESS = 37
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMWA_LAST = 39


@dataclass
class Window:
    """Represents a top-level window

    :param hwnd: HWND the window handle
    """

    _hwnd: HWND
    _rect = None
    _exepath = None
    _pid = None
    _elevated = None
    _title = None
    _class_name = None
    _cloaked = None
    _ncrendering = None
    _bound = None
    _last_rect = None

    def __init__(self, hwnd: HWND):
        self._hwnd = hwnd

    def __eq__(self, other):
        return isinstance(other, Window) and self._hwnd == other._hwnd

    def __hash__(self):
        return hash(self._hwnd)

    @property
    def handle(self) -> HWND:
        return self._hwnd

    @property
    def title(self) -> str:
        """Retrieves the text of the specified window's title bar (if it has one)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtexta

        :return: text of the title bar
        :rtype: str
        """
        # length = user32.GetWindowTextLengthW(self.hwnd)
        if self._title is None:
            self._title = create_unicode_buffer(255)
        user32.GetWindowTextW(self._hwnd, self._title, 255)
        return str(self._title.value)

    @property
    def class_name(self):
        """Retrieves the name of the class to which the specified window belongs.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclassnamea

        :return: class name
        :rtype: str
        """
        if self._class_name is None:  # class_name would never change
            buff = create_unicode_buffer(100)
            user32.GetClassNameW(self._hwnd, buff, 100)
            self._class_name = str(buff.value)
        return self._class_name

    @property
    def exe(self):
        """Retrieves the full path of the executable

        :return: full path of the executable
        :rtype: str
        """
        if self._exepath is None:
            self._exepath = process.get_exepath(self.pid)
        return self._exepath

    @property
    def pid(self) -> int:
        """Retrieves the process id

        :return: process id
        :rtype: int
        """
        if self._pid is None:  # pid would never change
            pid = DWORD()
            user32.GetWindowThreadProcessId(self._hwnd, pointer(pid))
            self._pid = pid.value
        return self._pid

    @property
    def is_visible(self) -> bool:
        """Determines the visibility state of the specified window.

        :return: If the specified window, its parent window, its parent's parent window,
            and so forth, have the WS_VISIBLE style, the return value is `True`.
            Otherwise, the return value is `False`.
        :rtype: bool
        """
        return bool(user32.IsWindowVisible(self._hwnd))

    def get_style(self) -> WindowStyle:
        """Retrieves style

        :return: window style
        :rtype: WindowStyle
        """
        return WindowStyle(user32.GetWindowLongA(self._hwnd, -16))

    def get_exstyle(self) -> int:
        """Retrieves ex-style

        :return: window ex-style
        :rtype: ExWindowStyle
        """
        return ExWindowStyle(user32.GetWindowLongA(self._hwnd, -20))

    def minimize(self):
        """Minimizes the specified window and activates the next top-level window in the Z order."""
        user32.ShowWindow(self._hwnd, ShowWindowCmd.SW_MINIMIZE)

    def maximize(self):
        """Activates the window and displays it as a maximized window."""
        user32.ShowWindow(self._hwnd, ShowWindowCmd.SW_MAXIMIZE)

    def restore(self):
        """Activates and displays the window. If the window is minimized or maximized,
        the system restores it to its original size and position."""
        user32.ShowWindow(self._hwnd, ShowWindowCmd.SW_RESTORE)

    def toggle_maximize(self):
        """Toggle maximize style"""
        if self.get_style() & WindowStyle.MAXIMIZE:
            self.restore()
        else:
            self.maximize()

    @property
    def is_evelated(self):
        """Check if window is elevated (Administrator)"""
        if self._elevated is None:  # would never change
            self._elevated = process.is_elevated(self.pid)
        return self._elevated

    @property
    def is_cloaked(self) -> bool:
        """Check if window is cloaked (DWM)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        """
        if self._cloaked is None:
            self._cloaked = INT()
        windll.dwmapi.DwmGetWindowAttribute(
            self._hwnd,
            DwmWindowAttribute.DWMWA_CLOAKED,
            pointer(self._cloaked),
            sizeof(self._cloaked),
        )
        return bool(self._cloaked.value)

    def exists(self) -> bool:
        return user32.IsWindow(self._hwnd)

    @property
    def is_non_client_rendering_enable(self) -> bool:
        """Check if non-client rendering is enabled (DWM)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        """
        if self._ncrendering is None:
            self._ncrendering = BOOL()
        windll.dwmapi.DwmGetWindowAttribute(
            self._hwnd,
            DwmWindowAttribute.DWMWA_NCRENDERING_ENABLED,
            pointer(self._ncrendering),
            sizeof(self._ncrendering),
        )
        return bool(self._ncrendering.value)

    def get_extended_frame_bounds(self) -> RECT:
        """Retrieves extended frame bounds

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        """
        if self._bound is None:
            self._bound = RECT()
        windll.dwmapi.DwmGetWindowAttribute(
            self._hwnd,
            DwmWindowAttribute.DWMWA_EXTENDED_FRAME_BOUNDS,
            pointer(self._bound),
            sizeof(self._bound),
        )
        return self._bound

    def get_rect(self) -> RECT:
        """Retrieves the dimensions of the bounding rectangle of the specified window.
        The dimensions are given in screen coordinates that are relative to the upper-left
        corner of the screen

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowrect

        :return: a RECT with top/left/bottom/right properties
        :rtype: RECT
        """
        if self._rect is None:
            self._rect = RECT()
        if not user32.GetWindowRect(self._hwnd, pointer(self._rect)):
            raise WinError(get_last_error())
        return self._rect

    def set_rect(self, rect: RECT):
        """Sets the dimensions of the bounding rectangle (Call SetWindowPos with RECT)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos

        :param rect: RECT with top/left/bottom/right properties
        """
        x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        if not user32.SetWindowPos(self._hwnd, None, x, y, w, h, 0):
            raise WinError(get_last_error())
        self._last_rect = rect

    def activate(self) -> bool:
        """Brings the thread that created current window into the foreground and activates the window"""
        return set_active_window(self)

    @property
    def last_rect(self) -> Optional[RECT]:
        return self._last_rect


def get_windows(hdst: Optional[HDESK] = None) -> Iterator[Window]:
    """Get all windows of specified/current desktop"""
    return map(Window, enum_desktop_windows(hdst))


def get_normal_windows(hdst: Optional[HDESK] = None) -> Iterator[Window]:
    """Get all normal windows of specified/current desktop

    normal windows would not include cloaked / invisible / unmaximizeable / unminimizable windows
    """
    for window in get_windows(hdst):
        style = window.get_style()
        if (
            window.title
            and not window.is_cloaked
            and WindowStyle.MAXIMIZEBOX & style
            and WindowStyle.MINIMIZEBOX & style
            and WindowStyle.VISIBLE & style
            and not WindowStyle.MINIMIZE & style
            and not window.is_evelated
        ):
            yield window


def get_active_window() -> Optional[Window]:
    """Retrieves current activated window"""
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        return Window(hwnd)


def set_active_window(window: Window) -> bool:
    """Brings the thread that created the specified window into the foreground and activates the window

    Ref: https://github.com/AutoHotkey/AutoHotkey/blob/e379b60e44d35494d4a19d1e5001f2dd38773391/source/window.cpp#L25
    """
    # simple way
    if user32.SetForegroundWindow(window.handle):
        # print("simple way works")
        return
    # well, simple way didn't work, we have to make our process Foreground
    our_thread_id = kernel32.GetCurrentThreadId()
    fore_thread_id = None
    target_thread_id = user32.GetWindowThreadProcessId(window.handle, None)

    uf = False  # attached our thread to the fore thread
    ft = False  # attached the fore thread to the target thread
    curr_fore_hwnd = user32.GetForegroundWindow()
    if curr_fore_hwnd:
        fore_thread_id = user32.GetWindowThreadProcessId(curr_fore_hwnd, None)
        if fore_thread_id and fore_thread_id != our_thread_id:
            uf = user32.AttachThreadInput(our_thread_id, fore_thread_id, True)
            # print("attach our thread to the fore thread:", uf)
        if fore_thread_id and target_thread_id and fore_thread_id != target_thread_id:
            ft = user32.AttachThreadInput(fore_thread_id, target_thread_id, True)
            # print("attach fore thread to the target thread:", ft)
    new_fore_window = None
    retry = 5
    while new_fore_window != window.handle and retry > 0:
        send_input(
            INPUT(
                type=INPUTTYPE.KEYBOARD,
                ki=KEYBDINPUT(wVk=Vk.MENU, dwFlags=KEYEVENTF.KEYUP),
            ),
            INPUT(
                type=INPUTTYPE.KEYBOARD,
                ki=KEYBDINPUT(wVk=Vk.MENU, dwFlags=KEYEVENTF.KEYUP),
            ),
        )
        user32.SetForegroundWindow(window.handle)
        new_fore_window = user32.GetForegroundWindow()
        retry -= 1
        time.sleep(0.01)
    # print(
    #     f"our: {our_thread_id}   fore: {fore_thread_id}   target{target_thread_id}  succeeded: {new_fore_window == window.handle}"
    # )
    # detach input thread
    if uf:
        user32.AttachThreadInput(our_thread_id, fore_thread_id, False)
    if ft:
        user32.AttachThreadInput(fore_thread_id, target_thread_id, False)
    # print("detached")


def minimize_active_window():
    window = get_active_window()
    if window:
        window.minimize()


def toggle_maximize_active_window():
    window = get_active_window()
    if window:
        window.toggle_maximize()


def inspect_window(window: Window):
    print()
    style = window.get_style()
    exstyle = window.get_exstyle()
    print(window.title)
    print("pid          :", window.pid)
    print("class name   :", window.class_name)
    print("exe path     :", window.exe)
    print("is_elevated  :", window.is_evelated)
    print("is_visible   :", WindowStyle.VISIBLE in style)
    print("is_minimized :", WindowStyle.MINIMIZE in style)
    print("is_cloaked   :", window.is_cloaked)
    # print("is_active    :", active_window == window)
    print("is_non_client_rending:", window.is_non_client_rendering_enable)
    rect = window.get_rect()
    print("rect         :", rect.left, rect.top, rect.right, rect.bottom)
    bound = window.get_extended_frame_bounds()
    print("bound        :", bound.left, bound.top, bound.right, bound.bottom)


if __name__ == "__main__":
    # pos = get_cursor_pos()
    # print(pos.x, pos.y)
    # hwnds = enum_windows()

    # for hwnd in hwnds:
    #   wnd = Window(hwnd)
    #   print(wnd.hwnd, wnd.title)
    # print(b'\xce\xde\xb1\xea\xcc\xe2 - \xbc\xc7\xca\xc2\xb1\xbe'.decode(locale.getpreferredencoding()))
    # windows = list(filter(lambda w: (
    #   w.is_visible and w.title and not w.is_minimized and w.is_minimizable and w.is_maximizable
    #   and not w.is_cloaked
    # ), get_windows()))
    # windows[0].set_rect(RECT(0, 0, 300, 300))
    # import time

    # time.sleep(2)
    # inspect_window(get_active_window())
    for window in get_normal_windows():
        inspect_window(window)
