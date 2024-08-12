"""Windows API for window management"""
import logging
import sys
import time
from ctypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from dataclasses import dataclass
from io import StringIO
from typing import Callable, List, Optional, Iterable
from os import path
from functools import cached_property

from . import process
from .sendinput import send_input, INPUT, INPUTTYPE, KEYBDINPUT, KEYEVENTF
from .vk import Vk
from .window_structs import (
  WindowStyle, WindowExStyle, EnumCheckResult, ShowWindowCmd, DwmWindowAttribute,
  repr_rect
)

user32 = WinDLL("user32", use_last_error=True)
kernel32 = WinDLL("kernel32", use_last_error=True)
dwmapi = WinDLL("dwmapi", use_last_error=True)

logger = logging.getLogger(__name__)


def iter_windows(
    cb: Callable[[HWND], bool]
) -> List[HWND]:
    """Iterate all top-level windows on current desktop.

    :param cb: handle each window handle
    """
    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(hwnd: HWND, _lParam: LPARAM) -> BOOL: # pylint: disable=invalid-name
        return cb(hwnd)

    if not user32.EnumWindows(enum_windows_proc, None):
        last_error = get_last_error()
        if last_error:
            raise WinError(last_error)

def enum_windows(
    check: Optional[Callable[[HWND], EnumCheckResult]] = None
) -> List[HWND]:
    """Returns a List of all top-level windows on current desktop.

    :param check: optional, to determinate if a HWN should be added to list, or stop iteration

    :return: list of window handles
    :rtype: List[HWND]
    """
    check = check or (lambda _: 1)
    hwnds = []

    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(hwnd: HWND, _lParam: LPARAM) -> BOOL: # pylint: disable=invalid-name
        r = check(hwnd)
        if EnumCheckResult.CAPTURE in r:
            hwnds.append(hwnd)
        return EnumCheckResult.STOP not in r

    if not user32.EnumWindows(enum_windows_proc, None):
        last_error = get_last_error()
        if last_error:
            raise WinError(last_error)
    return hwnds

def get_foreground_window() -> HWND:
    """Retrieves foreground window handle"""
    return user32.GetForegroundWindow()


def get_window_style(hwnd: HWND) -> WindowStyle:
    """Retrieves style of the specified window handle"""
    return WindowStyle(user32.GetWindowLongA(hwnd, -16))


def get_window_exstyle(hwnd: HWND) -> WindowExStyle:
    """Retrieves ex-style of the specified window handle"""
    return WindowExStyle(user32.GetWindowLongA(hwnd, -20))


def show_window(hwnd: HWND, cmd: ShowWindowCmd):
    """Show window"""
    user32.ShowWindow(hwnd, cmd)


def minimize_window(hwnd: HWND):
    """Minimize window"""
    show_window(hwnd, ShowWindowCmd.SW_MINIMIZE)


def maximize_window(hwnd: HWND):
    """Maximize window"""
    show_window(hwnd, ShowWindowCmd.SW_MAXIMIZE)


def restore_window(hwnd: HWND):
    """Restore window"""
    show_window(hwnd, ShowWindowCmd.SW_RESTORE)


def get_window_title(hwnd: HWND) -> str:
    """Retrieves window title"""
    title = create_unicode_buffer(255)
    user32.GetWindowTextW(hwnd, title, 255)
    return str(title.value)


def get_window_class_name(hwnd: HWND) -> str:
    """Retrieves window class name"""
    buff = create_unicode_buffer(100)
    user32.GetClassNameW(hwnd, buff, 100)
    return str(buff.value)


def get_window_pid(hwnd: HWND) -> DWORD:
    """Retrieves id of the process that owns the window"""
    pid = DWORD()
    user32.GetWindowThreadProcessId(hwnd, pointer(pid))
    return pid


def is_window_visible(hwnd: HWND) -> bool:
    """Check if window is visible"""
    return bool(user32.IsWindowVisible(hwnd))


def is_window_cloaked(hwnd: HWND) -> bool:
    """Check if window is cloaked"""
    cloaked = INT()
    windll.dwmapi.DwmGetWindowAttribute(
        hwnd,
        DwmWindowAttribute.DWMWA_CLOAKED,
        pointer(cloaked),
        sizeof(cloaked),
    )
    return bool(cloaked.value)


def is_window(hwnd: HWND) -> bool:
    """Check if handle is a window handle"""
    return user32.IsWindow(hwnd)


def is_toplevel_window(hwnd: HWND) -> bool:
    """Check if window is a top-level window"""
    return user32.IsTopLevelWindow(hwnd)


