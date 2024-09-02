"""

The ``tiler`` module is responsible for converting Layout to Physical Coordinates for arbitrary number of windows.

``Rect`` is a tuple with 4 elements (left/top/right/bottom) to describe a rectangle in pixels (integer)

``Tiler`` is a generator which generates Rects with specified Layout for given monitor work area and total number of windows

``LayoutTiler`` is similar to `Tiler` except the Layout was predefined

"""

from typing import Callable, Iterator, Tuple
from functools import partial

from .layouts import (
    Layout,
    dwindle,
    mono,
    static_bigscreen_8,
    plug_rect,
    widescreen_dwindle,
)

# Rect holds physical coordinate for rectangle (left/top/right/bottom)
Rect = Tuple[int, int, int, int]

# Tiler generates physical Rects for specified total number of windows based on given Layout
Tiler = Callable[[Layout, Rect, int], Iterator[Rect]]

# LayoutTiler generates physical Rects for specified total number of windows
LayoutTiler = Callable[[Rect, int], Iterator[Rect]]


def direct_tiler(layout: Layout, work_area: Rect, total_windows: int) -> Iterator[Rect]:
    """The default Tiler which maps specified `Layout` to physical work area directly

    :param layout: a Layout generator
    :param work_area: the monitor work area (taskbar excluded)
    :param total_windows: total number of windows
    :rtype: Iterator[Rect]
    """
    rects = layout(total_windows)
    w = work_area[2] - work_area[0]
    h = work_area[3] - work_area[1]
    is_portrait = w < h
    if is_portrait:
        # rotate 90 degree if monitor in portrait mode
        rects = map(lambda r: (r[1], r[0], r[3], r[2]), rects)
    for float_rect in rects:
        yield tuple(int(f) for f in plug_rect(float_rect, work_area))


def obs_tiler(
    layout: Layout,
    work_area: Rect,
    total_windows: int,
    obs_width: int = 1920,
    obs_height: int = 1080,
) -> Iterator[Rect]:
    """Useful for OBS screen recording, it would put the 1st and 2nd window to the left
    and bottom, while all the other windows go to the top right corne with specified
    layout as the area to be recorded.

    .. code-block:: text

        +-----------+-----------+-----------+
        |           |           |           |
        |           |           |     4     |
        |           |     3     |           |
        |     1     |           +-----+-----+
        |    obs    |           |  5  |  6  |
        |           |-----------------------|
        |           |   2. script reader    |
        +-----------+-----------------------+

    :param layout: `Layout` for the top right corne (area to be recorded)
    :param work_area: the monitor work area (taskbar excluded)
    :param total_windows: total number of windows
    :param obs_width: width for the top right corne (area to be recorded) in pixels
    :param obs_height: height for the top right corne (area to be recorded) in pixels
    :rtype: Iterator[Rect]
    """
    wl, wt, wr, wb = work_area
    scr_width, scr_height = wr - wl, wb - wt
    # fallback to direct_tiler when work_area is smaller than obs reserved area
    if obs_width >= scr_width or obs_height >= scr_height:
        yield from direct_tiler(layout, work_area, total_windows)
        return
    if total_windows == 0:
        return
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


def mono_layout_tiler(*args, **kwargs) -> Iterator[Rect]:
    """The dwindle layout tiler"""
    return direct_tiler(mono, *args, **kwargs)


def ratio_dwindle_layout_tiler(*args, master_ratio=0.618, **kwargs) -> Iterator[Rect]:
    """The dwindle layout tiler"""
    return direct_tiler(partial(dwindle, master_ratio=master_ratio), *args, **kwargs)


def dwindle_layout_tiler(*args, **kwargs) -> Iterator[Rect]:
    """The dwindle layout tiler"""
    return direct_tiler(dwindle, *args, **kwargs)


def static_bigscreen_8_layout_tiler(*args, **kwargs) -> Iterator[Rect]:
    """The static bigscreen layout tiler for up to 8 windows"""
    return direct_tiler(static_bigscreen_8, *args, **kwargs)


def widescreen_dwindle_layout_tiler(*args, **kwargs) -> Iterator[Rect]:
    """The wide-screen dwindle layout tiler"""
    return direct_tiler(widescreen_dwindle, *args, **kwargs)


def obs_dwindle_layout_tiler(*args, **kwargs) -> Iterator[Rect]:
    """The obs dwindle layout tiler"""
    return obs_tiler(dwindle, *args, **kwargs)


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
