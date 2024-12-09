"""Hotkey handler for JigsawWM."""

import logging
from typing import List, Optional, Set

from jigsawwm.w32.vk import Modifers

from .core import JmkEvent, JmkTrigger, JmkTriggerDefs, JmkTriggers, Vk

logger = logging.getLogger(__name__)


class JmkHotkeys(JmkTriggers):
    """A handler that handles hotkeys."""

    pressed_modifiers: Set[Vk]
    resend: Optional[JmkEvent] = None

    def __init__(
        self,
        hotkeys: JmkTriggerDefs = None,
    ):
        super().__init__(hotkeys)
        self.pressed_modifiers = set()

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
                if hotkey and hotkey.keys[-1] == evt.vk:
                    evt.system = False
                    self.resend = evt
                    return
        else:
            if evt.vk in self.pressed_modifiers:
                self.pressed_modifiers.remove(evt.vk)
                if not self.pressed_modifiers:
                    for hotkey in self.triggers.values():
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
                    return
                elif (
                    self.resend
                ):  # modifier key got released first, so we have to resend the previous key event
                    logger.debug("resend >>> %s", self.resend)
                    self.next_handler(self.resend)
                    self.resend = None

        super().__call__(evt)
