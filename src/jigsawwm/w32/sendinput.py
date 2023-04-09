import enum
import typing
from ctypes import *
from ctypes.wintypes import *

user32 = WinDLL("user32", use_last_error=True)

ULONG_PTR = LPARAM


class INPUTTYPE(enum.IntEnum):
    MOUSE = 0
    KEYBOARD = 1
    HARDWARE = 2


class KEYEVENTF(enum.IntFlag):
    EXTENDEDKEY = 0x0001
    KEYUP = 0x0002
    SCANCODE = 0x0008
    UNICODE = 0x0004


class KEYBDINPUT(Structure):
    _fields_ = (
        ("wVk", WORD),
        ("wScan", WORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEEVENTF(enum.IntFlag):
    ABSOLUTE = 0x8000
    HWHEEL = 0x01000
    MOVE = 0x0001
    MOVE_NOCOALESCE = 0x2000
    LEFTDOWN = 0x0002
    LEFTUP = 0x0004
    RIGHTDOWN = 0x0008
    RIGHTUP = 0x0010
    MIDDLEDOWN = 0x0020
    MIDDLEUP = 0x0040
    VIRTUALDESK = 0x4000
    WHEEL = 0x0800
    XDOWN = 0x0080
    XUP = 0x0100


class MOUSEINPUT(Structure):
    _fields_ = (
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(Structure):
    _fields_ = (
        ("uMsg", LONG),
        ("wParamL", WORD),
        ("wParamH", WORD),
    )


class INPUTDATA(Union):
    _fields_ = (
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    )


class INPUT(Structure):
    _anonymous_ = ["u"]
    _fields_ = (
        ("type", DWORD),
        ("u", INPUTDATA),
    )


SYNTHESIZED_ID = 123123123


def send_input(*inputs: typing.List[INPUT]):
    global SYNTHESIZED_ID
    """Synthesizes keystrokes, mouse motions, and button clicks.

    Usage:
    ```
    send_input(
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=VirtualKey.A),
        ),
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=VirtualKey.A, dwFlags=KEYEVENTF.KEYUP),
        ),
    )
    ```

    :param List[INPUT] inputs: list of keyboard/mouse inputs which
        to be sent to system

    """
    for item in inputs:
        if item is None:
            continue
        if item.ki:
            item.ki.dwExtraInfo = SYNTHESIZED_ID
        elif item.mi:
            item.mi.dwExtraInfo = SYNTHESIZED_ID
    length = len(inputs)
    array = INPUT * length
    if not user32.SendInput(length, array(*inputs), sizeof(INPUT)):
        raise WinError(get_last_error())


def is_synthesized(msg: typing.Union[KEYBDINPUT, MOUSEINPUT]) -> bool:
    """Check if keyboard/mouse event is sent by this module"""
    global SYNTHESIZED_ID
    return msg.dwExtraInfo == SYNTHESIZED_ID


if __name__ == "__main__":
    from .vk import Vk

    send_input(
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=Vk.A),
        ),
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=Vk.A, dwFlags=KEYEVENTF.KEYUP),
        ),
    )
