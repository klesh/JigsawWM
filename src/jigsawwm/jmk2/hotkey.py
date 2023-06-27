import logging
from dataclasses import dataclass
from typing import Callable, List, Tuple, Union

from jigsawwm.w32.vk import Vk, parse_combination

from .core import *

logger = logging.getLogger(__name__)

JmkHotkeyComb = Union[List[Vk], str]


@dataclass
class JmkHotkey:
    keys: typing.List[Vk]
    callback: typing.Callable


class JmkHotkeys(JmkHandler):
    next_handler: JmkHandler
    combs: typing.Dict[typing.FrozenSet[Vk], JmkHotkey]
    pressed_keys: typing.Set[Vk]
    resend: JmkEvent

    def __init__(
        self, next_handler, hotkeys: List[Tuple[JmkHotkeyComb, Callable]] = None
    ):
        self.next_handler = next_handler
        self.combs = {}
        self.pressed_keys = set()
        self.resend = None
        if hotkeys:
            for comb, cb in hotkeys:
                self.register(comb, cb)

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

    def register(self, comb: JmkHotkeyComb, cb: Callable):
        for keys in self.expand_comb(comb):
            hotkey = JmkHotkey(keys, cb)
            self.combs[frozenset(keys)] = hotkey

    def unregister(self, comb: JmkHotkeyComb):
        for keys in self.expand_comb(comb):
            self.combs.pop(frozenset(keys))

    def __call__(self, evt: JmkEvent) -> bool:
        logger.debug("%s >>> hotkey", evt)
        if evt.pressed:
            self.pressed_keys.add(evt.vk)
            hotkey = self.combs.get(frozenset(self.pressed_keys))
            # swallow keypress if hotkey is registered
            if hotkey and hotkey.keys[-1] == evt.vk:
                evt.system = False
                self.resend = evt
                return True
        else:
            pressed_keys = self.pressed_keys.copy()
            # wheel up/down don't have pressed event
            if evt.vk == Vk.WHEEL_UP or evt.vk == Vk.WHEEL_DOWN:
                pressed_keys.add(evt.vk)
            else:
                # if evt.vk not in pressed_keys:
                #     import traceback

                #     traceback.print_stack()
                if evt.vk in self.pressed_keys:
                    self.pressed_keys.remove(evt.vk)
            hotkey = self.combs.get(frozenset(pressed_keys))
            if hotkey:
                self.resend, resend = None, self.resend
                if hotkey.keys[-1] == evt.vk:  # trigger key matched
                    if len(hotkey.keys) == 2 and hotkey.keys[0] in (Vk.LWIN, Vk.RWIN):
                        # prevent start menu from popping up
                        self.next_handler(JmkEvent(Vk.NONAME, False))
                    execute(hotkey.callback)
                    return True  # maybe let user define whether to swallow
                elif hotkey:  # modifier key released first
                    self.next_handler(resend)

        return self.next_handler(evt)
