"""Hotkey handler for JigsawWM."""

import logging
import time
from typing import List, Optional, Set

from jigsawwm.w32.vk import Modifers

from .core import JmkEvent, JmkTrigger, JmkTriggerDefs, JmkTriggers, Vk

logger = logging.getLogger(__name__)


class JmkHotkeys(JmkTriggers):
    """A handler that handles hotkeys."""

    pressed_modifiers: Set[Vk]
    to_be_swallowed: Optional[Vk] = None

    def __init__(
        self,
        hotkeys: JmkTriggerDefs = None,
    ):
        super().__init__(hotkeys)
        self.pressed_modifiers = set()
        self.to_be_swallowed = None

    def check_comb(self, comb: List[Vk]):
        for key in comb[:-1]:
            if key not in Modifers:
                raise TypeError("hotkey keys must be a list of Modifers and a Vk")
            if comb[-1] in Modifers:
                raise TypeError("hotkey keys must be a list of Modifers and a Vk")

    def find_hotkey(self, evt: JmkEvent) -> Optional[JmkTrigger]:
        """Find a hotkey that matches the current pressed keys."""
        pressed_keys = self.pressed_modifiers.copy()
        pressed_keys.add(evt.vk)
        hotkey = self.triggers.get(frozenset(pressed_keys))
        # wheel up/down don't have pressed event
        if evt.vk == Vk.WHEEL_UP or evt.vk == Vk.WHEEL_DOWN:
            pressed_keys.add(evt.vk)
        logger.debug("current pressed keys: %s", pressed_keys)
        return hotkey

    def __call__(self, evt: JmkEvent):
        logger.debug("%s >>> hotkey", evt)
        if evt.pressed:
            if evt.vk in Modifers:
                self.pressed_modifiers.add(evt.vk)
            else:
                # swallow non-modifier keypress event if hotkey is registered
                hotkey = self.find_hotkey(evt)
                if hotkey:
                    if len(hotkey.keys) == 2 and hotkey.keys[0] in (
                        Vk.LWIN,
                        Vk.RWIN,
                    ):
                        # prevent start menu from popping up
                        self.next_handler(JmkEvent(Vk.NONAME, False))
                    # release current pressed modifiers in case trigger sends combination
                    for modifier in self.pressed_modifiers:
                        self.next_handler(JmkEvent(modifier, False))
                    time.sleep(0.01)  # allow active window to receive the key up events
                    hotkey.trigger()
                    # restore pressed modifiers
                    # for modifier in self.pressed_modifiers:
                    #     self.next_handler(JmkEvent(modifier, True))
                    # self.next_handler(JmkEvent(Vk.NONAME, False))
                    self.to_be_swallowed = evt.vk
                    return
        else:
            if evt.vk in self.pressed_modifiers:
                self.pressed_modifiers.remove(evt.vk)
                if not self.pressed_modifiers:
                    for hotkey in self.triggers.values():
                        hotkey.release()
            elif self.to_be_swallowed == evt.vk:
                self.to_be_swallowed = None
                return

        super().__call__(evt)
