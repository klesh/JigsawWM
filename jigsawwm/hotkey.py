import enum
from concurrent.futures import ThreadPoolExecutor
from traceback import print_exception
from typing import Callable, Dict, FrozenSet, Iterator, Optional, Sequence, Tuple

from jigsawwm.w32.hook import KBDLLHOOKDATA, KBDLLHOOKMSGID, Hook
from jigsawwm.w32.sendinput import (
    INPUT,
    INPUTTYPE,
    KEYBDINPUT,
    KEYEVENTF,
    is_synthesized,
    send_input,
)
from jigsawwm.w32.vk import Vk


class Modifier(enum.IntFlag):
    """Keyboard modifier"""

    LCONTROL = enum.auto()
    LMENU = enum.auto()
    LSHIFT = enum.auto()
    LWIN = enum.auto()
    RCONTROL = enum.auto()
    RMENU = enum.auto()
    RSHIFT = enum.auto()
    RWIN = enum.auto()
    CONTROL = LCONTROL | RCONTROL
    MENU = LMENU | RMENU
    SHIFT = LSHIFT | RSHIFT
    WIN = LWIN | RWIN


def expand_combination(
    combkeys: Sequence[Vk],
    index: Optional[int] = 0,
) -> Iterator[Sequence[Vk]]:
    """Expand `Ctrl+s` to `LCtrl+s` and `RCtrl+s`, so on and so forth"""
    key = combkeys[index]
    if key.name in Modifier.__members__:
        is_last = index + 1 == len(combkeys)
        for mk in Modifier[key.name]:
            new_combkeys = combkeys[:index] + [Vk[mk.name]]
            if is_last:
                yield new_combkeys
            else:
                yield from expand_combination(
                    new_combkeys + combkeys[index + 1 :], index + 1
                )
    else:
        yield combkeys


# print("MENU+s", list(expand_combination([Vk.MENU, Vk.S])))
# print("LMENU+s", list(expand_combination([Vk.LMENU, Vk.S])))
# print("MENU+SHIFT+s", list(expand_combination([Vk.MENU, Vk.SHIFT, Vk.S])))
# print("F1", list(expand_combination([Vk.F1])))
# exit()

# { combination: (func, swallow, counteract) }
_hotkeys: Dict[
    FrozenSet[Vk], Tuple[Callable, bool, bool, Callable[[Exception], None]]
] = {}
_executor = ThreadPoolExecutor()


def hotkey(
    combkeys: Sequence[Vk] | str,
    target: Callable | str,
    swallow: bool = True,
    error_handler: Callable[[Exception], None] = print_exception,
):
    """Register a system hotkey

    Check `jigsawwm.w32.vk.Vk` for virtual key names
    Check `_vk_aliases` for key aliases

    :param combkeys: Sequence[VirtualKey] | str, virtual keys combination
        example: [Vk.LCONTROL, Vk.LSHIFT, Vk.S] or "LControl+LShift+s"
    :param target: Callable | str, one of the following action would be carried
        out based on the type of the target:

        Callable:   the function would be executed
        str:        the str would be treated as a combination and send accordingly.
                    i.e. "RWin+Space"
    :param swallow: stop combination being process by other apps
    """
    global _hotkeys
    # parse combkeys if it is string
    if isinstance(combkeys, str):
        combkeys = parse_hotkey(combkeys)
    # check if combination valid
    if not combkeys:
        raise Exception("empty combination")
    # turn target to function if it is string
    counteract = False
    if isinstance(target, str):
        target = combination_input(target)
        counteract = True
    count = len(list(filter(lambda vk: vk.name not in Modifier.__members__, combkeys)))
    if count != 1:
        raise Exception("require 1 and only 1 triggering key")
    for ck in expand_combination(combkeys):
        _hotkeys[frozenset(ck)] = (target, swallow, counteract, error_handler)


_vk_aliases: Dict[str, Vk] = {
    "LCTRL": Vk.LCONTROL,
    "LALT": Vk.LMENU,
    "RCTRL": Vk.RCONTROL,
    "RALT": Vk.RMENU,
    "CTRL": Vk.CONTROL,
    "MENU": Vk.MENU,
    "-": Vk.OEM_MINUS,
    "=": Vk.OEM_PLUS,
    ";": Vk.OEM_1,
    "/": Vk.OEM_2,
    "`": Vk.OEM_3,
    "[": Vk.OEM_4,
    "\\": Vk.OEM_5,
    "]": Vk.OEM_6,
    "'": Vk.OEM_7,
    ",": Vk.OEM_COMMA,
    ".": Vk.OEM_PERIOD,
}


def parse_hotkey(combkeys: str) -> Sequence[Vk]:
    """Converts combination in plain text ("Ctrl+s") to Sequence[Vk] ([Vk.CONTROL, Vk.S])"""
    parsed = []
    if not combkeys:
        return parsed
    global _vk_aliases
    for key_name in combkeys.split("+"):
        key = None
        key_name = key_name.strip().upper()
        # try alias
        key = _vk_aliases.get(key_name)
        # try name
        if key is None:
            if key_name not in Vk.__members__:
                raise Exception(f"invalid key: {key_name}")
            key = Vk[key_name]
        parsed.append(key)
    return parsed


def combination_input(target: str) -> Callable:
    target = parse_hotkey(target)

    def callback():
        for key in target:
            send_input(INPUT(type=INPUTTYPE.KEYBOARD, ki=KEYBDINPUT(wVk=key)))
        for key in reversed(target):
            send_input(
                INPUT(
                    type=INPUTTYPE.KEYBOARD,
                    ki=KEYBDINPUT(wVk=key, dwFlags=KEYEVENTF.KEYUP),
                )
            )

    return callback


_modifier = Modifier(0)


def keyboard_event_handler(msgid: KBDLLHOOKMSGID, msg: KBDLLHOOKDATA) -> bool:
    global _hotkeys, _executor
    # skip key we sent out
    if is_synthesized(msg):
        return False
    global _modifier, _hotkeys
    vkey = Vk(msg.vkCode)
    # print(msgid.name, vkey.name, msg.dwExtraInfo)
    if vkey.name in Modifier.__members__:
        # update modifier state if
        if msgid == KBDLLHOOKMSGID.WM_KEYDOWN:
            _modifier |= Modifier[vkey.name]
        elif msgid == KBDLLHOOKMSGID.WM_KEYUP:
            _modifier &= ~Modifier[vkey.name]
    elif msgid == KBDLLHOOKMSGID.WM_KEYDOWN:
        # see if combination registered
        combination = frozenset((*map(lambda m: Vk[m.name], _modifier), vkey))
        fs = _hotkeys.get(combination)
        if fs is not None:
            func, swallow, counteract, error_handler = fs
            if counteract:
                # send key up for combination to avoid confliction if the func
                # call send_input
                for key in combination:
                    send_input(
                        INPUT(
                            type=INPUTTYPE.KEYBOARD,
                            ki=KEYBDINPUT(wVk=key, dwFlags=KEYEVENTF.KEYUP),
                        )
                    )
            # wrap func with in try-catch for safty
            def wrapped_func():
                try:
                    func()
                except Exception as e:
                    error_handler(e)

            _executor.submit(wrapped_func)
            return swallow


if __name__ == "__main__":
    import time

    def delay_hello():
        time.sleep(1)
        print("hello world")

    hotkey([Vk.LWIN, Vk.B], delay_hello, True)

    hook = Hook()
    hook.install_keyboard_hook(keyboard_event_handler)
    hook.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            hook.stop()
            break
