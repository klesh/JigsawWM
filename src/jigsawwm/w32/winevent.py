"""WinEvent eum"""

import logging
import enum
from ctypes import WINFUNCTYPE
from ctypes.wintypes import HANDLE, DWORD, HWND, LONG

HWINEVENTHOOK = HANDLE

WINEVENTHOOKPROC = WINFUNCTYPE(
    HWINEVENTHOOK, HANDLE, DWORD, HWND, LONG, LONG, DWORD, DWORD
)

logger = logging.getLogger(__name__)


class WinEvent(enum.IntEnum):
    """WinEvent enumeration for Windows event hooking"""

    # The range of WinEvent constant values specified by the Accessibility Interoperability Alliance (AIA) for use across the industry. For more information, see Allocation of WinEvent IDs.
    EVENT_AIA_START = 0xA000
    EVENT_AIA_END = 0xAFFF

    # The lowest and highest possible event values.
    EVENT_MIN = 0x00000001
    EVENT_MAX = 0x7FFFFFFF

    EVENT_OBJECT_ACCELERATORCHANGE = 0x8012
    # Sent when a window is cloaked
    EVENT_OBJECT_CLOAKED = 0x8017
    EVENT_OBJECT_CONTENTSCROLLED = 0x8015
    EVENT_OBJECT_CREATE = 0x8000
    EVENT_OBJECT_DEFACTIONCHANGE = 0x8011
    EVENT_OBJECT_DESCRIPTIONCHANGE = 0x800D
    EVENT_OBJECT_DESTROY = 0x8001
    EVENT_OBJECT_DRAGSTART = 0x8021
    EVENT_OBJECT_DRAGCANCEL = 0x8022
    EVENT_OBJECT_DRAGCOMPLETE = 0x8023
    EVENT_OBJECT_DRAGENTER = 0x8024
    EVENT_OBJECT_DRAGLEAVE = 0x8025
    EVENT_OBJECT_DRAGDROPPED = 0x8026
    EVENT_OBJECT_END = 0x80FF
    EVENT_OBJECT_FOCUS = 0x8005
    EVENT_OBJECT_HELPCHANGE = 0x8010
    # An object is hidden.
    EVENT_OBJECT_HIDE = 0x8003
    EVENT_OBJECT_HOSTEDOBJECTSINVALIDATED = 0x8020
    EVENT_OBJECT_IME_HIDE = 0x8028
    EVENT_OBJECT_IME_SHOW = 0x8027
    EVENT_OBJECT_IME_CHANGE = 0x8029
    EVENT_OBJECT_INVOKED = 0x8013
    EVENT_OBJECT_LIVEREGIONCHANGED = 0x8019
    EVENT_OBJECT_LOCATIONCHANGE = 0x800B
    EVENT_OBJECT_NAMECHANGE = 0x800C
    EVENT_OBJECT_PARENTCHANGE = 0x800F
    EVENT_OBJECT_REORDER = 0x8004
    EVENT_OBJECT_SELECTION = 0x8006
    EVENT_OBJECT_SELECTIONADD = 0x8007
    EVENT_OBJECT_SELECTIONREMOVE = 0x8008
    EVENT_OBJECT_SELECTIONWITHIN = 0x8009
    # A hidden object is shown
    EVENT_OBJECT_SHOW = 0x8002
    EVENT_OBJECT_STATECHANGE = 0x800A
    EVENT_OBJECT_TEXTEDIT_CONVERSIONTARGETCHANGED = 0x8030
    EVENT_OBJECT_TEXTSELECTIONCHANGED = 0x8014
    # Sent when a window is uncloaked
    EVENT_OBJECT_UNCLOAKED = 0x8018
    EVENT_OBJECT_VALUECHANGE = 0x800E

    # The range of event constant values reserved for OEMs. For more information, see Allocation of WinEvent IDs.
    EVENT_OEM_DEFINED_START = 0x0101
    EVENT_OEM_DEFINED_END = 0x01FF

    EVENT_SYSTEM_ALERT = 0x0002
    EVENT_SYSTEM_ARRANGMENTPREVIEW = 0x8016
    EVENT_SYSTEM_CAPTUREEND = 0x0009
    EVENT_SYSTEM_CAPTURESTART = 0x0008
    EVENT_SYSTEM_CONTEXTHELPEND = 0x000D
    EVENT_SYSTEM_CONTEXTHELPSTART = 0x000C
    # The active desktop has been switched.
    EVENT_SYSTEM_DESKTOPSWITCH = 0x0020
    EVENT_SYSTEM_DIALOGEND = 0x0011
    EVENT_SYSTEM_DIALOGSTART = 0x0010
    EVENT_SYSTEM_DRAGDROPEND = 0x000F
    EVENT_SYSTEM_DRAGDROPSTART = 0x000E
    EVENT_SYSTEM_END = 0x00FF
    EVENT_SYSTEM_FOREGROUND = 0x0003
    EVENT_SYSTEM_MENUPOPUPEND = 0x0007
    EVENT_SYSTEM_MENUPOPUPSTART = 0x0006
    EVENT_SYSTEM_MENUEND = 0x0005
    EVENT_SYSTEM_MENUSTART = 0x0004
    EVENT_SYSTEM_MINIMIZEEND = 0x0017
    EVENT_SYSTEM_MINIMIZESTART = 0x0016
    # The movement or resizing of a window has finished
    EVENT_SYSTEM_MOVESIZEEND = 0x000B
    EVENT_SYSTEM_MOVESIZESTART = 0x000A
    EVENT_SYSTEM_SCROLLINGEND = 0x0013
    EVENT_SYSTEM_SCROLLINGSTART = 0x0012
    EVENT_SYSTEM_SOUND = 0x0001
    EVENT_SYSTEM_SWITCHEND = 0x0015
    EVENT_SYSTEM_SWITCHSTART = 0x0014

    # The range of event constant values reserved for UI Automation event identifiers. For more information, see Allocation of WinEvent IDs.
    EVENT_UIA_EVENTID_START = 0x4E00
    EVENT_UIA_EVENTID_END = 0x4EFF

    # The range of event constant values reserved for UI Automation property-changed event identifiers. For more information, see Allocation of WinEvent IDs.
    EVENT_UIA_PROPID_START = 0x7500
    EVENT_UIA_PROPID_END = 0x75FF

    UNKNOWN = 0x00

    @classmethod
    def _missing_(cls, value):
        # logger.warning("Unknown WinEvent value: %s", value)
        return cls.UNKNOWN
