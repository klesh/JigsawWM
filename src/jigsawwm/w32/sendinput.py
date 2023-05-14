import enum
import typing
from ctypes import *
from ctypes.wintypes import *

from .vk import Vk

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


def vk_to_input(vk: Vk, pressed: bool) -> typing.Optional[INPUT]:
    if vk > Vk.KB_BOUND:
        return
    if vk < Vk.MS_BOUND:
        dwFlags = 0
        mouseData = 0
        if vk == Vk.LBUTTON:
            if pressed:
                dwFlags = MOUSEEVENTF.LEFTDOWN
            else:
                dwFlags = MOUSEEVENTF.LEFTUP
        elif vk == Vk.RBUTTON:
            if pressed:
                dwFlags = MOUSEEVENTF.RIGHTDOWN
            else:
                dwFlags = MOUSEEVENTF.RIGHTUP
        elif vk == Vk.MBUTTON:
            if pressed:
                dwFlags = MOUSEEVENTF.MIDDLEDOWN
            else:
                dwFlags = MOUSEEVENTF.MIDDLEUP
        elif vk == Vk.XBUTTON1:
            if pressed:
                dwFlags = MOUSEEVENTF.XUP
                mouseData = 1
            else:
                dwFlags = MOUSEEVENTF.MIDDLEUP
                mouseData = 1
        elif vk == Vk.XBUTTON2:
            if pressed:
                dwFlags = MOUSEEVENTF.XUP
                mouseData = 2
            else:
                dwFlags = MOUSEEVENTF.MIDDLEUP
                mouseData = 2
        return INPUT(
            type=INPUTTYPE.MOUSE,
            mi=MOUSEINPUT(dwFlags=dwFlags, mouseData=mouseData),
        )
    else:
        dwFlags = 0
        if not pressed:
            dwFlags |= KEYEVENTF.KEYUP
        if vk >= vk.PRIOR and vk <= vk.HELP:
            dwFlags |= KEYEVENTF.EXTENDEDKEY
        return INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=vk, dwFlags=dwFlags),
        )


def send_combination(comb: typing.Sequence[Vk]):
    # press keys in combination in order
    for key in comb:
        send_input(vk_to_input(key, pressed=True))
    # release keys in combination in reverse order
    for key in reversed(comb):
        send_input(vk_to_input(key, pressed=False))


if __name__ == "__main__":
    import time

    from .vk import Vk

    time.sleep(3)

    send_input(
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=Vk.LSHIFT),
        ),
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=Vk.INSERT, dwFlags=KEYEVENTF.EXTENDEDKEY),
        ),
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(
                wVk=Vk.INSERT, dwFlags=KEYEVENTF.KEYUP | KEYEVENTF.EXTENDEDKEY
            ),
        ),
        INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=Vk.LSHIFT, dwFlags=KEYEVENTF.KEYUP),
        ),
    )
