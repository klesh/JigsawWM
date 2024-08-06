from typing import Callable, List, Tuple

from .core import *
from .hotkey import *
from .combo import *
from .sysinout import *


def create_jmk(
    layers: List[JmkLayer],
    hotkeys: List[Tuple[JmkCombination, Callable]],
    combos: List[Tuple[List, Callable]],
    always_swallow: bool = True,
    bypass_exe: Set[str] = None,
):
    # from tail to head
    sysout = SystemOutput(always_swallow)
    hks = JmkHotkeys(sysout, hotkeys)
    # cbs = JmkCombos(hks, combos)
    # jmk = JmkCore(cbs, layers)
    jmk = JmkCore(hks, layers)
    sysin = SystemInput(jmk, bypass_exe)
    return sysin, jmk, hks, sysout
