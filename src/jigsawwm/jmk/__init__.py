from typing import Callable, List, Tuple

from .core import *
from .hotkey import *
from .sysinout import *


def create_jmk(
    layers: List[JmkLayer],
    hotkeys: List[Tuple[JmkHotkeyComb, Callable]],
    always_swallow: bool = True,
    bypass_exe: Set[str] = None,
):
    # from tail to head
    sysout = SystemOutput(always_swallow)
    hks = JmkHotkeys(sysout, hotkeys)
    jmk = JmkCore(hks, layers)
    sysin = SystemInput(jmk, bypass_exe)
    return sysin, jmk, hks, sysout
