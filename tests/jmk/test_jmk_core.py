"""Test cases for jigsawwm.jmk.core module."""

import time
from jigsawwm.jmk.core import JmkCore, JmkEvent, JmkKey, JmkTapHold, Vk


def test_jmk_core_map_key(mocker):
    """Test key mapping."""
    next_handler = mocker.Mock()
    jmk_core = JmkCore(
        layers=[{Vk.A: JmkKey(Vk.B)}],
    )
    jmk_core.pipe(next_handler)

    a_down, a_up = JmkEvent(Vk.A, True), JmkEvent(Vk.A, False)
    b_down, b_up = JmkEvent(Vk.B, True), JmkEvent(Vk.B, False)
    jmk_core(a_down)
    assert next_handler.call_count == 1
    assert b_down.same(next_handler.call_args[0][0])
    jmk_core(a_up)
    assert next_handler.call_count == 2
    assert b_up.same(next_handler.call_args[0][0])
    # pass through
    jmk_core(b_down)
    jmk_core(b_up)
    assert next_handler.call_count == 4
    assert b_up.same(next_handler.call_args[0][0])


def test_jmk_core_taphold_hold_triggerred_by_other_key(mocker):
    """Test tap-hold: when other key is tapped, hold is triggered."""
    next_handler = mocker.Mock()
    jmk_core = JmkCore(
        layers=[{Vk.A: JmkTapHold(hold=Vk.LMENU, tap=Vk.A, term=0.3)}],
    )
    jmk_core.pipe(next_handler)
    # hold triggerred by other keys
    jmk_core(JmkEvent(Vk.A, True))
    jmk_core(JmkEvent(Vk.B, True))
    jmk_core(JmkEvent(Vk.B, False))
    assert next_handler.call_count == 3
    assert JmkEvent(Vk.LMENU, True).same(next_handler.call_args_list[-3][0][0])
    assert JmkEvent(Vk.B, True).same(next_handler.call_args_list[-2][0][0])
    assert JmkEvent(Vk.B, False).same(next_handler.call_args_list[-1][0][0])


def test_jmk_core_taphold_tapping(mocker):
    """Test tap-hold: tapping the tap-hold key"""
    jmk_core = JmkCore(
        layers=[{Vk.A: JmkTapHold(hold=Vk.LMENU, tap=Vk.A, term=0.3)}],
    )
    jmk_core.next_handler = mocker.Mock()
    jmk_core(JmkEvent(Vk.A, True))
    jmk_core(JmkEvent(Vk.A, False))
    assert jmk_core.next_handler.call_count == 2
    assert JmkEvent(Vk.A, True).same(jmk_core.next_handler.call_args_list[-2][0][0])
    assert JmkEvent(Vk.A, False).same(jmk_core.next_handler.call_args_list[-1][0][0])
    # pass through
    jmk_core(JmkEvent(Vk.B, True))
    jmk_core(JmkEvent(Vk.B, False))
    assert jmk_core.next_handler.call_count == 4


def test_jmk_core_layers(mocker):
    """Test layer switching."""
    jmk_core = JmkCore(
        layers=[
            {Vk.G: JmkTapHold(hold=1, tap=Vk.G, term=0.3)},  # layer 0
            {Vk.H: JmkKey(Vk.LEFT)},  # layer 1
        ],
    )
    jmk_core.pipe(mocker.Mock())
    # simple toggle
    jmk_core(JmkEvent(Vk.G, True))
    time.sleep(0.4)
    assert jmk_core.next_handler.call_count == 0
    jmk_core(JmkEvent(Vk.H, True))
    assert jmk_core.next_handler.call_count == 1
    assert JmkEvent(Vk.LEFT, True).same(jmk_core.next_handler.call_args[0][0])
    # toggle while holding
    jmk_core(JmkEvent(Vk.G, True))
    time.sleep(0.4)
    jmk_core(JmkEvent(Vk.H, True))
    jmk_core(JmkEvent(Vk.G, False))
    jmk_core(JmkEvent(Vk.H, False))
    assert jmk_core.next_handler.call_count == 3
    assert JmkEvent(Vk.LEFT, True).same(jmk_core.next_handler.call_args_list[-2][0][0])
    assert JmkEvent(Vk.LEFT, False).same(jmk_core.next_handler.call_args_list[-1][0][0])


def test_tap_tap_hold_passthrough(mocker):
    """Test tap-tap-hold passthrough."""
    jmk_core = JmkCore(
        layers=[
            {
                Vk.A: JmkTapHold(
                    hold=Vk.LMENU,
                    tap=Vk.A,
                    quick_tap_term=0.2,
                ),
            }
        ],
    )
    jmk_core.pipe(mocker.Mock())
    jmk_core(JmkEvent(Vk.A, True))
    jmk_core(JmkEvent(Vk.A, False))
    assert JmkEvent(Vk.A, True).same(jmk_core.next_handler.call_args_list[0][0][0])
    assert JmkEvent(Vk.A, False).same(jmk_core.next_handler.call_args_list[1][0][0])
    jmk_core(JmkEvent(Vk.A, True))
    assert JmkEvent(Vk.A, True).same(jmk_core.next_handler.call_args_list[2][0][0])
    jmk_core(JmkEvent(Vk.A, True))
    assert JmkEvent(Vk.A, True).same(jmk_core.next_handler.call_args_list[3][0][0])
    jmk_core(JmkEvent(Vk.A, False))
    assert JmkEvent(Vk.A, False).same(jmk_core.next_handler.call_args_list[4][0][0])
