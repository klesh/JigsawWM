from jigsawwm.w32.hook import Hook, KBDLLHOOKMSGID, KBDLLHOOKDATA
from jigsawwm.w32.vk import VirtualKey
from jigsawwm.w32.sendinput import is_synthesized
from typing import Callable, Dict, Sequence, Tuple, FrozenSet
from concurrent.futures import ThreadPoolExecutor
import enum


class Modifier(enum.IntFlag):
    """Keyboard modifier"""

    VK_LCONTROL = enum.auto()
    VK_LMENU = enum.auto()
    VK_LSHIFT = enum.auto()
    VK_LWIN = enum.auto()
    VK_RCONTROL = enum.auto()
    VK_RMENU = enum.auto()
    VK_RSHIFT = enum.auto()
    VK_RWIN = enum.auto()


# { combination: (func, swallow) }
_hotkeys: Dict[FrozenSet[VirtualKey], Tuple[Callable, bool]] = {}
_executor = ThreadPoolExecutor()


def expand_combination(
    combkeys: Sequence[VirtualKey],
) -> Sequence[Sequence[VirtualKey]]:
    pass


def hotkey(
    combination: str, target: Callable | str | Sequence[str], swallow: bool = True
):
    """Register a combination to a function or inputs

    :param combination: str, example LCtrl+Alt+Shift+Win+a
    :param target: Callable | str, one of the following action would be carried
        out based on the type of the target:

        Callable:   the function would be executed
        str:        the str would be treated as a combination and send accordingly.
                    i.e. "RWin+Space"
        Sequence[str]: the sequence would be treated as key inputs
                    i.e. [ "Alt_Down", "q_Down", "q_Up", "Alt_Up", "h", "e", "l", "l", "o" ]
    """

    # process combination


def register_hotkey(
    combkeys: Sequence[VirtualKey], func: Callable, swallow: bool = True
):
    """Register a system hotkey

    :param combkeys: Sequence[VirtualKey], virtual keys combination
    :param func: Callable[[], bool], execute when the last key in the combination is
        pressed
    :param swallow: stop combination being process by other apps
    """
    global _hotkeys
    combkeys = frozenset(combkeys)
    # check if combination valid
    count = len(list(filter(lambda vk: vk.name not in Modifier.__members__, combkeys)))
    if count != 1:
        raise Exception("require 1 and onely 1 triggering key")
    _hotkeys[combkeys] = (func, swallow)


_modifier = Modifier(0)


def _keyboard_proc(msgid: KBDLLHOOKMSGID, msg: KBDLLHOOKDATA) -> bool:
    global _hotkeys, _executor
    # skip key we sent out
    if is_synthesized(msg):
        return False
    global _modifier, _hotkeys
    vkey = VirtualKey(msg.vkCode)
    if vkey.name in Modifier.__members__:
        # update modifier state if
        if msgid == KBDLLHOOKMSGID.WM_KEYDOWN:
            _modifier |= Modifier[vkey.name]
        else:
            _modifier &= ~Modifier[vkey.name]
    elif msgid == KBDLLHOOKMSGID.WM_KEYDOWN:
        # see if combination registered
        combination = frozenset((*map(lambda m: VirtualKey[m.name], _modifier), vkey))
        fs = _hotkeys.get(combination)
        if fs is not None:
            func, swallow = fs
            _executor.submit(func)
            return swallow


hook = Hook(keyboard=_keyboard_proc)
hook.start()

if __name__ == "__main__":
    import time
    from functools import partial

    def delay_hello():
        time.sleep(1)
        print("hello world")

    register_hotkey({VirtualKey.VK_LWIN, VirtualKey.VK_KEY_B}, delay_hello, True)

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            hook.stop()
            break
