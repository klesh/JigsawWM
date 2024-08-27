"""Windows API for window management"""
import logging
import sys
import time
from ctypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Any, Dict
from os import path
from functools import cached_property
from threading import Lock

from . import process
from .sendinput import send_input, INPUT, INPUTTYPE, KEYBDINPUT, KEYEVENTF
from .vk import Vk
from .monitor import get_monitor_from_window
from .window_structs import (
  WindowStyle, WindowExStyle, ShowWindowCmd, DwmWindowAttribute,
  repr_rect
)

user32 = WinDLL("user32", use_last_error=True)
kernel32 = WinDLL("kernel32", use_last_error=True)
dwmapi = WinDLL("dwmapi", use_last_error=True)
logger = logging.getLogger(__name__)

MANAGEABLE_CLASSNAME_BLACKLIST = {
    "Shell_TrayWnd", # taskbar
    "Shell_SecondaryTrayWnd",
    "Progman", # desktop background
    "WorkerW",
}
SWP_NOACTIVATE = 0x0010
SET_WINDOW_RECT_FLAG = SWP_NOACTIVATE
GCL_HICONSM = -34
GCL_HICON = -14
ICON_SMALL = 0
ICON_BIG = 1
ICON_SMALL2 = 2
WM_GETICON = 0x7F
NOT_TILABLE_EXE_NAMES = {
    "QuickLook.exe"
}


