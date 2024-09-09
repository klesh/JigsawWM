"""The module that holds the window structures and enums."""

import enum
from ctypes.wintypes import RECT
from dataclasses import dataclass


class EnumCheckResult(enum.IntFlag):
    SKIP = 0
    CAPTURE = 1
    STOP = 2
    CAPTURE_AND_STOP = 3


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


class WindowExStyle(enum.IntFlag):
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


def repr_rect(rect: RECT):
    """Return the string representation of the RECT object."""
    return f"RECT(left={rect.left}, top={rect.top}, right={rect.right}, bottom={rect.bottom})"


def rect_eq(a: RECT, b: RECT):
    """Return True if the two RECT objects are equal."""
    return (
        a.left == b.left
        and a.top == b.top
        and a.right == b.right
        and a.bottom == b.bottom
    )


@dataclass
class Rect:
    """ctypes.wintypes.RECT wrapper"""

    left: int
    top: int
    right: int
    bottom: int

    @classmethod
    def from_win_rect(cls, r: RECT):
        """Create a Rect object from a RECT object."""
        return cls(r.left, r.top, r.right, r.bottom)

    def __repr__(self) -> str:
        return f"Rect(left={self.left}, top={self.top}, right={self.right}, bottom={self.bottom})"

    @property
    def width(self) -> int:
        """Return the width of the rectangle."""
        return self.right - self.left

    @width.setter
    def width(self, value: int):
        """Set the width of the rectangle."""
        self.right = self.left + value

    @property
    def height(self) -> int:
        """Return the height of the rectangle."""
        return self.bottom - self.top

    @height.setter
    def height(self, value: int):
        """Set the height of the rectangle."""
        self.bottom = self.top + value

    @property
    def x(self) -> int:
        """Return the x coordinate of the rectangle."""
        return self.left

    @x.setter
    def x(self, value: int):
        """Set the x coordinate of the rectangle."""
        self.left = value

    @property
    def y(self) -> int:
        """Return the y coordinate of the rectangle."""
        return self.top

    @y.setter
    def y(self, value: int):
        """Set the y coordinate of the rectangle."""
        self.top = value

    @property
    def center_x(self) -> int:
        """Return the x coordinate of the center."""
        return self.left + self.width // 2

    @property
    def center_y(self) -> int:
        """Return the y coordinate of the center."""
        return self.top + self.height // 2

    def contains(self, x: int, y: int):
        """Return True if the point is inside the rectangle."""
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def contains_rect(self, other: "Rect"):
        """Return True if the other rectangle is inside the rectangle."""
        return self.contains(other.left, other.top) and self.contains(
            other.right, other.bottom
        )

    def contains_rect_center(self, other: "Rect"):
        """Return True if the other rectangle's center is inside the rectangle."""
        return self.contains(other.center_x, other.center_y)
