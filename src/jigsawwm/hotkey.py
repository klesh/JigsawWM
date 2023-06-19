import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from threading import Lock
from traceback import print_exception
from typing import (
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

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


@dataclass
class Combination:
    keys: Sequence[Vk]
    callback: Callable
    swallow: bool = True


@dataclass
class Holding:
    key: Vk
    down: Optional[Callable] = None
    up: Optional[Callable] = None
    term: int = 200
    swallow: bool = True

    @property
    def term_ns(self):
        return self.term * 1e6

    @property
    def term_s(self):
        return self.term * 1e-3


class Hotkeys:
    combinations: Dict[FrozenSet[Vk], Combination]
    holdkeys: Dict[Vk, Holding]
    pressed_keys: Dict[Vk, int]
    queue: List[Tuple[Vk, bool]]
    modifiers = [
        Vk.LSHIFT,
        Vk.LCONTROL,
        Vk.LMENU,
        Vk.LWIN,
        Vk.RSHIFT,
        Vk.RCONTROL,
        Vk.RMENU,
        Vk.RWIN,
    ]
    extra_modifers: Set[Vk]
    held = set()
    _lock: Lock

    def __init__(self):
        self.combinations = {}
        self.holdkeys = {}
        self.pressed_keys = dict()
        self.queue = []
        self.extra_modifers = set()
        self._lock = Lock()

    def combination(self, comb: Combination):
        self.combinations[frozenset(comb.keys)] = comb
        # register modifiers, we may need to swallow and resend
        if comb.swallow:
            for key in comb.keys[:-1]:
                if key not in self.modifiers:
                    if key in self.holdkeys:
                        raise ValueError(
                            "cannot register a combination with holdkey as modifier"
                        )
                    self.extra_modifers.add(key)

    def holding(self, holdkey: Holding):
        if holdkey.key in self.extra_modifers or holdkey.key in self.modifiers:
            raise ValueError(
                "cannot register a holdkey that is a modifier or used in combinations"
            )
        self.holdkeys[holdkey.key] = holdkey

    def event(
        self, key: Vk, pressed: bool
    ) -> Tuple[bool, Optional[Sequence[Tuple[Vk, bool]]]]:
        swallow = False
        resend = None
        # maintain the queue
        if (
            self.queue
            or (key in self.extra_modifers and pressed)
            or (key in self.holdkeys and pressed)
        ):
            swallow = True
            self.queue.append((key, pressed))

        if pressed:
            # update press state
            if key < Vk.KB_BOUND:
                self.pressed_keys[key] = time.time_ns()
            # holding key
            if key in self.holdkeys:
                holdkey = self.holdkeys[key]
                swallow = holdkey.swallow

                def holding_timer():
                    time.sleep(holdkey.term_s)
                    pressed_ts = self.pressed_keys.get(key)
                    if pressed_ts and time.time_ns() - pressed_ts > holdkey.term_ns:
                        with self._lock:
                            # mark the key as held
                            self.held.add(key)
                            if holdkey.swallow and key in self.extra_modifers:
                                self.queue.remove((key, True))
                            if holdkey.down:
                                _executor.submit(holdkey.down)

                _executor.submit(holding_timer)

            # combination match
            else:
                comb = self.combinations.get(frozenset(self.pressed_keys.keys()))
                if comb:
                    swallow = comb.swallow
        else:
            # preserve the potential hotkey match
            comb = self.combinations.get(frozenset(self.pressed_keys.keys()))
            # update the state
            if key < Vk.KB_BOUND:
                self.pressed_keys.pop(key)
            if key in self.held:
                holdkey = self.holdkeys[key]
                swallow = holdkey.swallow
                with self._lock:
                    self.held.remove(key)
                    if holdkey.swallow and key in self.extra_modifers:
                        self.queue.pop()
                if holdkey.up:
                    _executor.submit(holdkey.up)
            else:
                # BINGO if the last key matched
                if comb and comb.keys[-1] == key:
                    swallow = comb.swallow
                    _executor.submit(comb.callback)
                elif self.queue:
                    swallow = True
                    with self._lock:
                        resend, self.queue = self.queue, []
        return swallow, resend


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
def install_hotkey_hooks():
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

    install_hotkey_hooks()
    hook.message_loop()
