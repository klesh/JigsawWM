"""Test cases for jigsawwm.jmk.core module."""
import time
from jigsawwm.jmk.core import JmkCore, JmkEvent, JmkKey, JmkTapHold, Vk


def test_jmk_core_map_key(mocker):
    """Test key mapping."""
    jmk_core = JmkCore(
        next_handler=mocker.Mock(),
        layers=[
            {
                Vk.A: JmkKey(Vk.B),
            }
        ],
    )
    jmk_core(JmkEvent(Vk.A, True))
    assert jmk_core.next_handler.call_count == 1
    assert jmk_core.next_handler.call_args[0][0] == JmkEvent(Vk.B, True)
    jmk_core(JmkEvent(Vk.A, False))
    assert jmk_core.next_handler.call_count == 2
    assert jmk_core.next_handler.call_args[0][0] == JmkEvent(Vk.B, False)
    # pass through
    jmk_core(JmkEvent(Vk.B, True))
    jmk_core(JmkEvent(Vk.B, False))
    assert jmk_core.next_handler.call_count == 4


def test_jmk_core_taphold_hold_triggerred_by_other_key(mocker):
    """Test tap-hold: when other key is tapped, hold is triggered."""
    jmk_core = JmkCore(
        next_handler=mocker.Mock(),
        layers=[{Vk.A: JmkTapHold(hold=Vk.LMENU, tap=Vk.A, term=0.3)}],
    )
    # hold triggerred by other keys
    jmk_core(JmkEvent(Vk.A, True))
    jmk_core(JmkEvent(Vk.B, True))
    jmk_core(JmkEvent(Vk.B, False))
    assert jmk_core.next_handler.call_count == 3
    assert jmk_core.next_handler.call_args_list[-3][0][0] == JmkEvent(Vk.LMENU, True)
    assert jmk_core.next_handler.call_args_list[-2][0][0] == JmkEvent(Vk.B, True)
    assert jmk_core.next_handler.call_args_list[-1][0][0] == JmkEvent(Vk.B, False)

def test_jmk_core_taphold_tapping(mocker):
    """Test tap-hold: tapping the tap-hold key"""
    jmk_core = JmkCore(
        next_handler=mocker.Mock(),
        layers=[{Vk.A: JmkTapHold(hold=Vk.LMENU, tap=Vk.A, term=0.3)}],
    )
    jmk_core(JmkEvent(Vk.A, True))
    jmk_core(JmkEvent(Vk.A, False))
    assert jmk_core.next_handler.call_count == 2
    assert jmk_core.next_handler.call_args_list[-2][0][0] == JmkEvent(Vk.A, True)
    assert jmk_core.next_handler.call_args_list[-1][0][0] == JmkEvent(Vk.A, False)
    # pass through
    jmk_core(JmkEvent(Vk.B, True))
    jmk_core(JmkEvent(Vk.B, False))
    assert jmk_core.next_handler.call_count == 4


def test_jmk_core_layers(mocker):
    """Test layer switching."""
    jmk_core = JmkCore(
        next_handler=mocker.Mock(),
        layers=[
            {Vk.G: JmkTapHold(hold=1, tap=Vk.G, term=0.3)},  # layer 0
            {Vk.H: JmkKey(Vk.LEFT)},  # layer 1
        ],
    )
    # simple toggle
    jmk_core(JmkEvent(Vk.G, True))
    time.sleep(0.4)
    assert jmk_core.next_handler.call_count == 0
    jmk_core(JmkEvent(Vk.H, True))
    assert jmk_core.next_handler.call_count == 1
    assert jmk_core.next_handler.call_args[0][0] == JmkEvent(Vk.LEFT, True)
    # toggle while holding
    jmk_core(JmkEvent(Vk.G, True))
    time.sleep(0.4)
    jmk_core(JmkEvent(Vk.H, True))
    jmk_core(JmkEvent(Vk.G, False))
    jmk_core(JmkEvent(Vk.H, False))
    assert jmk_core.next_handler.call_count == 3
    assert jmk_core.next_handler.call_args_list[-2][0][0] == JmkEvent(Vk.LEFT, True)
    assert jmk_core.next_handler.call_args_list[-1][0][0] == JmkEvent(Vk.LEFT, False)


def test_tap_tap_hold_passthrough(mocker):
    """Test tap-tap-hold passthrough."""
    jmk_core = JmkCore(
        next_handler=mocker.Mock(),
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
    jmk_core(JmkEvent(Vk.A, True))
    jmk_core(JmkEvent(Vk.A, False))
    assert jmk_core.next_handler.call_args_list[0][0][0] == JmkEvent(Vk.A, True)
    assert jmk_core.next_handler.call_args_list[1][0][0] == JmkEvent(Vk.A, False)
    jmk_core(JmkEvent(Vk.A, True))
    assert jmk_core.next_handler.call_args_list[2][0][0] == JmkEvent(Vk.A, True)
    jmk_core(JmkEvent(Vk.A, True))
    assert jmk_core.next_handler.call_args_list[3][0][0] == JmkEvent(Vk.A, True)
    jmk_core(JmkEvent(Vk.A, False))
    assert jmk_core.next_handler.call_args_list[4][0][0] == JmkEvent(Vk.A, False)
