"""

The ``layout`` module operates in Relative Coordinate, to that end, it defines 2 basic types:

``FloatRect`` is a tuple with 4 elements (left/top/right/bottom) to describe a rectangle in ratio form (0.0~1.0)

``Layout`` is a generator which generates FloatRects for given total number of windows

"""

from functools import partial
from typing import Callable, Iterator, Tuple, Union

# FloatRect holds relative coordinate for rectangle (left/top/right/bottom)
FloatRect = Tuple[float, float, float, float]

# Layout accepts an integer (total number of windows) and return a FloatRect generator
Layout = Callable[[int], Iterator[FloatRect]]


def dwindle(n: int) -> Iterator[FloatRect]:
    """The dwindle Layout

    .. code-block:: text

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
    """A wide-screen friendly dwindle Layout

    .. code-block:: text

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
    :rtype: Iterator[FloatRect]
    """
    if n == 0:
        return
    #    wide_dwindle
    if n == 1:
        yield 0.0, 0.0, 1.0, 1.0
        return
    # master window on the left
    yield 0.0, 0.0, master_ratio, 1
    # other windows on the right with dwindle layout, just map the coordinate and we are good
    yield from map(
        partial(plug_rect, target=(master_ratio, 0.0, 1.0, 1.0)), dwindle(n - 1)
    )


Number = Union[int, float]
NumberRect = Tuple[Number, Number, Number, Number]


def plug_rect(source: FloatRect, target: NumberRect) -> NumberRect:
    """Plug the source rect into the target rect and compute the new dimensions,
    you may plug a Relative Rect into a Physical Rect, but not the other way around.

    :param source: the FloatRect to be moved
    :param target: the container, either a FloatRect or Rect(physical pixels)
    :returns: Rect or FloatRect depends on the type of the target
    :rtype: NumberRect
    """

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