@dataclass
class Window:
    """Represents a top-level window

    :param hwnd: HWND the window handle
    """

    handle: HWND
    restricted_rect = None
    compensated_rect = None
    restricted_actual_rect = None
    attrs: dict = field(default_factory=dict)
    restored_once = False
    minimized_by_user = False
    user_manageable = None
    unmanageable_reason: Optional[str] = None

    def __init__(self, hwnd: HWND):
        self.handle = hwnd
        self.attrs = {}

    def __eq__(self, other):
        return isinstance(other, Window) and self.handle == other.handle

    def __hash__(self):
        return hash(self.handle)

    def __repr__(self):
        marks = ' '
        if self.tilable:
            marks += 'T'
        if self.manageable:
            marks += 'M'
        if self.restricted_rect:
            marks += 'R'
        if self.minimized_by_user:
            marks += '_'
        return f"<Window id={id(self)} pid={self.pid} exe={self.exe_name} title={self.title[:10]} hwnd={self.handle}{marks}>"

    # some windows may change their style after created and there will be no event raised
    # so we need to remember the tilable state to avoid undesirable behavior.
    # i.e. Feishu meeting window initialy is not tilable, but it would become tilable after you press the "Meet now" button
    @cached_property
    def tilable(self) -> bool:
        """Check if window is tilable"""
        style = self.get_style()
        return (
            WindowStyle.SIZEBOX in style
            and WindowStyle.MAXIMIZEBOX & style and WindowStyle.MINIMIZEBOX & style
            and self.exe_name not in NOT_TILABLE_EXE_NAMES
            # and not WindowStyle.MINIMIZE & style
        )

    @property
    def manageable(self) -> bool:
        """Check if window is manageable"""
        if self.user_manageable is not None:
            return self.user_manageable
        self.unmanageable_reason = self.check_unmanageable()
        return not self.unmanageable_reason

    @manageable.setter
    def manageable(self, value):
        self.user_manageable = value

    @property
    def is_child(self) -> bool:
        """Check if window is a child window"""
        return self.parent_handle or (self.get_exstyle() & WindowExStyle.LAYERED)

    @property
    def title(self) -> str:
        """Retrieves the text of the specified window's title bar (if it has one)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtexta

        :return: text of the title bar
        :rtype: str
        """
        title = create_unicode_buffer(255)
        user32.GetWindowTextW(self.handle, title, 255)
        return str(title.value)

    @cached_property
    def class_name(self):
        """Retrieves the name of the class to which the specified window belongs.

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclassnamea

        :return: class name
        :rtype: str
        """
        buff = create_unicode_buffer(100)
        user32.GetClassNameW(self.handle, buff, 100)
        return str(buff.value)

    @cached_property
    def exe(self):
        """Retrieves the full path of the executable

        :return: full path of the executable
        :rtype: str
        """
        return process.get_exepath(self.pid)

    @cached_property
    def exe_name(self):
        """Retrieves the name of the executable"""
        exe = self.exe
        if exe:
            exe = path.basename(exe)
        return exe

    @cached_property
    def pid(self) -> int:
        """Retrieves the process id

        :return: process id
        :rtype: int
        """
        pid = DWORD()
        user32.GetWindowThreadProcessId(self.handle, pointer(pid))
        return pid.value

    @cached_property
    def parent_handle(self) -> HWND:
        """Retrieves the parent window handle"""
        return user32.GetParent(self.handle)

    @property
    def is_iconic(self) -> bool:
        """Check if window is iconic"""
        return user32.IsIconic(self.handle)

    @property
    def is_visible(self) -> bool:
        """Determines the visibility state of the specified window.

        :return: If the specified window, its parent window, its parent's parent window,
            and so forth, have the WS_VISIBLE style, the return value is `True`.
            Otherwise, the return value is `False`.
        :rtype: bool
        """
        return bool(user32.IsWindowVisible(self.handle))

    @property
    def is_zoomed(self) -> bool:
        """Check if window is maximized"""
        return user32.IsZoomed(self.handle)

    @property
    def is_fullscreen(self) -> bool:
        """Check if window is fullscreen"""
        m = get_monitor_from_window(self.handle)
        if m is None: # window is moved outside of monitors
            return False
        mr = m.get_rect()
        wr = self.get_rect()
        return mr.top == wr.top and mr.left == wr.left and mr.right == wr.right and mr.bottom == wr.bottom

    @cached_property
    def is_evelated(self):
        """Check if window is elevated (Administrator)"""
        return process.is_elevated(self.pid)

    @property
    def is_restored(self):
        """Check if window is restored"""
        return not self.is_iconic and not self.is_fullscreen and not self.is_zoomed

    @cached_property
    def dpi_awareness(self):
        """Check if window is api aware"""
        return process.get_process_dpi_awareness(self.pid)

    @property
    def is_cloaked(self) -> bool:
        """Check if window is cloaked (DWM)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        """
        cloaked = INT()
        windll.dwmapi.DwmGetWindowAttribute(
            self.handle,
            DwmWindowAttribute.DWMWA_CLOAKED,
            pointer(cloaked),
            sizeof(cloaked),
        )
        return bool(cloaked.value)

    @cached_property
    def is_toplevel(self) -> bool:
        """Retrieve if the window is top level"""
        return user32.IsTopLevelWindow(self.handle)

    @cached_property
    def icon_handle(self) -> HANDLE:
        """Retrieves the icon handle of the specified window"""
        handle = user32.SendMessageW(self.handle, WM_GETICON, ICON_SMALL2, 0)
        if not handle:
            handle = user32.SendMessageW(self.handle, WM_GETICON, ICON_SMALL, 0)
        if not handle:
            handle = user32.SendMessageW(self.handle, WM_GETICON, ICON_BIG, 0)
        if not handle:
            handle = user32.GetClassLongPtrW(self.handle, GCL_HICONSM)
        if not handle:
            handle = user32.GetClassLongPtrW(self.handle, GCL_HICON)
        return handle

    def check_unmanageable(self) -> str:
        """Check if window is a app window which could be managed"""
        if not self.is_toplevel:
            return "not a top-level window"
        if self.is_cloaked:
            return "%s unmanageable: cloaked"
        if self.class_name in MANAGEABLE_CLASSNAME_BLACKLIST:
            return "blacklisted"
        exstyle = self.get_exstyle()
        if WindowExStyle.TRANSPARENT in exstyle:
            return "WindowExStyle.TRANSPARENT"
        if process.is_elevated(self.pid):
            return "admin window"
        if not self.exe:
            return "no executable path"
        return None

    def get_attr(self, key: str) -> Any:
        """Retrieve attribute"""
        if key not in self.attrs:
            logger.warning("%s doesn't contain attr %s", self, key)
        return self.attrs.get(key)

    def get_style(self) -> WindowStyle:
        """Retrieves style

        :return: window style
        :rtype: WindowStyle
        """
        return WindowStyle(user32.GetWindowLongA(self.handle, -16))

    def get_exstyle(self) -> WindowExStyle:
        """Retrieves ex-style

        :return: window ex-style
        :rtype: ExWindowStyle
        """
        return WindowExStyle(user32.GetWindowLongA(self.handle, -20))

    def minimize(self):
        """Minimizes the specified window and activates the next top-level window in the Z order."""
        self.show_window(ShowWindowCmd.SW_MINIMIZE)

    def maximize(self):
        """Activates the window and displays it as a maximized window."""
        self.show_window(ShowWindowCmd.SW_MAXIMIZE)

    def restore(self):
        """Activates and displays the window. If the window is minimized or maximized,
        the system restores it to its original size and position."""
        self.show_window(ShowWindowCmd.SW_RESTORE)

    def toggle_maximize(self):
        """Toggle maximize style"""
        if self.is_zoomed:
            self.restore()
        else:
            self.maximize()

    def exists(self) -> bool:
        """Check if window exists"""
        return user32.IsWindow(self.handle)

    def get_extended_frame_bounds(self) -> RECT:
        """Retrieves extended frame bounds

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        """
        bound = RECT()
        windll.dwmapi.DwmGetWindowAttribute(
            self.handle,
            DwmWindowAttribute.DWMWA_EXTENDED_FRAME_BOUNDS,
            pointer(bound),
            sizeof(bound),
        )
        return bound

    def get_rect(self) -> RECT:
        """Retrieves the dimensions of the bounding rectangle of the specified window.
        The dimensions are given in screen coordinates that are relative to the upper-left
        corner of the screen

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowrect

        :return: a RECT with top/left/bottom/right properties
        :rtype: RECT
        """
        rect = RECT()
        if not user32.GetWindowRect(self.handle, pointer(rect)):
            raise WinError(get_last_error())
        return rect

    def set_rect(self, rect: RECT):
        """Sets the dimensions of the bounding rectangle (Call SetWindowPos with RECT)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos

        :param rect: RECT with top/left/bottom/right properties
        """
        logger.debug("set rect to %s for %s", repr_rect(rect), self.title)
        x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        if not user32.SetWindowPos(self.handle, None, x, y, w, h, SET_WINDOW_RECT_FLAG):
            raise WinError(get_last_error())

    def set_restrict_rect(self, rect: RECT):
        """Set the restricted rect"""
        if not self.is_restored:
            self.restore()
            self.restored_once = True
        self.set_rect(rect)
        self.restricted_rect = rect
        self.compensated_rect = None
        if self.dpi_awareness == process.ProcessDpiAwareness.PROCESS_PER_MONITOR_DPI_AWARE:
            # seems like the `get_extended_frame_bounds` would return physical size
            # for DPI unware window, skip them for now
            # TODO: convert physical size to logical size for DPI unware window
            # compensation
            r = self.get_rect()
            b = self.get_extended_frame_bounds()
            self.compensated_rect = RECT(
                round(rect.left + r.left - b.left),
                round(rect.top + r.top - b.top),
                round(rect.right + r.right - b.right),
                round(rect.bottom + r.bottom - b.bottom),
            )
            self.set_rect(self.compensated_rect)
        self.restricted_actual_rect = self.get_rect()

    def restrict(self):
        """Restrict the window to the restricted rect"""
        logger.debug("restricting %s", self)
        if self.restored_once and not self.is_restored:
            # user intentionally maximize the window, don't restrict it
            return
        self.restored_once = True
        if self.restricted_actual_rect:
            r1 = self.restricted_actual_rect
            r2 = self.get_rect()
            if r1.left == r2.left and r1.top == r2.top and r1.right == r2.right and r1.bottom == r2.bottom:
                return
            self.set_rect(self.compensated_rect or self.restricted_rect)
            logger.debug("restrict to %s for %s", repr_rect(self.restricted_rect), self.title)

    def unrestrict(self):
        """Unrestrict the window"""
        self.restricted_rect = None
        self.restricted_actual_rect = None

    def shrink(self, margin: int=20):
        """Shrink the window by margin"""
        logger.info("shrink %s by %d", self.title, margin)
        rect = self.get_rect()
        rect.left += margin
        rect.top += margin
        rect.right -= margin
        rect.bottom -= margin
        self.set_rect(rect)

    def activate(self) -> bool:
        """Brings the thread that created current window into the foreground and activates the window"""
        # move cursor to the center of the window
        rect = self.get_rect()
        x = rect.left + (rect.right - rect.left) / 2
        y = rect.top + (rect.bottom - rect.top) / 2
        user32.SetCursorPos(int(x), int(y))
        # activation
        # simple way
        if user32.SetForegroundWindow(self.handle):
            return
        # well, simple way didn't work, we have to make our process Foreground
        our_thread_id = kernel32.GetCurrentThreadId()
        fore_thread_id = None
        target_thread_id = user32.GetWindowThreadProcessId(self.handle, None)

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
        while new_fore_window != self.handle and retry > 0:
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
            user32.SetForegroundWindow(self.handle)
            new_fore_window = user32.GetForegroundWindow()
            retry -= 1
            time.sleep(0.01)
        logger.debug("set_active_window: %s", new_fore_window == self.handle)
        # detach input thread
        if uf:
            user32.AttachThreadInput(our_thread_id, fore_thread_id, False)
        if ft:
            user32.AttachThreadInput(fore_thread_id, target_thread_id, False)

    def show_window(self, cmd: ShowWindowCmd):
        """Show window"""
        user32.ShowWindow(self.handle, cmd)

    def show(self):
        """Shows the window"""
        self.show_window(ShowWindowCmd.SW_SHOWNA)

    def hide(self):
        """Hides the window"""
        self.show_window(ShowWindowCmd.SW_HIDE)

    def toggle(self, show: bool):
        """Toggle window visibility"""
        # fusion360 object selection window not functioning properly after hidden and show, unless minimized then restored
        # notepad status bar not positioning properly unless it get restored before show
        if not show:
            return self.hide()
        elif not self.minimized_by_user and self.exe_name in {"Fusion360.exe"}:
            self.minimize()
            self.restore()
        return self.show()

    @cached_property
    def root_window(self) -> "Window":
        """Retrieve the root window"""
        root_window = self
        while root_window.parent_handle:
            root_window = lookup_window(root_window.parent_handle)
        return root_window

    def find_children(self) -> List["Window"]:
        """Retrieve the children windows"""
        # process children windows
        def find_children(w: Window):
            children = set(filter_windows(lambda x: x.parent_handle == w.handle))
            for child in children:
                children |= find_children(child)
            return children
        return find_children(self)

    def inspect(self, file=sys.stdout):
        """Inspect window and print the information to the file"""
        if not self.exists():
            print("window doesn't exist anymore")
            return
        print(self, file=file)
        print("pid          :", self.pid, file=file)
        print("class name   :", self.class_name, file=file)
        print("exe path     :", self.exe, file=file)
        style = self.get_style()
        style_flags = []
        for s in WindowStyle:
            if s in style:
                style_flags.append(s.name)
        print("style        :", ", ".join(style_flags), file=file)
        exstyle = self.get_exstyle()
        exstyle_flags = []
        for s in WindowExStyle:
            if s in exstyle:
                exstyle_flags.append(s.name)
        print("exstyle      :", ", ".join(exstyle_flags), file=file)
        for k, v in self.attrs.items():
            print(f"attr({k}): {v}", file=file)
        rect = self.get_rect()
        print("rect         :", rect.left, rect.top, rect.right, rect.bottom, file=file)
        bound = self.get_extended_frame_bounds()
        print("bound        :", bound.left, bound.top, bound.right, bound.bottom, file=file)
        if self.restricted_rect:
            r = self.restricted_rect
            print("restricted   :", r.left, r.top, r.right, r.bottom, file=file)
        print("is_evelated  :", self.is_evelated, file=file)
        print("is_toplevel  :", self.is_toplevel, file=file)
        print("is_cloaked   :", self.is_cloaked, file=file)
        print("is_visible   :", self.is_visible, file=file)
        print("is_iconic    :", self.is_iconic, file=file)
        print("is_resored   :", self.is_restored, file=file)
        print("unmanageable :", self.unmanageable_reason, file=file)
        print("parent       :", self.parent_handle, file=file)
        print("dpi_awareness:", self.dpi_awareness.name, file=file)


