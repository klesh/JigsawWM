"""Test jigsawwm.jmk.hotkey module."""

from jigsawwm.jmk.combo import JmkCombos, JmkEvent, Vk


def test_combos(mocker):
    """Test hotkey registration and trigger."""
    pressed_cb1 = mocker.Mock()
    release_cb1 = mocker.Mock()
    pressed_cb2 = mocker.Mock()
    release_cb2 = mocker.Mock()
    next_handler = mocker.Mock()
    combs = JmkCombos(
        combos=[
            ("LBUTTON+RBUTTON", pressed_cb1, release_cb1),
            ("LBUTTON+MBUTTON", pressed_cb2, release_cb2),
        ]
    )
    combs.pipe(next_handler)
    # normal case
    combs(JmkEvent(Vk.LBUTTON, True))
    combs(JmkEvent(Vk.RBUTTON, True))
    assert pressed_cb1.call_count == 1
    combs(JmkEvent(Vk.RBUTTON, False))
    assert release_cb1.call_count == 0
    combs(JmkEvent(Vk.LBUTTON, False))
    assert release_cb1.call_count == 1
