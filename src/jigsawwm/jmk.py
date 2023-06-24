import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from threading import Lock
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
from jigsawwm.w32.vk import Vk, expand_combination, parse_combination, parse_key

logger = logging.getLogger(__name__)
# for executing callback function
_executor = ThreadPoolExecutor()
handle_exc = traceback.print_exc


@dataclass
class Hotkey:
    keys: Sequence[Vk]
    callback: Callable
    swallow: bool = True


@dataclass
class Holdtap:
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


class Jmk:
    hotkeys: Dict[FrozenSet[Vk], Hotkey]
    holdtaps: Dict[Vk, Holdtap]
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
    swallow_up = set()
    double_tap_term: int = 300 * 1e6
    tapped: Tuple[Optional[Vk], int] = (None, 0)
    tap_tap_hold: Optional[Vk] = None
    _lock: Lock

    def __init__(self):
        self.hotkeys = {}
        self.holdtaps = {}
        self.pressed_keys = dict()
        self.queue = []
        self.extra_modifers = set()
        self._lock = Lock()

    def hotkey(self, hotkey: Hotkey):
        self.hotkeys[frozenset(hotkey.keys)] = hotkey
        # register modifiers, we may need to swallow and resend
        if hotkey.swallow:
            for key in hotkey.keys[:-1]:
                if key not in self.modifiers:
                    if key in self.holdtaps:
                        raise ValueError(
                            "cannot register a combination with holdkey as modifier"
                        )
                    self.extra_modifers.add(key)

    def holdtap(self, holdtap: Holdtap):
        if holdtap.key in self.extra_modifers or holdtap.key in self.modifiers:
            raise ValueError(
                "cannot register a holdkey that is a modifier or used in combinations"
            )
        self.holdtaps[holdtap.key] = holdtap

    def execute(self, func: Callable):
        try:
            func()
        except:
            handle_exc()

    def event(
        self, key: Vk, pressed: bool
    ) -> Tuple[bool, Optional[Sequence[Tuple[Vk, bool]]]]:
        # ignore duplicatedkeydown event
        if pressed and key in self.pressed_keys:
            return True, None
        # passthrough tap-tap-hold
        if self.tap_tap_hold:
            if self.tap_tap_hold == key:
                if not pressed:
                    self.tap_tap_hold = None
                return False, None
            else:
                self.tap_tap_hold = None
        # maintain the queue
        swallow = False
        resend = None
        if (
            self.queue
            or (key in self.extra_modifers and pressed)
            or (key in self.holdtaps and pressed)
        ):
            swallow = True
            self.queue.append((key, pressed))

        if pressed:
            # update press state
            if key < Vk.KB_BOUND:
                self.pressed_keys[key] = time.time_ns()
            # holding key
            if key in self.holdtaps:
                holdtap = self.holdtaps[key]
                swallow = holdtap.swallow

                def holding_timer():
                    time.sleep(holdtap.term_s)
                    pressed_ts = self.pressed_keys.get(key)
                    if pressed_ts and time.time_ns() - pressed_ts > holdtap.term_ns:
                        # trigger the down callback if specified
                        if holdtap.down:
                            logger.debug("triggering holdkey %s down callback", key)
                            _executor.submit(self.execute, holdtap.down)
                        # mark the key as held
                        self.held.add(key)
                        # clear the key from the queue
                        with self._lock:
                            self.queue = [k for k in self.queue if k[0] != key]

                _executor.submit(self.execute, holding_timer)
            else:
                # combination match
                hotkey = self.hotkeys.get(frozenset(self.pressed_keys.keys()))
                if hotkey:
                    swallow = hotkey.swallow
        else:
            # preserve the potential hotkey match
            pressed_keys = [k for k in self.pressed_keys]
            if key > Vk.KB_BOUND:
                pressed_keys.append(key)
            hotkey = self.hotkeys.get(frozenset(pressed_keys))
            # update the state
            if key < Vk.KB_BOUND:
                self.pressed_keys.pop(key)
            if self.tapped[0] != key or self.tapped[1] < time.time_ns():
                self.tapped = (key, time.time_ns() + self.double_tap_term)
            else:
                self.tap_tap_hold = key
            if key in self.holdtaps:
                holdtap = self.holdtaps[key]
                swallow = holdtap.swallow
                # trigger the up callback only if the key is held long enough
                if key in self.held:
                    if holdtap.up:
                        logger.debug("triggering holdkey %s up callback", key)
                        _executor.submit(self.execute, holdtap.up)
                    self.held.remove(key)
                elif holdtap.tap:
                    logger.debug("triggering holdkey %s tap callback", key)
                    _executor.submit(self.execute, holdtap.tap)
                else:
                    resend = [(key, True), (key, False)]
                with self._lock:
                    self.queue = [k for k in self.queue if k[0] != key]
            else:
                # BINGO if the last key matched
                if hotkey and hotkey.keys[-1] == key:
                    swallow = hotkey.swallow
                    logger.debug("triggering hotkey %s callback", hotkey.keys)
                    _executor.submit(self.execute, hotkey.callback)
                    # send a key up to interrupt the combination
                    if len(hotkey.keys) == 2 and hotkey.keys[0] in (Vk.LWIN, Vk.RWIN):
                        # to prevent the start menu from popping up
                        resend = [(Vk.NONAME, False)]
                    if swallow:
                        # remove extra modifiers from the queue
                        extra_modifers = set(
                            vk for vk in hotkey.keys[:-1] if vk in self.extra_modifers
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


class Group:
    def __init__(self, name="noname"):
        self.name = name
        self.hotkeys = []
        self.holdtaps = []

    def hotkey(
        self,
        combination: Union[Sequence[Vk], str],
        target: Union[Callable, Union[Sequence[Vk], str]],
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
        :param swallow: stop combination being processed by other apps
        """
        # parse combkeys if it is string
        if isinstance(combination, str):
            combination = parse_combination(combination)
        # check if combination valid
        if not combination:
            raise ValueError("empty combination")
        # turn target to function if it is string
        if isinstance(target, str):
            target = parse_combination(target)
        if isinstance(target, Sequence):
            target = partial(send_combination, target)

        # count = len(list(filter(lambda vk: vk.name not in Modifier.__members__, combkeys)))
        # if count != 1:
        #     raise Exception("require 1 and only 1 triggering key")
        if len(combination) == 0:
            raise ValueError("empty combination")
        for ck in expand_combination(combination):
            hk = Hotkey(keys=ck, callback=target, swallow=swallow)
            core.hotkey(hk)
            self.hotkeys.append(hk)

    def holdtap(
        self,
        key: Union[Vk, str],
        hold: Union[Callable, Union[Vk, str]] = None,
        tap: Union[Callable, Union[Vk, str]] = None,
        term: int = 200,
        swallow: bool = True,
    ):
        """Register a holdtap key

        :param key: VirtualKey | str, the key to be intercepted
        :param hold: Callable | Vk | str, the function to be executed or key to be sent when the key is held longer than `term`
        :param tap: Callable | Vk | str, the function to be executed or key to be sent when the key is tapped
        :param term: int, the time in ms to trigger the hold callback
        :param swallow: bool, stop key being processed by other apps
        """
        if not hold and not tap:
            raise ValueError("hold and tap cannot be both None")
        if isinstance(key, str):
            key = parse_key(key)
        if isinstance(hold, str):
            hold = parse_key(hold)
        up, down = None, None
        if isinstance(hold, Sequence):
            up = partial(send_input, vk_to_input(hold, False))
            down = partial(send_input, vk_to_input(hold, True))
        elif isinstance(hold, Callable):
            down = hold
        if isinstance(tap, str):
            tap = parse_key(tap)
            tap = partial(send_input, vk_to_input(tap, True), vk_to_input(tap, False))

        ht = Holdtap(key=key, up=up, down=down, term=term, swallow=swallow, tap=tap)
        core.holdtap(ht)
        self.holdtaps.append(ht)

    def uninstall(self):
        for hk in self.hotkeys:
            core.hotkeys.pop(frozenset(hk.keys))
        self.hotkeys.clear()
        for ht in self.holdtaps:
            core.holdtaps.pop(ht.key)
        self.holdtaps.clear()


core = Jmk()
default_group = Group("default group")
hotkey = default_group.hotkey
holdtap = default_group.holdtap


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
        if (
            msgid == hook.KBDLLHOOKMSGID.WM_KEYDOWN
            or msgid == hook.KBDLLHOOKMSGID.WM_SYSKEYDOWN
        ):
            pressed = True
        elif (
            msgid == hook.KBDLLHOOKMSGID.WM_KEYUP
            or msgid == hook.KBDLLHOOKMSGID.WM_SYSKEYUP
        ):
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

    swallow, resend = core.event(vkey, pressed)
    logger.debug(
        "key: %s, pressed: %s, swallow: %s, resend: %s",
        vkey.name,
        pressed,
        swallow,
        resend,
    )
    if resend:
        _executor.submit(lambda: send_input(*(vk_to_input(k, p) for k, p in resend)))
    return swallow


hook_ids = []


# install hook, do NOT call this function when debugging
def install_hotkey_hooks():
    global hook_ids
    if hook_ids:
        return
    hook_ids = [
        hook.hook_keyboard(input_event_handler),
        hook.hook_mouse(input_event_handler),
    ]


if __name__ == "__main__":
    import time
    from functools import partial

    logging.basicConfig(level=logging.DEBUG)

    def delay_hello():
        time.sleep(1)
        print("hello world")

    def raise_error():
        raise ValueError("test")

    # hotkey([Vk.LWIN, Vk.B], delay_hello, True)
    # hotkey([Vk.LCONTROL, Vk.B], delay_hello, True)
    # hotkey([Vk.XBUTTON1, Vk.LBUTTON], delay_hello, True)
    # hotkey([Vk.XBUTTON2, Vk.LBUTTON], partial(print, "hello"), True)
    # holdtap(
    #     Vk.XBUTTON1,
    #     hold=partial(print, "holding xbutton1"),
    # )
    # hotkey([Vk.XBUTTON2, Vk.WHEEL_UP], partial(print, "X2 + WHEEL_UP"))
    # hotkey("Q+W", raise_error, True)
    hotkey("Q+W", partial(print, "E+R"))
    # holdtap("W", hold=partial(print, "W"))

    # hotkey("E+R", partial(print, "E+R"), False)
    # g = Group()
    # g.holdtap(Vk.CAPITAL, hold=Vk.LCONTROL, tap=lambda: g.uninstall_all())

    install_hotkey_hooks()
    hook.message_loop()
