import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from traceback import print_exception
from typing import Callable, Dict, FrozenSet, Sequence, Tuple, Union

from jigsawwm.w32 import hook
from jigsawwm.w32.sendinput import (
    is_synthesized,
    send_combination,
    send_input,
    vk_to_input,
)
from jigsawwm.w32.vk import Modifier, Vk, expand_combination, parse_combination

_hotkeys: Dict[
    FrozenSet[Vk], Tuple[Callable, bool, bool, Callable[[Exception], None]]
] = {}
# for executing callback function
_executor = ThreadPoolExecutor()


def hotkey(
    combkeys: Union[Sequence[Vk], str],
    target: Union[Callable, str],
    swallow: bool = True,
    error_handler: Callable[[Exception], None] = print_exception,
    counteract: bool = False,
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
    # parse combkeys if it is string
    if isinstance(combkeys, str):
        combkeys = parse_combination(combkeys)
    # check if combination valid
    if not combkeys:
        raise ValueError("empty combination")
    # turn target to function if it is string
    if isinstance(target, str):
        target = partial(send_combination, parse_combination(target))
        counteract = True
    count = len(list(filter(lambda vk: vk.name not in Modifier.__members__, combkeys)))
    if count != 1:
        raise Exception("require 1 and only 1 triggering key")
    for ck in expand_combination(combkeys):
        _hotkeys[frozenset(ck)] = (target, swallow, counteract, error_handler)


# holding hotkey
_last_pressed_key: Vk = None
_last_pressed_time: float = 0
_holding_hotkeys: Dict[Vk, Tuple[float, Callable, Callable[[Exception], None]]] = {}


def holding_hotkey(
    key: Vk,
    callback: Callable,
    min_hold_time: float = 0.5,
    error_handler: Callable[[Exception], None] = print_exception,
):
    global _holding_hotkeys
    _holding_hotkeys[key] = (min_hold_time, callback, error_handler)


_modifier = Modifier(0)


def input_event_handler(
    msgid: Union[hook.KBDLLHOOKMSGID, hook.MSLLHOOKMSGID],
    msg: Union[hook.KBDLLHOOKDATA, hook.MSLLHOOKDATA],
) -> bool:
    """Handles keyboard events and call callback if the combination
    had been registered
    """
    # skip key we sent out
    if is_synthesized(msg):
        return False
    # convert keyboard/mouse event to a unified virtual key representation
    vkey = None
    pressed = None
    if isinstance(msgid, hook.KBDLLHOOKMSGID):
        vkey = Vk(msg.vkCode)
        if msgid == hook.KBDLLHOOKMSGID.WM_KEYDOWN:
            pressed = True
        elif msgid == hook.KBDLLHOOKMSGID.WM_KEYUP:
            pressed = False
    elif isinstance(msgid, hook.MSLLHOOKMSGID):
        if msgid == hook.MSLLHOOKMSGID.WM_LBUTTONDOWN:
            vkey = Vk.LBUTTON
            pressed = True
        elif msgid == hook.MSLLHOOKMSGID.WM_LBUTTONUP:
            vkey = Vk.LBUTTON
            pressed = False
        elif msgid == hook.MSLLHOOKMSGID.WM_RBUTTONDOWN:
            vkey = Vk.RBUTTON
            pressed = True
        elif msgid == hook.MSLLHOOKMSGID.WM_RBUTTONUP:
            vkey = Vk.RBUTTON
            pressed = False
        elif msgid == hook.MSLLHOOKMSGID.WM_MBUTTONDOWN:
            vkey = Vk.MBUTTON
            pressed = True
        elif msgid == hook.MSLLHOOKMSGID.WM_MBUTTONUP:
            vkey = Vk.MBUTTON
            pressed = False
        elif msgid == hook.MSLLHOOKMSGID.WM_XBUTTONDOWN:
            vkey = Vk.XBUTTON1 if msg.hiword() == 1 else Vk.XBUTTON2
            pressed = True
        elif msgid == hook.MSLLHOOKMSGID.WM_XBUTTONUP:
            vkey = Vk.XBUTTON1 if msg.hiword() == 1 else Vk.XBUTTON2
            pressed = False
        elif msgid == hook.MSLLHOOKMSGID.WM_MOUSEWHEEL:
            delta = msg.get_wheel_delta()
            if delta > 0:
                vkey = Vk.WHEEL_UP
            else:
                vkey = Vk.WHEEL_DOWN
            pressed = True
    # skip events that out of our interest
    if vkey is None or pressed is None:
        return
    global _modifier, _hotkeys, _executor, _last_pressed_key, _last_pressed_time

    swallow = False
    is_hodling_hotkey = vkey in _holding_hotkeys
    # check if holding key matches
    if pressed:
        if _last_pressed_key is None and is_hodling_hotkey:
            # swallow key press event if holding key registered
            _last_pressed_key = vkey
            _last_pressed_time = time.time()
            swallow = True
        elif _last_pressed_key is not None and _last_pressed_key != vkey:
            # resend last keypress if another key is pressed
            send_input(vk_to_input(_last_pressed_key, pressed=False))
            _last_pressed_key = None
            _last_pressed_time = None
    elif _last_pressed_key == vkey and is_hodling_hotkey:
        # check if holding time is long enough
        min_hold_time, func, error_handler = _holding_hotkeys[vkey]
        if time.time() - _last_pressed_time >= min_hold_time:
            # wrap func with in try-catch for safty
            def wrapped_func():
                try:
                    func()
                except Exception as e:
                    error_handler(e)

            # execute hook in a separate thread for performance
            _executor.submit(wrapped_func)
            swallow = True
        _last_pressed_key = None
        _last_pressed_time = None
        if swallow:
            return True

    # then check if combination matches
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


# install hook
hook.hook_keyboard(input_event_handler)
hook.hook_mouse(input_event_handler)

if __name__ == "__main__":
    import time
    from functools import partial

    def delay_hello():
        time.sleep(1)
        print("hello world")

    hotkey([Vk.LWIN, Vk.B], delay_hello, True)
    # hotkey([Vk.XBUTTON1, Vk.LBUTTON], delay_hello, True)
    # hotkey([Vk.XBUTTON2, Vk.LBUTTON], delay_hello, True)
    # holding_hotkey(Vk.XBUTTON2, partial(print, "holding X2"))

    hook.message_loop()
