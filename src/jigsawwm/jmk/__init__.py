"""Jigsaw Multi-Key (JMK) module - A QMK a-like key mapping system"""

from typing import Callable, List, Tuple

from .core import *
from .hotkey import *

# from .combo import *
from .sysinout import *


def create_jmk(
    layers: List[JmkLayer],
    hotkeys: List[Tuple[JmkCombination, Callable]],
    # combos: List[Tuple[List, Callable]],
    bypass_exe: Set[str] = None,
):
    """Create a JMK state machine"""
    sysin = SystemInput(bypass_exe)
    core = JmkCore(layers)
    # combos = JmkCombos(combos)
    hotkeys = JmkHotkeys(hotkeys)
    sysout = SystemOutput()
    sysin.pipe(core).pipe(hotkeys).pipe(sysout)
    return sysin, core, hotkeys, sysout
