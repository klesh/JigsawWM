"""

The ``tiler`` module is responsible for converting Layout to Physical Coordinates for arbitrary number of windows.

``Rect`` is a tuple with 4 elements (left/top/right/bottom) to describe a rectangle in pixels (integer)

``Tiler`` is a generator which generates Rects with specified Layout for given monitor work area and total number of windows

``LayoutTiler`` is similar to `Tiler` except the Layout was predefined

"""
from typing import Callable, Iterator, Tuple, List
from dataclasses import dataclass

from .layouts import Layout, dwindle, mono, static_bigscreen_8, plug_rect, widescreen_dwindle
from jigsawwm.w32.window import Window, get_foreground_window

# Rect holds physical coordinate for rectangle (left/top/right/bottom)
Rect = Tuple[int, int, int, int]

# Tiler generates physical Rects for specified total number of windows based on given Layout
Tiler = Callable[[Layout, Rect, int], Iterator[Rect]]

# LayoutTiler generates physical Rects for specified total number of windows
LayoutTiler = Callable[[Rect, List[Window]], Iterator[Rect]]


def direct_tiler(layout: Layout, work_area: Rect, windows: List[Window]) -> Iterator[Rect]:
    """The default Tiler which maps specified `Layout` to physical work area directly

    :param layout: a Layout generator
    :param work_area: the monitor work area (taskbar excluded)
    :param total_windows: total number of windows
    :rtype: Iterator[Rect]
    """
    rects = layout(len(windows))
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
    windows: List[Window],
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
    total_windows = len(windows)
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


@dataclass
class PaperWindowPref:
    width_ratio: float = 0.8
    height_ratio: float = 1.0
    align: str = "center"

_paper_window_prefs = {}

def paper_get_window_pref(window: Window) -> PaperWindowPref:
    """Get the preference for a window"""
    pref = _paper_window_prefs.get(window.handle, None)
    if pref is None:
        pref = PaperWindowPref()
        _paper_window_prefs[window.handle] = pref
        # save to disk
    return pref

def paper_layout_tiler(
    work_area: Rect,
    windows: List[Window],
) -> Iterator[Rect]:
    """The paper layout tiler"""
    float_rects = []
    left, right = 0.0, 0.0
    hwnd = get_foreground_window()
    for i, w in enumerate(windows):
        pref = paper_get_window_pref(w)
        right = left + pref.width_ratio
        float_rects.append((left, 0, right, 1))
        left = right
        if w.handle == hwnd: # if the window is the foreground window then it is the anchor
            anchor = i
    if anchor: # adjust all windows according to the anchor
        print("anchor", anchor)
        for i, r in enumerate(float_rects):
            afr = float_rects[anchor]
            float_rects[i] = (
                r[0] - afr[0 if i <= anchor else 2],
                r[1],
                r[2] - afr[0 if i <= anchor else 2] ,
                r[3],
            )
    print("float_rects", float_rects)


if __name__ == "__main__":
    from jigsawwm.w32.window import get_manageable_windows
    print("paper tiler")
    
    windows = list(get_manageable_windows())
    windows[0], windows[1] = windows[1], windows[0]
    paper_layout_tiler(
        work_area=(10, 10, 3450, 1450),
        windows=windows,
    )
    # print("direct dwindle")
    # for n in range(1, 5):
    #     print(
    #         list(
    #             direct_tiler(
    #                 layout=dwindle,
    #                 work_area=(10, 10, 3450, 1450),
    #                 total_windows=n,
    #             )
    #         )
    #     )
    # print("obs dwindle")
    # for n in range(1, 5):
    #     print(
    #         list(
    #             obs_tiler(
    #                 layout=dwindle,
    #                 work_area=(10, 10, 3450, 1450),
    #                 total_windows=n,
    #             )
    #         )
    #     )