def is_app_window(hwnd: HWND, style: Optional[WindowExStyle] = None) -> bool:
    """Check if window is a app window (user mode / visible / resizable)"""
    style = style or get_window_style(hwnd)
    pid = get_window_pid(hwnd)
    return bool(
        WindowStyle.VISIBLE in style
        and (WindowStyle.MAXIMIZEBOX & style or WindowStyle.MINIMIZEBOX & style)
        and is_toplevel_window(hwnd)
        and not user32.GetParent(hwnd)
        and not is_window_cloaked(hwnd)
        and not process.is_elevated(pid)
        and process.get_exepath(pid)
    )


def get_window_extended_frame_bounds(hwnd: HWND) -> RECT:
    """Retrieve extended frame bounds of the specified window"""
    bound = RECT()
    windll.dwmapi.DwmGetWindowAttribute(
        hwnd,
        DwmWindowAttribute.DWMWA_EXTENDED_FRAME_BOUNDS,
        pointer(bound),
        sizeof(bound),
    )
    return bound


def get_window_rect(hwnd: HWND) -> RECT:
    """Retrieves rect(position/size) of the specified window"""
    rect = RECT()
    if not user32.GetWindowRect(hwnd, pointer(rect)):
        raise WinError(get_last_error())
    return rect


SWP_NOACTIVATE = 0x0010
SET_WINDOW_RECT_FLAG = SWP_NOACTIVATE


def set_window_rect(hwnd: HWND, rect: RECT):
    """Move/resize specified window"""
    x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    if not user32.SetWindowPos(hwnd, None, x, y, w, h, SET_WINDOW_RECT_FLAG):
        raise WinError(get_last_error())


GCL_HICONSM = -34
GCL_HICON = -14

ICON_SMALL = 0
ICON_BIG = 1
ICON_SMALL2 = 2

WM_GETICON = 0x7F


def get_window_icon(hwnd: HWND) -> HANDLE:
    """Retrieves the icon handle of the specified window"""
    handle = user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL2, 0)
    if not handle:
        handle = user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0)
    if not handle:
        handle = user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0)
    if not handle:
        handle = user32.GetClassLongPtrW(hwnd, GCL_HICONSM)
    if not handle:
        handle = user32.GetClassLongPtrW(hwnd, GCL_HICON)
    return handle


