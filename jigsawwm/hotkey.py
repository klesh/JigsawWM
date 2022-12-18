from jigsawwm.w32.hook import Hook, KBDLLHOOKMSGID, KBDLLHOOKDATA
from jigsawwm.w32.vk import VirtualKey
from jigsawwm.w32.sendinput import is_synthesized
from typing import Callable, Dict, Sequence, Tuple, FrozenSet
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


def hotkey(combination: Sequence[VirtualKey], func: Callable, swallow: bool = True):
    """Register a system hotkey

    :param combination: Sequence[VirtualKey], virtual key combination list
    :param func: Callable[[], bool], execute when the last key in the combination is
        pressed
    :param swallow: stop combination being process by other apps
    """
    global _hotkeys
    combination = frozenset(combination)
    # check if combination valid
    count = len(
        list(filter(lambda vk: vk.name not in Modifier.__members__, combination))
    )
    if count != 1:
        raise Exception("require 1 and onely 1 triggering key")
    _hotkeys[combination] = (func, swallow)


_modifier = Modifier(0)


def _keyboard_proc(msgid: KBDLLHOOKMSGID, msg: KBDLLHOOKDATA) -> bool:
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
            fs[0]()
            return fs[1]


hook = Hook(keyboard=_keyboard_proc)
hook.start()

if __name__ == "__main__":
    import time
    from functools import partial

    hotkey(
        {VirtualKey.VK_LWIN, VirtualKey.VK_KEY_B}, partial(print, "hello world"), True
    )

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            hook.stop()
            break
