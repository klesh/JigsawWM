from ctypes import *
from ctypes.wintypes import *
from typing import List, Iterator, Optional
from dataclasses import dataclass
import enum
import locale

encoding = locale.getpreferredencoding()

user32 = WinDLL("user32", use_last_error=True)
kernel32 = WinDLL("kernel32", use_last_error=True)
advapi32 = WinDLL("advapi32", use_last_error=True)
dwmapi = WinDLL("dwmapi", use_last_error=True)


_current_pos_ptr = POINT()


def get_cursor_pos() -> POINT:
    """Retrieves the position of the mouse cursor, in screen coordinates.

    :return: mouse position
    :rtype: POINT
    """
    if not user32.GetCursorPos(pointer(_current_pos_ptr)):
        raise Exception("failed to get cursor position")
    return _current_pos_ptr


def open_process_for_limited_query(pid: int) -> HANDLE:
    """Opens an existing local process object with permission to query limited information

    Ref: https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights

    :param pid: int
    :return:  process handle
    :rtype: HANDLE
    """
    PROCESS_QUERY_LIMITED_INFORMATION = DWORD(0x1000)
    hprc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not hprc:
        raise WinError(get_last_error())
    return hprc


def is_process_elevated(pid: int) -> bool:
    """Check if specified process is elevated (run in Administrator Role)

    :param pid: int
    :return: `True` if elevated, `False` otherwise
    :rtype: bool
    """
    hprc = open_process_for_limited_query(pid)
    TOKEN_QUERY = DWORD(8)
    htoken = PHANDLE()
    if not windll.advapi32.OpenProcessToken(hprc, TOKEN_QUERY, byref(htoken)):
        windll.kernel32.CloseHandle(hprc)
        return
    TOKEN_ELEVATION = INT(20)
    is_elevated = BOOL()
    returned_length = DWORD()
    if not advapi32.GetTokenInformation(
        htoken,
        TOKEN_ELEVATION,
        byref(is_elevated),
        4,
        byref(returned_length),
    ):
        raise WinError(get_last_error())
    kernel32.CloseHandle(hprc)
    kernel32.CloseHandle(htoken)
    return bool(is_elevated.value)


def get_process_exepath(pid: int) -> str:
    """Retrieves the full name of the executable image for the specified process.

    :param pid: int
    :return: the full path of the executable
    :rtype: str
    """
    hprc = open_process_for_limited_query(pid)
    buff = create_string_buffer(512)
    size = DWORD(sizeof(buff))
    if not kernel32.QueryFullProcessImageNameA(hprc, 0, buff, pointer(size)):
        kernel32.CloseHandle(hprc)
        raise WinError(get_last_error())
    kernel32.CloseHandle(hprc)
    return buff.value.decode(encoding)


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

    def __init__(self, hwnd: HWND):
        self._hwnd = hwnd

    def __eq__(self, other):
        return isinstance(other, Window) and self._hwnd == other._hwnd

    @property
    def title(self) -> str:
        """Retrieves the text of the specified window's title bar (if it has one)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtexta

        :return: text of the title bar
        :rtype: str
        """
        # length = user32.GetWindowTextLengthW(self.hwnd)
        if self._title is None:
            self._title = create_string_buffer(255)
        user32.GetWindowTextA(self._hwnd, self._title, 255)
        return self._title.value.decode(encoding)

    @property
    def class_name(self):
        """Retrieves the name of the class to which the specified window belongs.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclassnamea

        :return: class name
        :rtype: str
        """
        if self._class_name is None:  # class_name would never change
            buff = create_string_buffer(100)
            user32.GetClassNameA(self._hwnd, buff, 100)
            self._class_name = buff.value.decode(encoding)
        return self._class_name

    @property
    def exe(self):
        """Retrieves the full path of the executable

        :return: full path of the executable
        :rtype: str
        """
        if self._exepath is None:
            self._exepath = get_process_exepath(self.pid)
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
        if self.is_maximized:
            self.restore()
        else:
            self.maximize()

    @property
    def is_evelated(self):
        """Check if window is elevated (Administrator)"""
        if self._elevated is None:  # would never change
            self._elevated = is_process_elevated(self.pid)
        return self._elevated

    @property
    def is_cloaked(self) -> any:
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

    def activate(self):
        """Brings the thread that created current window into the foreground and activates the window"""
        set_active_window(self)


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
        ):
            yield window


def get_active_window() -> Optional[Window]:
    """Retrieves current activated window"""
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        return Window(hwnd)


def set_active_window(window: Window):
    """Brings the thread that created the specified window into the foreground and activates the window"""
    user32.SetForgroundWindow(window._hwnd)


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
    active_window = get_active_window()
    for window in get_normal_windows():
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
        print("is_active    :", active_window == window)
        rect = window.get_rect()
        print("rect         :", rect.top, rect.left, rect.right, rect.bottom)
