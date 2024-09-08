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
    ms1 = MonitorState(
        index=0,
        name="ms1",
        workspace_names=["ws"],
        rect=Rect(0, 1920, 0, 1080),
        full_rect=Rect(0, 1920, 0, 1080),
        theme=theme,
    )
    ms2 = MonitorState(
        index=1,
        name="ms2",
        workspace_names=["ws"],
        rect=Rect(0, 800, 0, 600),
        full_rect=Rect(0, 1920, 0, 1080),
        theme=theme,
    )
    w1, w2, w3 = Window(1), Window(2), Window(3)
    w1.manageable = True
    w1.attrs[MONITOR_STATE] = ms1
    vd = VirtDeskState(b"111", config, None)
    vd.monitor_state_from_cursor = mocker.Mock(return_value=ms2)
    vd.move_to_monitor = mocker.Mock()
    vd.on_moved_or_resized(w1)
    vd.move_to_monitor.assert_called()
