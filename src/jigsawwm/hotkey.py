import enum
from concurrent.futures import ThreadPoolExecutor
from traceback import print_exception
from typing import Callable, Dict, FrozenSet, Iterator, Optional, Sequence, Tuple, Union

from jigsawwm.w32.hook import (
    KBDLLHOOKDATA,
    KBDLLHOOKMSGID,
    MSLLHOOKDATA,
    MSLLHOOKMSGID,
    Hook,
)
from jigsawwm.w32.sendinput import (
    INPUT,
    INPUTTYPE,
    KEYBDINPUT,
    KEYEVENTF,
    MOUSEEVENTF,
    MOUSEINPUT,
    is_synthesized,
    send_input,
)
from jigsawwm.w32.vk import Vk


def is_power_of_2(num: int) -> bool:
    return num != 0 and num & (num - 1) == 0


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
    XBUTTON1 = enum.auto()
    XBUTTON2 = enum.auto()
    CONTROL = LCONTROL | RCONTROL
    MENU = LMENU | RMENU
    SHIFT = LSHIFT | RSHIFT
    WIN = LWIN | RWIN

    @classmethod
    def unfold(cls, mk: Union[str, int]) -> Iterator["Modifier"]:
        if not mk:
            return
        if isinstance(mk, str):
            mk = cls[mk].value
        if is_power_of_2(mk):
            yield cls(mk)
            return
        for v in cls.__members__.values():
            if v >= cls.CONTROL:
                return
            if v & mk:
                yield cls(v)


def expand_combination(
    combkeys: Sequence[Vk],
    index: Optional[int] = 0,
) -> Iterator[Sequence[Vk]]:
    """Expand `Ctrl+s` to `LCtrl+s` and `RCtrl+s`, so on and so forth"""
    key = combkeys[index]
    if key.name in Modifier.__members__:
        is_last = index + 1 == len(combkeys)
        for mk in Modifier.unfold(key.name):
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
    combkeys: Union[Sequence[Vk], str],
    target: Union[Callable, str],
    swallow: bool = True,
    error_handler: Callable[[Exception], None] = print_exception,
):
    """Register a system hotkey
    check `jigsawwm.w32.vk.Vk` for virtual key names
    check `_vk_aliases` for key aliases

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
    """Converts key combination in text format to a Callable function"""
    target = parse_hotkey(target)

    def callback():
        for key in target:
            send_input(vk_to_input(key, pressed=True))
        for key in reversed(target):
            send_input(vk_to_input(key, pressed=False))

    return callback


def vk_to_input(vk: Vk, pressed: bool) -> Optional[INPUT]:
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
        return INPUT(
            type=INPUTTYPE.KEYBOARD,
            ki=KEYBDINPUT(wVk=vk, dwFlags=0 if pressed else KEYEVENTF.KEYUP),
        )


_modifier = Modifier(0)


def input_event_handler(
    msgid: Union[KBDLLHOOKMSGID, MSLLHOOKMSGID], msg: Union[KBDLLHOOKDATA, MSLLHOOKDATA]
) -> bool:
    """Handles keyboard events and call callback if the combination
    had been registered
    """
    global _hotkeys, _executor
    # skip key we sent out
    if is_synthesized(msg):
        return False
    # convert keyboard/mouse event to a unified virtual key representation
    vkey = None
    pressed = None
    if isinstance(msgid, KBDLLHOOKMSGID):
        vkey = Vk(msg.vkCode)
        if msgid == KBDLLHOOKMSGID.WM_KEYDOWN:
            pressed = True
        elif msgid == KBDLLHOOKMSGID.WM_KEYUP:
            pressed = False
    elif isinstance(msgid, MSLLHOOKMSGID):
        if msgid == MSLLHOOKMSGID.WM_LBUTTONDOWN:
            vkey = Vk.LBUTTON
            pressed = True
        elif msgid == MSLLHOOKMSGID.WM_LBUTTONUP:
            vkey = Vk.LBUTTON
            pressed = False
        elif msgid == MSLLHOOKMSGID.WM_RBUTTONDOWN:
            vkey = Vk.RBUTTON
            pressed = True
        elif msgid == MSLLHOOKMSGID.WM_RBUTTONUP:
            vkey = Vk.RBUTTON
            pressed = False
        elif msgid == MSLLHOOKMSGID.WM_MBUTTONDOWN:
            vkey = Vk.MBUTTON
            pressed = True
        elif msgid == MSLLHOOKMSGID.WM_MBUTTONUP:
            vkey = Vk.MBUTTON
            pressed = False
        elif msgid == MSLLHOOKMSGID.WM_XBUTTONDOWN:
            vkey = Vk.XBUTTON1 if msg.flags == 1 else Vk.XBUTTON2
            pressed = True
        elif msgid == MSLLHOOKMSGID.WM_XBUTTONUP:
            vkey = Vk.XBUTTON1 if msg.flags == 1 else Vk.XBUTTON2
            pressed = False
        elif msgid == MSLLHOOKMSGID.WM_MOUSEWHEEL:
            delta = msg.get_wheel_delta()
            if delta > 0:
                vkey = Vk.WHEEL_UP
            else:
                vkey = Vk.WHEEL_DOWN
            pressed = True
    # skip events that out of our interest
    if vkey is None or pressed is None:
        return
    global _modifier, _hotkeys
    if vkey.name in Modifier.__members__:
        # update modifier state (pressed, released)
        if pressed:
            _modifier |= Modifier[vkey.name]
        else:
            _modifier &= ~Modifier[vkey.name]
    elif pressed:
        # see if combination registered
        combination = frozenset(
            (*map(lambda m: Vk[m.name], Modifier.unfold(_modifier)), vkey)
        )
        fs = _hotkeys.get(combination)
        if fs is not None:
            func, swallow, counteract, error_handler = fs
            if counteract:
                # send key up for combination to avoid confliction in case the hooked func call send_input
                for key in combination:
                    if key < Vk.MS_BOUND or key > Vk.KB_BOUND:
                        continue
                    send_input(vk_to_input(key, pressed=False))
            # wrap func with in try-catch for safty
            def wrapped_func():
                try:
                    func()
                except Exception as e:
                    error_handler(e)

            # execute hook in a separate thread for performance
            _executor.submit(wrapped_func)
            # tell other apps to ignore this event
            return swallow


if __name__ == "__main__":
    import time

    def delay_hello():
        time.sleep(1)
        print("hello world")

    hotkey([Vk.LWIN, Vk.B], delay_hello, True)
    # hotkey([Vk.XBUTTON1, Vk.LBUTTON], delay_hello, True)
    hotkey([Vk.XBUTTON2, Vk.LBUTTON], delay_hello, True)

    hook = Hook()
    hook.install_keyboard_hook(input_event_handler)
    hook.install_mouse_hook(input_event_handler)
    hook.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            hook.stop()
            break