_seen_windows_lock = Lock()
_seen_windows: Dict[HWND, Window] = {}

def get_seen_windows() -> Dict[HWND, Window]:
    """Retrieve all windows that ever been seen"""
    return _seen_windows

def replace_seen_windows(data: Dict[HWND, Window]):
    """Replace seen windows"""
    global _seen_windows # pylint: disable=global-statement
    with _seen_windows_lock:
        _seen_windows = data

def lookup_window(hwnd: Optional[HWND]) -> Optional[Window]:
    """Lookup window"""
    if not hwnd:
        raise ValueError("hwnd is None")
    if hwnd not in _seen_windows:
        with _seen_windows_lock:
            if hwnd not in _seen_windows:
                window = Window(hwnd)
                _seen_windows[hwnd] = window
    return _seen_windows[hwnd]

def filter_windows(check: Callable[[Window], bool]) -> List[Window]:
    """Filter app windows of the current desktop"""

    windows = set()
    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(hwnd: HWND, _lParam: LPARAM) -> BOOL: # pylint: disable=invalid-name
        window = lookup_window(hwnd)
        try:
            if check(window):
                windows.add(window)
        except StopIteration:
            return False
        return True

    if not user32.EnumWindows(enum_windows_proc, None):
        last_error = get_last_error()
        if last_error:
            raise WinError(last_error)
    return windows

def get_window_from_pos(x, y: int) -> Optional[Window]:
    """Retrieves the window at the specified position"""
    hwnd = user32.WindowFromPoint(POINT(int(x), int(y)))
    if hwnd:
        return lookup_window(user32.GetAncestor(hwnd, 2))

def get_active_window() -> Optional[Window]:
    """Retrieves current activated window"""
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        return lookup_window(hwnd)

###
### helper functions
###

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

###
### debugging
###

if __name__ == "__main__":
    if len(sys.argv)  > 1:
        param = sys.argv[1]
        if param.isdigit():
            lookup_window(int(param)).inspect()
        elif param == "app":
            for wd in filter_windows(lambda w: w.manageable and w.is_visible):
                print()
                wd.inspect()
        elif param == "exe":
            for wd in filter_windows(lambda w: w.exe_name.lower() == sys.argv[2].lower()):
                print()
                wd.inspect()
        elif param == "unhide":
            Window(int(sys.argv[2])).show()
        elif param == "layered":
            for wd in filter_windows(lambda w: w.manageable and w.is_visible and (w.get_exstyle() & WindowExStyle.LAYERED)):
                print()
                wd.inspect()
    else:
        time.sleep(2)
        get_active_window().inspect()