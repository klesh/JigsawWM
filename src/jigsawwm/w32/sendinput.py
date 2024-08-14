import enum
import os
import random
import time
import typing
import logging
from ctypes import *
from ctypes.wintypes import *

from .vk import Vk

logger = logging.getLogger(__name__)
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


random.seed(os.getpid())


def random_flags(length: int = 4, a: int = 0, b: int = 31) -> int:
    flags = set()
    while len(flags) < length:
        flags.add(1 << random.randint(a, b))
    return flags


def combine_flags(flags: typing.Iterable[int]) -> int:
    flag = 0
    for f in flags:
        flag |= f
    return flag


FLAGS = random_flags()
SYNTHESIZED_FLAG = combine_flags(FLAGS)


def send_input(*inputs: typing.List[INPUT], extra: int = 0):
    global SYNTHESIZED_FLAG
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
        if item.type == INPUTTYPE.KEYBOARD:
            item.ki.dwExtraInfo = ULONG_PTR(extra | SYNTHESIZED_FLAG)
            if not item.ki.wScan and not item.ki.dwFlags & KEYEVENTF.UNICODE:
                item.ki.wScan = user32.MapVirtualKeyW(item.ki.wVk, 0)
            # item.ki.dwFlags |= KEYEVENTF.SCANCODE
            # print("virt key", item.ki.wVk, "scan code", item.ki.wScan)
        elif item.type == INPUTTYPE.MOUSE:
            item.mi.dwExtraInfo = ULONG_PTR(extra | SYNTHESIZED_FLAG)
    length = len(inputs)
    array = INPUT * length
    if not user32.SendInput(length, array(*inputs), sizeof(INPUT)):
        logger.exception("send input error: %s", WinError(get_last_error())) 


def is_synthesized(msg: typing.Union[KEYBDINPUT, MOUSEINPUT]) -> bool:
    """Check if keyboard/mouse event is sent by this module"""
    # the propability of conflict is 31 x 30 x 29 x 28 ...
    global FLAGS
    for flag in FLAGS:
        if not msg.dwExtraInfo & flag:
            return False
    return True


def set_synthesized_flag(flag: int):
    global SYNTHESIZED_FLAG
    SYNTHESIZED_FLAG = flag


def vk_to_input(vk: Vk, pressed: bool = None, flags: int = 0) -> typing.Optional[INPUT]:
    if vk < Vk.MS_BOUND or vk > Vk.KB_BOUND:
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
            mouseData = 0x0001
            if pressed:
                dwFlags = MOUSEEVENTF.XDOWN
            else:
                dwFlags = MOUSEEVENTF.XUP
        elif vk == Vk.XBUTTON2:
            mouseData = 0x0002
            if pressed:
                dwFlags = MOUSEEVENTF.XDOWN
            else:
                dwFlags = MOUSEEVENTF.XUP
        elif vk == Vk.WHEEL_UP:
            mouseData = 120
            dwFlags = MOUSEEVENTF.WHEEL
        elif vk == Vk.WHEEL_DOWN:
            mouseData = -120
            dwFlags = MOUSEEVENTF.WHEEL
        return INPUT(
            type=INPUTTYPE.MOUSE,
            mi=MOUSEINPUT(dwFlags=dwFlags | flags, mouseData=mouseData),
        )
    else:
        dwFlags = 0
        if not pressed:
            dwFlags |= KEYEVENTF.KEYUP
        if vk >= vk.PRIOR and vk <= vk.HELP:
            dwFlags |= KEYEVENTF.EXTENDEDKEY
        return INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=vk, dwFlags=dwFlags | flags),
        )


def reset_modifiers():
    send_input(
        vk_to_input(key, pressed=False)
        for key in [Vk.LSHIFT, Vk.RSHIFT, Vk.LCONTROL, Vk.RCONTROL, Vk.LMENU, Vk.RMENU]
    )


def send_combination(*comb: typing.Sequence[Vk]):
    # reset_modifiers()
    # press keys in combination in order
    for key in comb:
        send_input(vk_to_input(key, pressed=True))
    # release keys in combination in reverse order
    for key in reversed(comb):
        send_input(vk_to_input(key, pressed=False))


def send_text(text: str):
    """Send unicode text including emojis to active window. NOTE: do NOT use this in side
    a Hotkey with ALT modifier, it won't work and I don't know how to mitigate(sending ALT up didn't work).
    """
    b = text.encode("utf_16_le")
    for i in range(0, len(b), 2):
        code = b[i] | b[i + 1] << 8
        send_input(
            INPUT(
                type=INPUTTYPE.KEYBOARD,
                ki=KEYBDINPUT(dwFlags=KEYEVENTF.UNICODE, wScan=code),
            ),
            INPUT(
                type=INPUTTYPE.KEYBOARD,
                ki=KEYBDINPUT(dwFlags=KEYEVENTF.UNICODE | KEYEVENTF.KEYUP, wScan=code),
            ),
        )


if __name__ == "__main__":
    import time

    from .vk import Vk

    # print(hex(ord("😂")))
    # encodings = [
    #     "utf_32",
    #     "utf_32_be",
    #     "utf_32_le",
    #     "utf_16",
    #     "utf_16_be",
    #     "utf_16_le",
    #     "utf_7",
    #     "utf_8",
    #     "utf_8_sig",
    # ]
    # for e in encodings:
    #     b = "😄".encode(e)
    #     print(e.ljust(20), " ".join("{:02x}".format(x) for x in b))
    time.sleep(3)
    # send_text("hello😂您好")
    # from datetime import datetime

    # send_text(datetime.now().strftime("%Y-%m-%d"))
    # send_input(
    #     INPUT(
    #         type=INPUTTYPE.KEYBOARD,
    #         ki=KEYBDINPUT(wVk=Vk.RETURN, wScan=0x1c),
    #     ),
    #     INPUT(
    #         type=INPUTTYPE.KEYBOARD,
    #         ki=KEYBDINPUT(wVk=Vk.RETURN, wScan=0x1c, dwFlags=KEYEVENTF.KEYUP),
    #     ),
    # )
    send_input(
        vk_to_input(Vk.RETURN, pressed=True),
        vk_to_input(Vk.RETURN, pressed=False),
    )

    # send_input(
    #     vk_to_input(Vk.WHEEL_UP),
    #     vk_to_input(Vk.WHEEL_DOWN),
    #     vk_to_input(Vk.XBUTTON2, pressed=True),
    #     vk_to_input(Vk.XBUTTON2, pressed=False),
    #     INPUT(
    #         type=INPUTTYPE.KEYBOARD,
    #         ki=KEYBDINPUT(wVk=Vk.LSHIFT),
    #     ),
    #     INPUT(
    #         type=INPUTTYPE.KEYBOARD,
    #         ki=KEYBDINPUT(wVk=Vk.INSERT, dwFlags=KEYEVENTF.EXTENDEDKEY),
    #     ),
    #     INPUT(
    #         type=INPUTTYPE.KEYBOARD,
    #         ki=KEYBDINPUT(
    #             wVk=Vk.INSERT, dwFlags=KEYEVENTF.KEYUP | KEYEVENTF.EXTENDEDKEY
    #         ),
    #     ),
    #     INPUT(
    #         type=INPUTTYPE.KEYBOARD,
    #         ki=KEYBDINPUT(wVk=Vk.LSHIFT, dwFlags=KEYEVENTF.KEYUP),
    #     ),
    # )
