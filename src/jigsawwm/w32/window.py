"""Windows API for window management"""

import enum
import logging
import sys
import time
from ctypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from dataclasses import dataclass, field
from functools import cached_property, cmp_to_key
from os import path
from typing import Any, Callable, Iterable, Optional, Set

from . import process
from .monitor import Monitor, monitor_from_window
from .sendinput import INPUT, INPUTTYPE, KEYBDINPUT, KEYEVENTF, send_input
from .vk import Vk
from .window_structs import (
    DwmWindowAttribute,
    Rect,
    ShowWindowCmd,
    WindowExStyle,
    WindowStyle,
)

user32 = WinDLL("user32", use_last_error=True)
kernel32 = WinDLL("kernel32", use_last_error=True)
dwmapi = WinDLL("dwmapi", use_last_error=True)
logger = logging.getLogger(__name__)

MANAGEABLE_CLASSNAME_BLACKLIST = {
    "Shell_TrayWnd",  # taskbar
    "Shell_SecondaryTrayWnd",
    "Progman",  # desktop background
    "WorkerW",
    "IME",
    "Default IME",
    "MSCTFIME UI",
}
APPLICABLE_EXE_BLACKLIST = {
    "msedge.exe",  # stupid copilot
    "msedgewebview2.exe",  # this shit would display a invisible widow and hide it right away, what the heck
    # "msrdc.exe",  # WSL
    # "wslhost.exe",
}
SWP_NOACTIVATE = 0x0010
SET_WINDOW_RECT_FLAG = SWP_NOACTIVATE
GCL_HICONSM = -34
GCL_HICON = -14
ICON_SMALL = 0
ICON_BIG = 1
ICON_SMALL2 = 2
WM_GETICON = 0x7F
NOT_TILABLE_EXE_NAMES = {"QuickLook.exe"}


class InsertAfter(enum.IntEnum):
    """https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos?redirectedfrom=MSDN"""

    HWND_BOTTOM = 1
    HWND_NOTOPMOST = -2
    HWND_TOP = 0
    HWND_TOPMOST = -1


