"""Hotkey handler for JigsawWM."""
import logging
from typing import Callable, List, Optional, Tuple

from jigsawwm.w32.vk import Vk

from .shared import * # pylint: disable=wildcard-import, unused-wildcard-import

logger = logging.getLogger(__name__)

class JmkCombos(JmkTriggers):
    """A handler that handles combos."""
    queue: typing.List[JmkEvent]
    term = 0.2

    def __init__(
        self,
        next_handler,
        combos: List[Tuple[JmkCombination, Callable, Optional[Callable]]] = None,
        term: float = 0.2,
    ):
        super().__init__(next_handler, combos)
        self.queue = []
        self.term = term

    def check_comb(self, comb: typing.List[Vk]):
        if len(comb) < 2:
            raise TypeError("combo keys must consist of at least two keys")

    def __call__(self, evt: JmkEvent) -> bool:
        if evt.pressed:
            for keys in self.triggers:
                if evt.vk in keys:
                    trigger = self.triggers[keys]
                    if trigger.first_lit_at is None:
                        trigger.lit_keys = {evt.vk}
                        trigger.first_lit_at = evt.time
                        self.queue.append(evt)
                    elif evt.time - trigger.first_lit_at <= self.term:
                        trigger.lit_keys.add(evt.vk)
                        if trigger.lit_keys == keys:
                            trigger.trigger()
                            self.queue = [e for e in self.queue if e.vk not in keys]
                            return True
                    else:
                        trigger.first_lit_at = None
                        for resend in self.queue:
                            super().__call__(resend)
        else:
            for keys in self.triggers:
                if evt.vk in keys:
                    trigger = self.triggers[keys]
                    if trigger.triggerred:
                        trigger.lit_keys.remove(evt.vk)
                        if not trigger.lit_keys:
                            trigger.release()
                        return True
                        
        return super().__call__(evt)
