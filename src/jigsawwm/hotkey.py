import logging
import time
from concurrent.futures import ThreadPoolExecutor
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
from jigsawwm.w32.vk import Vk, expand_combination, parse_combination

logger = logging.getLogger(__name__)
# for executing callback function
_executor = ThreadPoolExecutor()


@dataclass
class Hotkey:
    keys: Sequence[Vk]
    callback: Callable
    swallow: bool = True


@dataclass
class Holdkey:
    key: Vk
    down: Optional[Callable] = None
    up: Optional[Callable] = None
    term: int = 200
    swallow: bool = True
    tap: Optional[Callable] = None

    @property
    def term_ns(self):
        return self.term * 1e6

    @property
    def term_s(self):
        return self.term * 1e-3


class Hotkeys:
    combinations: Dict[FrozenSet[Vk], Hotkey]
    holdkeys: Dict[Vk, Holdkey]
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
    error_handler: Callable[[Exception], None] = print_exception
    swallow_up = set()
    _lock: Lock

    def __init__(self):
        self.combinations = {}
        self.holdkeys = {}
        self.pressed_keys = dict()
        self.queue = []
        self.extra_modifers = set()
        self._lock = Lock()

    def hotkey(self, comb: Hotkey):
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

    def holdkey(self, holdkey: Holdkey):
        if holdkey.key in self.extra_modifers or holdkey.key in self.modifiers:
            raise ValueError(
                "cannot register a holdkey that is a modifier or used in combinations"
            )
        self.holdkeys[holdkey.key] = holdkey

    def execute(self, func: Callable):
        try:
            func()
        except Exception as e:
            self.error_handler(e)

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
            if key in self.pressed_keys:
                return swallow, resend
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
                        # trigger the down callback if specified
                        if holdkey.down:
                            _executor.submit(self.execute, holdkey.down)
                        # mark the key as held
                        self.held.add(key)
                        # clear the key from the queue
                        with self._lock:
                            self.queue = [k for k in self.queue if k[0] != key]

                _executor.submit(self.execute, holding_timer)
            else:
                # combination match
                comb = self.combinations.get(frozenset(self.pressed_keys.keys()))
                if comb:
                    swallow = comb.swallow
        else:
            # for wheel up/down that has no up/down events
            pressed_keys = [k for k in self.pressed_keys]
            if key > Vk.KB_BOUND:
                pressed_keys.append(key)
            # preserve the potential hotkey match
            comb = self.combinations.get(frozenset(pressed_keys))
            # update the state
            if key < Vk.KB_BOUND:
                self.pressed_keys.pop(key)
            if key in self.holdkeys:
                holdkey = self.holdkeys[key]
                swallow = holdkey.swallow
                # trigger the up callback only if the key is held long enough
                if key in self.held:
                    _executor.submit(self.execute, holdkey.up)
                    self.held.remove(key)
                elif holdkey.tap:
                    _executor.submit(self.execute, holdkey.tap)
                with self._lock:
                    self.queue = [k for k in self.queue if k[0] != key]
            else:
                # BINGO if the last key matched
                if comb and comb.keys[-1] == key:
                    swallow = comb.swallow
                    _executor.submit(self.execute, comb.callback)
                    # send a key up to interrupt the combination
                    if Vk.LWIN in comb.keys or Vk.RWIN in comb.keys:
                        # to prevent the start menu from popping up
                        resend = [(Vk.NONAME, False)]
                    if swallow:
                        # remove extra modifiers from the queue
                        extra_modifers = set(
                            vk for vk in comb.keys[:-1] if vk in self.extra_modifers
                        )
                        with self._lock:
                            self.queue = [
                                k
                                for k in self.queue
                                if k[0] != key and k[0] not in extra_modifers
                            ]
                            self.swallow_up.update(extra_modifers)
                elif self.queue:
                    swallow = True
                    with self._lock:
                        resend, self.queue = self.queue, []
                elif key in self.swallow_up:
                    swallow = True
                    self.swallow_up.remove(key)
        return swallow, resend


_hotkeys = Hotkeys()


def set_error_handler(handler: Callable[[Exception], None]):
    _hotkeys.error_handler = handler


def hotkey(
    combkeys: Union[Sequence[Vk], str],
    target: Union[Callable, str],
    swallow: bool = True,
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

    # count = len(list(filter(lambda vk: vk.name not in Modifier.__members__, combkeys)))
    # if count != 1:
    #     raise Exception("require 1 and only 1 triggering key")
    if len(combkeys) == 0:
        raise ValueError("empty combination")
    for ck in expand_combination(combkeys):
        _hotkeys.hotkey(Hotkey(keys=ck, callback=target, swallow=swallow))


def holding_hotkey(
    key: Vk,
    up: Callable = None,
    down: Callable = None,
    tap: Callable = None,
    term: int = 200,
    swallow: bool = True,
):
    _hotkeys.holdkey(
        Holdkey(key=key, up=up, down=down, term=term, swallow=swallow, tap=tap)
    )


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
            pressed = False
    # skip events that out of our interest
    if vkey is None or pressed is None:
        return

    swallow, resend = _hotkeys.event(vkey, pressed)
    logger.debug(
        "key: %s, pressed: %s, swallow: %s, resend: %s",
        vkey.name,
        pressed,
        swallow,
        resend,
    )
    if resend:
        for k, p in resend:
            send_input(vk_to_input(k, p))
    return swallow


# install hook
def install_hotkey_hooks():
    hook.hook_keyboard(input_event_handler)
    hook.hook_mouse(input_event_handler)


if __name__ == "__main__":
    import time
    from functools import partial

    logging.basicConfig(level=logging.DEBUG)

    def delay_hello():
        time.sleep(1)
        print("hello world")

    # hotkey([Vk.LWIN, Vk.B], delay_hello, True)
    # hotkey([Vk.LCONTROL, Vk.B], delay_hello, True)
    # hotkey([Vk.XBUTTON1, Vk.LBUTTON], delay_hello, True)
    # hotkey([Vk.XBUTTON2, Vk.LBUTTON], partial(print, "hello"), True)
    # holding_hotkey(
    #     Vk.XBUTTON1,
    #     down=partial(print, "holding xbutton1"),
    #     tap=partial(print, "tap xbutton1"),
    # )
    # holding_hotkey(
    #     Vk.XBUTTON1,
    #     down=partial(print, "holding xbutton1"),
    #     tap=partial(print, "tap xbutton1"),
    #     swallow=False,
    # )
    # hotkey([Vk.XBUTTON2, Vk.WHEEL_UP], partial(print, "X2 + WHEEL_UP"))
    hotkey("Q+W", partial(print, "Q+W"), True)
    hotkey("E+R", partial(print, "E+R"), False)

    install_hotkey_hooks()
    hook.message_loop()