@dataclass
class Window:
    """Represents a top-level window

    :param hwnd: HWND the window handle
    """

    handle: HWND
    restricted_rect: Rect = None
    compensated_rect: Rect = None
    restricted_actual_rect: Rect = None
    attrs: dict = field(default_factory=dict)
    unapplicable_reason: Optional[str] = None
    unmanageable_reason: Optional[str] = None
    untilable_reason: Optional[str] = None
    parent: Optional["Window"] = None
    manageable_children: Set["Window"] = None
    off: bool = False
    original_rect: Optional[Rect] = None

    def __init__(self, hwnd: HWND):
        self.handle = hwnd
        self.attrs = {}
        self.manageable_children = set()

    def __eq__(self, other):
        return isinstance(other, Window) and self.handle == other.handle

    def __hash__(self):
        return hash(self.handle)

    def __repr__(self):
        marks = ""
        if self.tilable:
            marks += "T"
        if self.manageable:
            marks += "M"
        if self.restricted_rect:
            marks += "R"
        if marks:
            marks = f"({marks})"
        return f"<Window hwnd={self.handle} pid={self.pid} exe={self.exe_name} title={self.title[:10]} child={len(self.manageable_children)}{marks}>"

    # some windows may change their style after created and there will be no event raised
    # so we need to remember the tilable state to avoid undesirable behavior.
    # i.e. Feishu meeting window initialy is not tilable, but it would become tilable after you press the "Meet now" button
    @cached_property
    def tilable(self) -> bool:
        """Check if window is tilable"""
        self.untilable_reason = self.check_untilable()
        return not self.untilable_reason

    def check_untilable(self):
        """Check if window is tilable"""
        style = self.get_style()
        if WindowStyle.SIZEBOX not in style:
            return "SIZEBOX not in style"
        if WindowStyle.MAXIMIZEBOX & style == 0:
            return "MAXIMIZEBOX not in style"
        if WindowStyle.MINIMIZEBOX & style == 0:
            return "MINIMIZEBOX not in style"
        if not self.is_root_window:
            return "not a root window"
        if self.exe_name in NOT_TILABLE_EXE_NAMES:
            return "exe_name blacklisted"
        return None

    @cached_property
    def manageable(self) -> bool:
        """Check if window is manageable"""
        self.unmanageable_reason = self.check_unmanageable()
        return not self.unmanageable_reason

    def check_unmanageable(self) -> str:
        """Check if window is a app window which could be managed"""
        if not self.applicable:
            return "not applicable"
        if self.is_modal_window:
            return None
        # all the following windows should be manageable
        #
        # dbeaver preference window
        # style        : BORDER, CLIPCHILDREN, CLIPSIBLINGS, DLGFRAME, MAXIMIZEBOX, POPUP, SIZEBOX, SYSMENU, VISIBLE
        #
        # fusion360 preference window
        # style        : BORDER, CLIPCHILDREN, CLIPSIBLINGS, DLGFRAME, POPUP, SIZEBOX, SYSMENU, VISIBLE
        #
        # obsidian
        # style        : BORDER, CLIPSIBLINGS, DLGFRAME, GROUP, MAXIMIZEBOX, SIZEBOX, VISIBLE
        #
        # feishu meeting window
        # style        : CLIPCHILDREN, CLIPSIBLINGS, GROUP, MAXIMIZEBOX, SIZEBOX, SYSMENU, VISIBLE
        #
        # NOT manage/tilable fusion360 object selector
        # style        : CLIPCHILDREN, CLIPSIBLINGS, POPUP, VISIBLE
        style = self.get_style()
        if WindowStyle.SIZEBOX not in style:
            return "SIZEBOX not in style"
        if self.is_cloaked:
            return "%s cloaked"
        if self.class_name in MANAGEABLE_CLASSNAME_BLACKLIST:
            return "blacklisted"
        exstyle = self.get_exstyle()
        if WindowExStyle.TRANSPARENT in exstyle:
            return "WindowExStyle.TRANSPARENT"
        return None

    @cached_property
    def applicable(self):
        """Retrieve if window is rule applicable"""
        self.unapplicable_reason = self.check_unapplicable()
        return not self.unapplicable_reason

    def check_unapplicable(self):
        """Check if window can be applied with rule"""
        if not self.is_toplevel:
            return "not a top-level window"
        if not self.exe:
            return "no executable path"
        if self.exe_name in APPLICABLE_EXE_BLACKLIST:
            return "exe blacklisted"
        if process.is_elevated(self.pid):
            return "admin window"
        return None

    @cached_property
    def is_modal_window(self) -> bool:
        """Check if window is a modal window"""
        if not self.is_toplevel:
            return False
        owner_handle = user32.GetWindow(self.handle, 4)
        if not owner_handle:
            return False
        if not user32.IsTopLevelWindow(owner_handle):
            return False
        owner_style = WindowStyle(user32.GetWindowLongA(owner_handle, -16))
        return WindowStyle.DISABLED in owner_style

    @property
    def title(self) -> str:
        """Retrieves the text of the specified window's title bar (if it has one)"""
        title = create_unicode_buffer(255)
        user32.GetWindowTextW(self.handle, title, 100)
        user32.SetLastErrorEx(0)
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
        try:
            return process.get_exepath(self.pid)
        except:
            return None

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
        hmon = monitor_from_window(self.handle)
        if not hmon:  # window is hmonoved outside of monitors
            return False
        m = Monitor(hmon)
        mr = m.get_rect()
        wr = self.get_rect()
        return (
            mr.top == wr.top
            and mr.left == wr.left
            and mr.right == wr.right
            and mr.bottom == wr.bottom
        )

    @cached_property
    def is_elevated(self):
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

    def get_extended_frame_bounds(self) -> Rect:
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
        return Rect.from_win_rect(bound)

    def get_rect(self) -> Rect:
        """Retrieves the dimensions of the bounding rectangle of the specified window.
        The dimensions are given in screen coordinates that are relative to the upper-left
        corner of the screen

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowrect

        :return: a RECT with top/left/bottom/right properties
        :rtype: RECT
        """
        rect = RECT()
        if not user32.GetWindowRect(self.handle, pointer(rect)):
            # raise WinError(get_last_error())
            return Rect(0, 0, 0, 0)
        return Rect.from_win_rect(rect)

    def set_rect(self, rect: Rect, insert_after: InsertAfter | None = None):
        """Sets the dimensions of the bounding rectangle (Call SetWindowPos with RECT)

        Ref: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos

        :param rect: RECT with top/left/bottom/right properties
        """
        logger.debug("%s set rect to %s insert_after: %s", self, rect, insert_after)
        if not user32.SetWindowPos(
            self.handle,
            insert_after,
            rect.x,
            rect.y,
            rect.width,
            rect.height,
            SET_WINDOW_RECT_FLAG,
        ):
            raise WinError(get_last_error())
        logger.debug("done %s set rect to %s", self, rect)

    def set_restrict_rect(self, rect: Rect):
        """Set the restricted rect"""
        try:
            if not self.is_restored:
                self.restore()
            self.set_rect(rect)
            self.restricted_rect = rect
            self.compensated_rect = None
            if (
                self.dpi_awareness
                == process.ProcessDpiAwareness.PROCESS_PER_MONITOR_DPI_AWARE
            ):
                # seems like the `get_extended_frame_bounds` would return physical size
                # for DPI unware window, skip them for now
                # TODO: convert physical size to logical size for DPI unware window
                # compensation
                r = self.get_rect()
                b = self.get_extended_frame_bounds()
                self.compensated_rect = Rect(
                    round(rect.left + r.left - b.left),
                    round(rect.top + r.top - b.top),
                    round(rect.right + r.right - b.right),
                    round(rect.bottom + r.bottom - b.bottom),
                )
                self.set_rect(self.compensated_rect)
            self.restricted_actual_rect = self.get_rect()
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("set compensated rect failed: %s", e)

    def restrict(self):
        """Restrict the window to the restricted rect"""
        if self.restricted_actual_rect:
            logger.debug("%s restricting to %s", self, self.restricted_actual_rect)
            r1 = self.restricted_actual_rect
            r2 = self.get_rect()
            if (
                r1.left == r2.left
                and r1.top == r2.top
                and r1.right == r2.right
                and r1.bottom == r2.bottom
            ):
                return
            self.set_rect(self.compensated_rect or self.restricted_rect)

    def unrestrict(self):
        """Unrestrict the window"""
        self.restricted_rect = None
        self.restricted_actual_rect = None

    def shrink(self, margin: int = 20):
        """Shrink the window by margin"""
        logger.info("shrink %s by %d", self.title, margin)
        rect = self.get_rect()
        rect.left += margin
        rect.top += margin
        rect.right -= margin
        rect.bottom -= margin
        self.set_rect(rect)

    def activate(self, cursor_follows=True) -> bool:
        """Brings the thread that created current window into the foreground and activates the window"""
        # move cursor to the center of the window
        if cursor_follows:
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
            if (
                fore_thread_id
                and target_thread_id
                and fore_thread_id != target_thread_id
            ):
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
        logger.debug("%s show", self)
        self.show_window(ShowWindowCmd.SW_SHOWNA)
        self.off = False

    def hide(self):
        """Hides the window"""
        logger.debug("%s hide", self)
        self.show_window(ShowWindowCmd.SW_HIDE)
        self.off = True

    @cached_property
    def is_root_window(self) -> bool:
        """Check if window is a root window"""
        return not self.parent_handle

    def inspect(self, file=sys.stdout):
        """Inspect window and print the information to the file"""
        if not self.exists():
            print("window doesn't exist anymore")
            return
        print(self, file=file)
        print("title        :", self.title, file=file)
        print("pid          :", self.pid, file=file)
        print("class name   :", self.class_name, file=file)
        print("exe path     :", self.exe, file=file)
        style = self.get_style()
        style_flags = []
        for s in WindowStyle:
            if s in style:
                style_flags.append(s.name)
        print("overlapped   :", WindowStyle.OVERLAPPEDWINDOW in style, file=file)
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
        print(
            "bound        :",
            bound.left,
            bound.top,
            bound.right,
            bound.bottom,
            file=file,
        )
        if self.restricted_rect:
            r = self.restricted_rect
            print("restricted   :", r.left, r.top, r.right, r.bottom, file=file)
        print("is_evelated  :", self.is_elevated, file=file)
        print("is_toplevel  :", self.is_toplevel, file=file)
        print("is_cloaked   :", self.is_cloaked, file=file)
        print("is_visible   :", self.is_visible, file=file)
        print("is_iconic    :", self.is_iconic, file=file)
        print("is_restored  :", self.is_restored, file=file)
        print("unmanageable :", self.unmanageable_reason, file=file)
        print("untilable    :", self.untilable_reason, file=file)
        print("parent       :", self.parent_handle, file=file)
        print("dpi_awareness:", self.dpi_awareness.name, file=file)


