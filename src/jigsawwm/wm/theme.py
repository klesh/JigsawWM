from dataclasses import dataclass
from typing import Optional

from jigsawwm.tiler.tilers import *
from jigsawwm.w32.monitor import Monitor


@dataclass
class Theme:
    """Theme is a set of preference packed together for users to switch easily,
    typically, it consists of a LayoutTiler, Gap between windows and
    other options.
    """

    # name of the theme
    name: str
    # layout tiler
    layout_tiler: LayoutTiler
    static_layout = False
    max_tiling_windows = 4
    # unused
    icon_name: Optional[str] = None
    # unused
    icon_path: Optional[str] = None
    # new appeared window would be prepended to the list if the option was set to True
    new_window_as_master: Optional[bool] = None
    # gap between windows / monitor edges
    gap: Optional[int] = 0
    # forbid
    strict: Optional[bool] = None
    affinity_index: Optional[Callable[[Monitor], int]] = None
