from typing import Iterator, Tuple, Callable, Union
from functools import partial

# FloatRect holds relative coordinate for rectangle (left/top/right/bottom)
FloatRect = Tuple[float, float, float, float]

# Layout accepts an integer (total number of windows) and return a FloatRect generator
Layout = Callable[[int], Iterator[FloatRect]]


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
    l, t, r, b = 0.0, 0.0, 1.0, 1.0
    last_index = n - 1
    for i in range(n):
        # last window would occupy the whole area
        if i == last_index:
            yield l, t, r, b
        # or it should leave out half space for the other windows
        elif i % 2 == 0:
            nl = r - (r - l) / 2
            yield l, t, nl, b
            l = nl
        else:
            nb = b - (b - t) / 2
            yield l, t, r, nb
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
    # other windows on the right with dwindle layout, just map the coordinate and we are good
    yield from map(
        partial(plug_rect, target=(1.0 - master_ratio, 0.0, 1.0, 1.0)), dwindle(n - 1)
    )


Number = Union[int, float]
NumberRect = Tuple[Number, Number, Number, Number]


def plug_rect(source: NumberRect, target: NumberRect) -> NumberRect:
    """Plug the source rect inside the target rect and compute the new dimensions for the target rect"""
    sl, st, sr, sb = source
    tl, tt, tr, tb = target
    tw = tr - tl
    th = tb - tt
    return (
        tl + sl * tw,  # left = target left + scaled source left
        tt + st * th,  # top = target top + scaled source top
        tl + sr * tw,  # right
        tt + sb * th,  # bottom
    )


if __name__ == "__main__":
    print("dwindle")
    for n in range(1, 5):
        print(list(dwindle(n)))
    print()
    print("widescreen_dwindle")
    for n in range(1, 5):
        print(list(widescreen_dwindle(n)))