@dataclass
class Window:
    """Represents a top-level window

    :param hwnd: HWND the window handle
    """

    _hwnd: HWND
    _restricted_rect = None
    _restricted_actual_rect = None
    attrs: dict = None

    def __init__(self, hwnd: HWND):
        self._hwnd = hwnd
        self.attrs = {}

    def __eq__(self, other):
        return isinstance(other, Window) and self._hwnd == other._hwnd

    def __hash__(self):
        return hash(self._hwnd)

    def __repr__(self):
        exe = self.exe
        if exe:
            exe = path.basename(exe)
        return f"<Window exe={exe} title={self.title[:10]} hwnd={self._hwnd}{' tilable' if self.is_tilable else ''}>"

    # some windows may change their style after created and there will be no event raised
    # so we need to remember the tilable state to avoid undesirable behavior.
    # i.e. Feishu meeting window initialy is not tilable, but it would become tilable after you press the "Meet now" button
    @cached_property
    def is_tilable(self) -> bool:
        """Check if window is tilable"""
        style = self.get_style()
        return (
            WindowStyle.SIZEBOX in style
            and WindowStyle.MAXIMIZEBOX & style and WindowStyle.MINIMIZEBOX & style
            # and not WindowStyle.MINIMIZE & style
        )

    @property
    def handle(self) -> HWND:
        """Retrieves the window handle"""
        return self._hwnd

    @property
    def title(self) -> str:
        """Retrieves the text of the specified window's title bar (if it has one)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtexta

        :return: text of the title bar
        :rtype: str
        """
        return get_window_title(self._hwnd)

    @property
    def class_name(self):
        """Retrieves the name of the class to which the specified window belongs.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclassnamea

        :return: class name
        :rtype: str
        """
        return get_window_class_name(self._hwnd)

    @property
    def exe(self):
        """Retrieves the full path of the executable

        :return: full path of the executable
        :rtype: str
        """
        return process.get_exepath(self.pid)

    @property
    def pid(self) -> int:
        """Retrieves the process id

        :return: process id
        :rtype: int
        """
        return get_window_pid(self._hwnd)

    @property
    def is_iconic(self) -> bool:
        """Check if window is iconic"""
        return user32.IsIconic(self._hwnd)

    @property
    def is_visible(self) -> bool:
        """Determines the visibility state of the specified window.

        :return: If the specified window, its parent window, its parent's parent window,
            and so forth, have the WS_VISIBLE style, the return value is `True`.
            Otherwise, the return value is `False`.
        :rtype: bool
        """
        return is_window_visible(self._hwnd) and not self.is_cloaked and not self.is_iconic

    @property
    def is_maximized(self) -> bool:
        """Check if window is maximized"""
        return self.get_style() & WindowStyle.MAXIMIZE

    @property
    def is_minimized(self) -> bool:
        """Check if window is minimized"""
        return not WindowStyle.MINIMIZE & self.get_style()

    @property
    def is_evelated(self):
        """Check if window is elevated (Administrator)"""
        return process.is_elevated(self.pid)

    @property
    def dpi_awareness(self):
        """Check if window is api aware"""
        return process.get_process_dpi_awareness(self.pid)

    @property
    def is_cloaked(self) -> bool:
        """Check if window is cloaked (DWM)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        """
        return is_window_cloaked(self._hwnd)

    @property
    def icon_handle(self) -> HANDLE:
        """Retrieves the icon handle of the specified window"""
        return get_window_icon(self._hwnd)

    def get_style(self) -> WindowStyle:
        """Retrieves style

        :return: window style
        :rtype: WindowStyle
        """
        return get_window_style(self._hwnd)

    def get_exstyle(self) -> WindowExStyle:
        """Retrieves ex-style

        :return: window ex-style
        :rtype: ExWindowStyle
        """
        return get_window_exstyle(self._hwnd)

    def minimize(self):
        """Minimizes the specified window and activates the next top-level window in the Z order."""
        minimize_window(self._hwnd)

    def maximize(self):
        """Activates the window and displays it as a maximized window."""
        maximize_window(self._hwnd)

    def restore(self):
        """Activates and displays the window. If the window is minimized or maximized,
        the system restores it to its original size and position."""
        restore_window(self._hwnd)

    def toggle_maximize(self):
        """Toggle maximize style"""
        if self.is_maximized:
            self.restore()
        else:
            self.maximize()

    def exists(self) -> bool:
        """Check if window exists"""
        return is_window(self._hwnd)

    def get_extended_frame_bounds(self) -> RECT:
        """Retrieves extended frame bounds

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        """
        return get_window_extended_frame_bounds(self._hwnd)

    def get_rect(self) -> RECT:
        """Retrieves the dimensions of the bounding rectangle of the specified window.
        The dimensions are given in screen coordinates that are relative to the upper-left
        corner of the screen

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowrect

        :return: a RECT with top/left/bottom/right properties
        :rtype: RECT
        """
        return get_window_rect(self._hwnd)

    def set_rect(self, rect: RECT):
        """Sets the dimensions of the bounding rectangle (Call SetWindowPos with RECT)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos

        :param rect: RECT with top/left/bottom/right properties
        """
        logger.debug("set rect to %s for %s", repr_rect(rect), self.title)
        if self.is_maximized:
            self.restore()
        set_window_rect(self._hwnd, rect)
        self._restricted_rect = rect

    def set_restrict_rect(self, rect: RECT):
        """Set the restricted rect"""
        self.set_rect(rect)
        self._restricted_rect = rect
        self._restricted_actual_rect = self.get_rect()

    def restrict(self):
        """Restrict the window to the restricted rect"""
        if self._restricted_actual_rect:
            r1 = self._restricted_actual_rect
            r2 = self.get_rect()
            if r1.left == r2.left and r1.top == r2.top and r1.right == r2.right and r1.bottom == r2.bottom:
                return
            self.set_rect(self._restricted_rect)
            logger.debug("restrict to %s for %s", repr_rect(self._restricted_rect), self.title)

    def unrestrict(self):
        """Unrestrict the window"""
        self._restricted_rect = None
        self._restricted_actual_rect = None

    def shrink(self, margin: int=20):
        """Shrink the window by margin"""
        logger.info("shrink %s by %d", self.title, margin)
        rect = self.get_rect()
        rect.left += margin
        rect.top += margin
        rect.right -= margin
        rect.bottom -= margin
        set_window_rect(self._hwnd, rect)

    def activate(self) -> bool:
        """Brings the thread that created current window into the foreground and activates the window"""
        # move cursor to the center of the window
        rect = self.get_rect()
        x = rect.left + (rect.right - rect.left) / 2
        y = rect.top + (rect.bottom - rect.top) / 2
        user32.SetCursorPos(int(x), int(y))
        return set_active_window(self)

    def show(self):
        """Shows the window"""
        user32.ShowWindow(self._hwnd, ShowWindowCmd.SW_SHOWNA)

    def hide(self):
        """Hides the window"""
        user32.ShowWindow(self._hwnd, ShowWindowCmd.SW_HIDE)

    def toggle(self, show: bool):
        """Toggle window visibility"""
        user32.ShowWindow(self._hwnd,  ShowWindowCmd.SW_SHOWNA if show else ShowWindowCmd.SW_HIDE)