def filter_windows(cb: Callable[[HWND], Any]) -> Set[Any]:
    """Filter app windows of the current desktop"""
    result = set()

    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(
        hwnd: HWND, _lparam: LPARAM
    ) -> BOOL:  # pylint: disable=invalid-name
        if cb(hwnd):
            result.add(hwnd)
        return True

    if not user32.EnumWindows(enum_windows_proc, None):
        last_error = get_last_error()
        if last_error:
            raise WinError(last_error)
    return result


def get_foreground_window() -> Optional[HWND]:
    """Get the foreground window handle"""
    return user32.GetForegroundWindow()


def get_focused_window() -> Optional[HWND]:
    """Get the foreground window handle"""
    return user32.GetFocus()


def minimize_active_window():
    """Minize active window"""
    hwnd = get_foreground_window()
    if hwnd:
        Window(hwnd).minimize()


def toggle_maximize_active_window():
    """Maximize/Unmaximize active window"""
    hwnd = get_foreground_window()
    if hwnd:
        Window(hwnd).toggle_maximize()


def topo_sort_windows(windows: Iterable[Window]):
    """Sort windows topologicallly"""

    def cmp(w1: Window, w2: Window) -> int:
        r1, r2 = w1.get_rect(), w2.get_rect()
        if abs(r1.top - r2.top) < 15:
            return r1.left - r2.left
        else:
            return r1.top - r2.top

    return sorted(windows, key=cmp_to_key(cmp))


###
### debugging
###

if __name__ == "__main__":
    if len(sys.argv) > 1:
        action, args = sys.argv[1], sys.argv[2:]
        if action == "inspect":
            Window(int(args[0])).inspect()
        elif action == "move":
            w = Window(int(args[0]))
            w.set_rect(Rect(int(args[1]), int(args[2]), int(args[3]), int(args[4])))
            w.show()
        elif action == "rescue":
            w = Window(int(args[0]))
            w.set_rect(Rect(0, 0, 800, 600))
            w.show()
        elif action == "exe":
            for wd in map(
                Window,
                filter_windows(
                    lambda hwnd: Window(hwnd).exe_name.lower() == sys.argv[2].lower()
                ),
            ):
                print()
                wd.inspect()
        elif action == "app":
            for wd in map(
                Window,
                filter_windows(
                    lambda hwnd: (Window(hwnd).manageable and Window(hwnd).is_visible)
                ),
            ):
                print()
                wd.inspect()
    else:
        time.sleep(2)
        Window(get_foreground_window()).inspect()
