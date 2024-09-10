"""Hotkey handler for JigsawWM."""

import logging
from typing import List, FrozenSet

from jigsawwm.jmk.core import JmkEvent
from jigsawwm.w32.vk import Vk


logger = logging.getLogger(__name__)


class JmkCombo:
    """A class that represents a combo."""

    term: float = 0.2
    comb: FrozenSet[Vk]
    first_key_pressed_at: float = 0.0

    def __init__(self) -> None:
        pass


class JmkCombos:
    """Implement the Combo feature: press multiple keys at the same time to
    execute a callback or send another key instead."""

    combos: List[JmkCombo]

    def __init__(self, combos: List[JmkCombo]):
        for combo in combos:
            self.register(combo)

    def register(self, combo: JmkCombo):
        """Register a combo."""
        self.check_comb(combo)
        self.combos.append(combo)

    def unregister(self, combo: JmkCombo):
        """Unregister a combo."""
        self.combos.remove(combo)

    def check_comb(self, combo: JmkCombo):
        """Check if the combo keys are valid."""
        if len(combo.comb) < 2:
            raise TypeError("combo trigger must consist of at least two keys")
        for c in self.combos:
            if c.comb == combo.comb:
                raise KeyError("combo already registered")

    def __call__(self, evt: JmkEvent):
        for combo in self.combos:
            if evt.vk not in combo.comb:
                continue
