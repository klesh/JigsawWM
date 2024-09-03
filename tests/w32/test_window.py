"""Test w32.window."""

from jigsawwm.w32.window import Window, topo_sort_windows, Rect


def test_topo_sort_windows(mocker):
    """Test the topology comparison of windows."""
    w1, w2, w3 = Window(1), Window(2), Window(3)
    # simulate a 3 window topology, 1 master on the top, 2 slaves on the bottom
    # 1st row, only column in a perfect condition
    w1.get_rect = mocker.Mock(return_value=Rect(0, 0, 100, 100))
    # 2nd row, 1st column, with a little bit(5x) off toward the bottom
    w2.get_rect = mocker.Mock(return_value=Rect(0, 105, 50, 200))
    # 2dn row, 2nd column
    w3.get_rect = mocker.Mock(return_value=Rect(100, 100, 100, 100))
    assert topo_sort_windows([w3, w1, w2]) == [w1, w2, w3]
    assert topo_sort_windows([w1, w3, w2]) == [w1, w2, w3]
    assert topo_sort_windows([w2, w3, w1]) == [w1, w2, w3]
