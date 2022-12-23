from ctypes import *
from ctypes.wintypes import *
from typing import List
import enum

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


def send_input(*inputs: List[INPUT]):
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

    """
    for input in inputs:
        input.dwExtraInfo = SYNTHESIZED_ID
    length = len(inputs)
    array = INPUT * length
    if not user32.SendInput(length, array(*inputs), sizeof(INPUT)):
        raise WinError(get_last_error())


def is_synthesized(msg: KEYBDINPUT | MOUSEINPUT) -> bool:
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
