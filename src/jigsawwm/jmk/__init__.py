from typing import Callable, List, Tuple
from queue import SimpleQueue

from .core import *
from .hotkey import *
from .sysinout import *


def create_jmk(
    layers: List[JmkLayer],
    hotkeys: List[Tuple[JmkHotkeyComb, Callable]],
    always_swallow: bool = True,
    bypass_exe: Set[str] = None,
):
    sent_queue = SimpleQueue()
    # from tail to head
    sysout = SystemOutput(always_swallow, feedback=sent_queue)
    hks = JmkHotkeys(sysout, hotkeys)
    jmk = JmkCore(hks, layers)
    sysin = SystemInput(jmk, bypass_exe=bypass_exe, feedback=sent_queue)
    return sysin, jmk, hks, sysout
