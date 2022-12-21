from .layouts import Layout, plug_rect, dwindle, widescreen_dwindle
from typing import Iterator, Callable, Tuple
from functools import partial

# Rect holds physical coordinate for rectangle (left/top/right/bottom)
Rect = Tuple[int, int, int, int]

# Tiler generates physical Rects for specified total number of windows based on given Layout
Tiler = Callable[[Layout, Rect, int], Iterator[Rect]]

# LayoutTiler generates physical Rects for specified total number of windows
LayoutTiler = Callable[[Rect, int], Iterator[Rect]]


def direct_tiler(layout: Layout, work_area: Rect, total_windows: int) -> Iterator[Rect]:
    """Generates physical Rects for work_area Rect with specified layout"""
    for float_rect in layout(total_windows):
        yield tuple(int(f) for f in plug_rect(float_rect, work_area))


def obs_tiler(
    layout: Layout,
    work_area: Rect,
    total_windows: int,
    obs_width: int = 1920,
    obs_height: int = 1080,
) -> Iterator[Rect]:
    """Generates physical Rects for work_area Rect with specified layout, but leave a
    reserved area on top right corner for OBS recording
    """
    wl, wt, wr, wb = work_area
    scr_width, scr_height = wr - wl, wb - wt
    # fallback to direct_tiler when work_area is smaller than obs reserved area
    if obs_width >= scr_width or obs_height >= scr_height:
        return direct_tiler(work_area, layout, total_windows)
    fr = wr - obs_width
    # first window on the left
    yield wl, wt, fr, wb
    if total_windows == 1:
        return
    # second window on the bottom right
    yield fr, wt + obs_height, wr, wb
    if total_windows == 2:
        return
    obs_rect = (fr, wt, wr, wt + obs_height)
    yield from direct_tiler(layout, obs_rect, total_windows - 2)


dwindle_layout_tiler: LayoutTiler = partial(direct_tiler, dwindle)
widescreen_dwindle_layout_tiler: LayoutTiler = partial(direct_tiler, widescreen_dwindle)
obs_dwindle_layout_tiler: LayoutTiler = partial(obs_tiler, dwindle)

if __name__ == "__main__":
    print("direct dwindle")
    for n in range(1, 5):
        print(
            list(
                direct_tiler(
                    layout=dwindle,
                    work_area=(10, 10, 3450, 1450),
                    total_windows=n,
                )
            )
        )
    print("obs dwindle")
    for n in range(1, 5):
        print(
            list(
                obs_tiler(
                    layout=dwindle,
                    work_area=(10, 10, 3450, 1450),
                    total_windows=n,
                )
            )
        )
