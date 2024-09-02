"""Test workspace state."""

from jigsawwm.wm.workspace_state import WorkspaceState, Rect, Theme, Window


def test_workspace_state_update_list_from_set(mocker):
    """Test workspace state update list from set."""
    # pylint: disable=protected-access
    theme = Theme(
        name="test_theme", layout_tiler=mocker.Mock(), new_window_as_master=False
    )
    ws = WorkspaceState(
        0, 0, "test_ws", Rect(left=0, top=0, right=1000, bottom=1000), theme
    )
    old_list = [Window(1), Window(2)]
    new_set = set(old_list + [Window(3)])
    assert ws._update_list_from_set(old_list, new_set) == [
        Window(1),
        Window(2),
        Window(3),
    ]
    theme.new_window_as_master = True
    assert ws._update_list_from_set(old_list, new_set) == [
        Window(3),
        Window(1),
        Window(2),
    ]


def test_workspace_state_dynamic_tiling(mocker):
    """Test workspace state dynamic tiling."""
    theme = Theme(
        name="test_theme",
        layout_tiler=mocker.Mock(
            return_value=[
                (0, 0, 500, 1000),
                (500, 0, 1000, 500),
                (500, 500, 1000, 1000),
            ]
        ),
        max_tiling_windows=3,
        gap=2,
        stacking_margin_x=0.1,
        stacking_margin_y=0.1,
        stacking_max_step=40,
        stacking_window_width=0.6,
        stacking_window_height=0.6,
    )
    ws = WorkspaceState(
        0, 0, "test_ws", Rect(left=0, top=0, right=1000, bottom=1000), theme
    )
    ws.tiling_windows = [
        mocker.Mock(set_restrict_rect=mocker.Mock()),
        mocker.Mock(set_restrict_rect=mocker.Mock()),
        mocker.Mock(set_restrict_rect=mocker.Mock()),
        mocker.Mock(set_restrict_rect=mocker.Mock()),
        mocker.Mock(set_restrict_rect=mocker.Mock()),
    ]

    ws.arrange()
    assert ws.tiling_windows[0].set_restrict_rect.call_args[0][0] == Rect(
        4, 4, 498, 996
    )
    assert ws.tiling_windows[1].set_restrict_rect.call_args[0][0] == Rect(
        502, 4, 996, 498
    )
    assert ws.tiling_windows[2].set_restrict_rect.call_args[0][0] == Rect(
        502, 502, 996, 996
    )
    # stacking window size: 600x600; max bound: 900x900; final bound: 640x640; step: 40, num_rest: 2
    # first Rect(180, 180, 180+600, 180+600)
    assert ws.tiling_windows[3].set_restrict_rect.call_args[0][0] == Rect(
        180, 180, 780, 780
    )
    assert ws.tiling_windows[4].set_restrict_rect.call_args[0][0] == Rect(
        220, 220, 820, 820
    )
