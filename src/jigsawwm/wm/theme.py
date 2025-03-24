"""Theme"""

from dataclasses import dataclass
from typing import Callable, Optional

from jigsawwm.tiler import tilers
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
    layout_tiler: tilers.LayoutTiler
    static_layout: bool = False
    max_tiling_areas: int = 0
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
    stacking_margin_x: float = 0.1
    stacking_margin_y: float = 0.1
    stacking_window_width: float = 0.8
    stacking_window_height: float = 0.8
    stacking_max_step: int = 30

    # Theme(
    #     name="OBS Dwindle",
    #     layout_tiler=tilers.obs_dwindle_layout_tiler,
    #     icon_name="obs.png",
    #     gap=2,
    #     strict=True,
    # ),


static_bigscreen_8 = Theme(
    name="static_bigscreen_8",
    layout_tiler=tilers.static_bigscreen_8_layout_tiler,
    static_layout=True,
    max_tiling_areas=8,
    strict=True,
    gap=2,
    new_window_as_master=True,
    affinity_index=(lambda si: 10 if si.inch >= 40 else 0),
)
dwindle = Theme(
    name="Dwindle",
    layout_tiler=tilers.ratio_dwindle_layout_tiler,
    max_tiling_areas=3,
    strict=True,
    gap=4,
    new_window_as_master=True,
    affinity_index=(
        lambda si: (4 if si.inch >= 20 else 0) + (5 if 1 < si.ratio < 2 else 0)
    ),
)
dwindle_static = Theme(
    name="Dwindle Static",
    layout_tiler=tilers.ratio_dwindle_layout_tiler,
    max_tiling_areas=3,
    # windows with static index defined in rules would be placed into the specified position
    static_layout=True,
    strict=True,
    gap=20,
    new_window_as_master=True,
    affinity_index=lambda si: (4 if si.inch >= 20 else 0)
    + (5 if 1 < si.ratio < 2 else 0),
)
mono = Theme(
    name="Mono",
    layout_tiler=tilers.mono_layout_tiler,
    strict=True,
    affinity_index=lambda si: (
        10 if si.inch < 20 or (si.width_px == 2048 and si.height_px == 1536) else 0
    ),
)
widescreen_dwindle = Theme(
    name="WideScreen Dwindle",
    layout_tiler=tilers.widescreen_dwindle_layout_tiler,
    max_tiling_areas=4,
    icon_name="wide-dwindle.png",
    gap=2,
    strict=True,
    new_window_as_master=True,
    affinity_index=lambda si: (4 if si.inch >= 20 else 0)
    + (5 if si.ratio < 1 or si.ratio >= 2 else 0),
)

all_themes = [
    static_bigscreen_8,
    dwindle,
    dwindle_static,
    mono,
    widescreen_dwindle,
]
