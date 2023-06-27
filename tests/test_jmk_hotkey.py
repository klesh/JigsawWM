from jigsawwm.jmk.hotkey import *
from jigsawwm.w32.vk import *


def test_hotkey(mocker):
    hotkey = JmkHotkeys(mocker.Mock())
    win_alt_a_cb = mocker.Mock()
    hotkey.register([Vk.LWIN, Vk.LMENU, Vk.A], win_alt_a_cb)
    # trigger when key up
    hotkey(JmkEvent(Vk.LWIN, True))
    hotkey(JmkEvent(Vk.LMENU, True))
    hotkey(JmkEvent(Vk.A, True))
    assert win_alt_a_cb.call_count == 0
    hotkey(JmkEvent(Vk.A, False))
    time.sleep(0.1)
    assert win_alt_a_cb.call_count == 1
    # second trigger
    hotkey(JmkEvent(Vk.A, True))
    assert win_alt_a_cb.call_count == 1
    hotkey(JmkEvent(Vk.A, False))
    time.sleep(0.01)
    assert win_alt_a_cb.call_count == 2
    assert hotkey.next_handler.call_count == 2
    # pass through if modifier key is released first
    hotkey(JmkEvent(Vk.A, True))
    hotkey(JmkEvent(Vk.LMENU, False))
    hotkey(JmkEvent(Vk.A, False))
    hotkey(JmkEvent(Vk.LWIN, False))
    assert win_alt_a_cb.call_count == 2
    assert hotkey.next_handler.call_count == 6
