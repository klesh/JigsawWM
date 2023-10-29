import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, Union

from jigsawwm.w32.sendinput import send_combination
from jigsawwm.w32.vk import Vk, parse_combination

from .core import *

logger = logging.getLogger(__name__)

JmkHotkeyComb = Union[List[Vk], str]


@dataclass
class JmkHotkey:
    keys: typing.List[Vk]
    # when hotkey is triggered, this callback will be executed
    callback: typing.Callable
    # when all modifiers are released, this callback will be executed
    release_callback: typing.Callable = None
    triggerred: bool = False

    def trigger(self):
        logger.info("hotkey triggered: %s", self.keys)
        self.triggerred = True
        execute(self.callback)

    def release(self):
        if not self.triggerred:
            return
        logger.info("hotkey released: %s", self.keys)
        self.triggerred = False
        if self.release_callback:
            execute(self.release_callback)


class JmkHotkeys(JmkHandler):
    """A handler that handles hotkeys."""

    next_handler: JmkHandler
    combs: typing.Dict[typing.FrozenSet[Vk], JmkHotkey]
    pressed_modifiers: typing.Set[Vk]
    resend: JmkEvent

    def __init__(
        self,
        next_handler,
        hotkeys: List[Tuple[JmkHotkeyComb, Callable, Optional[Callable]]] = None,
    ):
        self.next_handler = next_handler
        self.combs = {}
        self.pressed_modifiers = set()
        self.resend = None
        if hotkeys:
            for args in hotkeys:
                self.register(*args)

    @staticmethod
    def expand_comb(comb: JmkHotkeyComb) -> List[List[Vk]]:
        if isinstance(comb, str):
            comb = parse_combination(comb)
        for key in comb[:-1]:
            if key not in Modifers:
                raise TypeError("hotkey keys must be a list of Modifers and a Vk")
            if comb[-1] in Modifers:
                raise TypeError("hotkey keys must be a list of Modifers and a Vk")
        return expand_combination(comb)

    def register(
        self, comb: JmkHotkeyComb, cb: Union[Callable, str], release_cb: Callable = None
    ):
        if isinstance(cb, str):
            new_comb = parse_combination(cb)
            cb = lambda: send_combination(*new_comb)
        for keys in self.expand_comb(comb):
            hotkey = JmkHotkey(keys, cb, release_cb)
            self.combs[frozenset(keys)] = hotkey

    def unregister(self, comb: JmkHotkeyComb):
        for keys in self.expand_comb(comb):
            self.combs.pop(frozenset(keys))

    def find_hotkey(self, evt: JmkEvent) -> typing.Optional[JmkHotkey]:
        pressed_keys = self.pressed_modifiers.copy()
        pressed_keys.add(evt.vk)
        hotkey = self.combs.get(frozenset(pressed_keys))
        # wheel up/down don't have pressed event
        if evt.vk == Vk.WHEEL_UP or evt.vk == Vk.WHEEL_DOWN:
            pressed_keys.add(evt.vk)
        logger.debug("current pressed keys: %s", pressed_keys)
        return hotkey

    def __call__(self, evt: JmkEvent) -> bool:
        logger.debug("%s >>> hotkey", evt)
        if evt.pressed:
            if evt.vk in Modifers:
                self.pressed_modifiers.add(evt.vk)
            else:
                # swallow non-modifier keypress event if hotkey is registered
                hotkey = self.find_hotkey(evt)
                if hotkey and hotkey.keys[-1] == evt.vk:
                    evt.system = False
                    self.resend = evt
                    return True
        else:
            if evt.vk in self.pressed_modifiers:
                self.pressed_modifiers.remove(evt.vk)
                if not self.pressed_modifiers:
                    for hotkey in self.combs.values():
                        hotkey.release()
            else:
                hotkey = self.find_hotkey(evt)
                if hotkey:
                    if len(hotkey.keys) == 2 and hotkey.keys[0] in (
                        Vk.LWIN,
                        Vk.RWIN,
                    ):
                        # prevent start menu from popping up
                        self.next_handler(JmkEvent(Vk.NONAME, False))
                    self.resend = None
                    hotkey.trigger()
                    return True  # maybe let user define whether to swallow
                elif (
                    self.resend
                ):  # modifier key released first, so we resend previous event
                    logger.debug("resend >>> %s", self.resend)
                    self.next_handler(self.resend)
                    self.resend = None

        return self.next_handler(evt)
