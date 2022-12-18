from typing import Iterator, Tuple
from functools import partial

FloatRect = Tuple[float, float, float, float]


def dwindle(n: int) -> Iterator[FloatRect]:
    """Returns a generator of dwindle layout
    +-----------+-----------+
    |           |           |
    |           |     2     |
    |           |           |
    |     1     +-----+-----+
    |           |     |  4  |
    |           |  3  +--+--+
    |           |     | 5|-.|
    +-----------+-----+-----+

    :param n: total number of windows
    :return: dwindle generator
    :rtype: Iterator[FloatRect]
    """
    t, l, b, r = 0.0, 0.0, 1.0, 1.0
    last_index = n - 1
    for i in range(n):
        # last window would occupy the whole area
        if i == last_index:
            yield t, l, b, r
        # or it should leave out half space for the other windows
        elif i % 2 == 0:
            nl = r - (r - l) / 2
            yield t, l, b, nl
            l = nl
        else:
            nb = b - (b - t) / 2
            yield t, l, nb, r
            t = nb


def widescreen_dwindle(n: int, master_ratio: float = 0.4) -> Iterator[FloatRect]:
    """Returns a generator of dwindle layout, works greate for wide-screen monitor
    +-----------+-----------+-----------+
    |           |           |           |
    |           |           |     3     |
    |           |           |           |
    |     1     |     2     +-----+-----+
    |           |           |     |  5  |
    |           |           |  4  +--+--+
    |           |           |     | 6|-.|
    +-----------+-----------+-----+-----+

    :param n: total number of windows
    :return: master_dwindle generator
    :rtype: Iterator[FloatRect]
    """
    #    wide_dwindle
    if n == 1:
        yield 0.0, 0.0, 1.0, 1.0
        return
    # master window on the left
    yield 0.0, 0.0, 1, master_ratio
    l = master_ratio
    r = 1 - l
    # other windows on the right with dwindle layout, just map the coordinate and we are good
    yield from map(
        partial(plug_rect, target=(0.0, 1.0 - master_ratio, 1.0, 1.0)), dwindle(n - 1)
    )


def plug_rect(source: FloatRect, target: FloatRect) -> FloatRect:
    """Plug the source rect inside the target rect and compute the new dimensions for the target rect"""
    st, sl, sb, sr = source
    tt, tl, tb, tr = target
    tw = tr - tl
    th = tb - tt
    return (
        tt + st * th,  # top = target top + scaled source top
        tl + sl * tw,  # left = target left + scaled source left
        tt + sb * th,
        tl + sr * tw,
    )


if __name__ == "__main__":
    print("dwindle")
    for n in range(1, 5):
        print(list(dwindle(n)))
    """ expected: top/left/bottom/right
    [(0.0, 0.0, 1.0, 1.0)]
    [(0.0, 0.0, 1.0, 0.5), (0.0, 0.5, 1.0, 1.0)]
    [(0.0, 0.0, 1.0, 0.5), (0.0, 0.5, 0.5, 1.0), (0.5, 0.5, 1.0, 1.0)]
    [(0.0, 0.0, 1.0, 0.5), (0.0, 0.5, 0.5, 1.0), (0.5, 0.5, 1.0, 0.75), (0.5, 0.75, 1.0, 1.0)]
    """
    print()
    print("widescreen_dwindle")
    for n in range(1, 5):
        print(list(widescreen_dwindle(n)))
    """ expected: top/left/bottom/right
    [(0.0, 0.0, 1.0, 1.0)]
    [(0.0, 0.0, 1, 0.4), (0.0, 0.6, 1.0, 1.0)]
    [(0.0, 0.0, 1, 0.4), (0.0, 0.6, 1.0, 0.8), (0.0, 0.8, 1.0, 1.0)]
    [(0.0, 0.0, 1, 0.4), (0.0, 0.6, 1.0, 0.8), (0.0, 0.8, 0.5, 1.0), (0.5, 0.8, 1.0, 1.0)] 
    """
