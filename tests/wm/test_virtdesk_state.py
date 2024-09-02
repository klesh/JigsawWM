"""Test vritdesk state."""

from jigsawwm.wm.virtdesk_state import (
    VirtDeskState,
    Window,
    MonitorState,
    MONITOR_STATE,
)
from jigsawwm.w32.window import Rect
from jigsawwm.wm.theme import Theme


def test_try_swapping_windows(mocker):
    """Test try swapping windows."""
    config = mocker.Mock()
    theme = Theme(
        name="test_theme",
        layout_tiler=mocker.Mock(return_value=[]),
        new_window_as_master=False,
    )
    ms1 = MonitorState(0, "ms1", ["ws"], Rect(0, 1920, 0, 1080), theme)
    ms2 = MonitorState(1, "ms2", ["ws"], Rect(0, 800, 0, 600), theme)
    w1, w2, w3 = Window(1), Window(2), Window(3)
    w1.manageable = True
    w1.attrs[MONITOR_STATE] = ms1
    vd = VirtDeskState(b"111", config)
    vd.monitor_state_from_cursor = mocker.Mock(return_value=ms2)
    ms1.remove_windows = mocker.Mock()
    ms2.add_windows = mocker.Mock()
    assert vd.try_swapping_window(w1)
    assert ms1.remove_windows.call_count == 1
    assert ms2.add_windows.call_count == 1