def get_app_windows() -> List[Window]:
    """Get all app windows of the current desktop"""
    return map(Window, enum_windows(
        lambda hwnd: EnumCheckResult.CAPTURE
        if is_app_window(hwnd)
        else EnumCheckResult.SKIP
    ))


def get_window_from_pos(x, y: int) -> Optional[Window]:
    """Retrieves the window at the specified position"""
    hwnd = user32.WindowFromPoint(POINT(int(x), int(y)))
    if hwnd:
        return Window(user32.GetAncestor(hwnd, 2))


def get_active_window() -> Optional[Window]:
    """Retrieves current activated window"""
    hwnd = get_foreground_window()
    if hwnd:
        return Window(hwnd)


def set_active_window(window: Window) -> bool:
    """Brings the thread that created the specified window into the foreground
       and activates the window

    Ref: https://github.com/AutoHotkey/AutoHotkey/blob/e379b60e44d35494d4a19d1e5001f2dd38773391/source/window.cpp#L25
    """
    # simple way
    if user32.SetForegroundWindow(window.handle):
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
        if fore_thread_id and target_thread_id and fore_thread_id != target_thread_id:
            ft = user32.AttachThreadInput(fore_thread_id, target_thread_id, True)
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
    logger.debug("set_active_window: %s", new_fore_window == window.handle)
    # detach input thread
    if uf:
        user32.AttachThreadInput(our_thread_id, fore_thread_id, False)
    if ft:
        user32.AttachThreadInput(fore_thread_id, target_thread_id, False)


def minimize_active_window():
    """Minize active window"""
    window = get_active_window()
    if window:
        window.minimize()


def toggle_maximize_active_window():
    """Maximize/Unmaximize active window"""
    window = get_active_window()
    if window:
        window.toggle_maximize()

def top_most_window(windows: Iterable[Window]) -> Optional[Window]:
    """Get the top most window from the list of windows"""
    hwnd = user32.GetTopWindow(user32.GetDesktopWindow())
    while hwnd:
        if Window(hwnd) in windows:
            for w in windows:
                if w.handle == hwnd:
                    return w
        hwnd = user32.GetWindow(hwnd, 2)
    return None

def sprint_window(hwnd: HWND) -> str:
    """Inspect window and return the information as string"""
    f = StringIO()
    inspect_window(hwnd, file=f)
    return f.getvalue()


def inspect_window(hwnd: HWND, file=sys.stdout):
    """Inspect window and print the information to the file"""
    print(file=file)
    window = Window(hwnd)
    if not window.exists():
        print("window doesn't exist anymore")
        return
    print("hwnd         :", window.handle, file=file)
    print("title        :", window.title, file=file)
    print("pid          :", window.pid, file=file)
    print("class name   :", window.class_name, file=file)
    print("exe path     :", window.exe, file=file)
    style = window.get_style()
    style_flags = []
    for s in WindowStyle:
        if s in style:
            style_flags.append(s.name)
    print("style        :", ", ".join(style_flags), file=file)
    exstyle = window.get_exstyle()
    exstyle_flags = []
    for s in WindowExStyle:
        if s in exstyle:
            exstyle_flags.append(s.name)
    print("exstyle      :", ", ".join(exstyle_flags), file=file)
    print("is_cloaked   :", window.is_cloaked, file=file)
    rect = window.get_rect()
    print("rect         :", rect.left, rect.top, rect.right, rect.bottom, file=file)
    bound = window.get_extended_frame_bounds()
    print("bound        :", bound.left, bound.top, bound.right, bound.bottom, file=file)
    print("is_app_window:", is_app_window(hwnd), file=file)
    print("is_evelated  :", window.is_evelated, file=file)
    print("is_iconic    :", user32.IsIconic(hwnd), file=file)
    print("visible      :", user32.IsWindowVisible(hwnd), file=file)
    print("parent       :", user32.GetParent(hwnd), file=file)
    print("dpi_awareness:", window.dpi_awareness.name, file=file)


def inspect_active_window(hwnd=None):
    """Inspect active window and show the information in a message box"""
    text = sprint_window(hwnd or get_foreground_window())
    print(text)
    # messagebox.showinfo("JigsawWM", text)


if __name__ == "__main__":
    # import time

    # handle = get_window_icon(get_foreground_window())
    # from PySide6.QtGui import QIcon, QImage, QPixmap

    # QImage.fromHICON(handle).save("icon.png")

    # QIcon.fromData(handle).pixmap(32, 32).save("icon.png")
    # print(QPixmap.loadFromData(handle))
    time.sleep(2)
    inspect_active_window()
    # app_windows =list(get_app_windows())
    # top_window = top_most_window(app_windows)
    # inspect_window(131638)
    # inspect_active_window(HWND(4196926))
    # for wd in get_app_windows():
    #     inspect_window(wd.handle)
    # for win in get_windows():
    #     inspect_window(win)
