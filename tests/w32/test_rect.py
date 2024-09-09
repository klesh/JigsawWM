"""Test w32.window_struct.Rect"""

from jigsawwm.w32.window_structs import Rect


def test_rect_contains_rect():
    """Test if a rect contains another rect."""
    assert Rect(left=0, top=5928, right=3840, bottom=8016).contains_rect_center(
        Rect(left=1326, top=6756, right=2454, bottom=7486)
    )
    assert Rect(0, 0, 100, 100).contains_rect_center(Rect(0, 0, 50, 50))
