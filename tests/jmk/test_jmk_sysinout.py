"""Test jigsawwm.jmk.sysinout module."""

import time
from jigsawwm.jmk.sysinout import (
    SystemInput,
    SystemOutput,
    Window,
    WindowCache,
    hook,
    state,
    Vk,
    JmkEvent,
)
from jigsawwm.jmk.core import JmkCore, JmkTapHold


def test_jmk_sysin_disable_for_admin_windows(mocker):
    """Test system input handler disabled when ."""
    next_handler = mocker.Mock()
    window_cache = WindowCache()
    sysin = SystemInput(window_cache=window_cache)
    sysin.pipe(next_handler)
    # admin
    elevated_window = Window(123)
    elevated_window.is_elevated = True
    window_cache.get_window = mocker.Mock(return_value=elevated_window)
    assert sysin.disabled is False
    # admin window is focused
    sysin.on_focus_changed(123)
    assert window_cache.get_window.call_args[0][0] == 123
    assert sysin.disabled is True
    # key event should be igored for administrative windows
    swallow = sysin.input_event(
        0, hook.KBDLLHOOKMSGID.WM_KEYDOWN, hook.KBDLLHOOKDATA(vkCode=Vk.A)
    )
    assert swallow is False
    # user window is focused
    user_window = Window(456)
    user_window.is_elevated = False
    user_window.exe_name = "whatever.exe"
    window_cache.get_window = mocker.Mock(return_value=user_window)
    sysin.on_focus_changed(456)
    assert sysin.disabled is False
    # key event should be swallowed for user mode window
    sysin.enqueue = mocker.Mock()
    swallow = sysin.input_event(
        0, hook.KBDLLHOOKMSGID.WM_KEYDOWN, hook.KBDLLHOOKDATA(vkCode=Vk.A)
    )
    assert swallow is True
    assert sysin.enqueue.call_count == 1


def test_jmk_sysout_state(mocker):
    """Test jigsawwm.jmk.sysinout.state."""
    sysout = SystemOutput()
    sysout.input_sender = mocker.Mock()
    sysout(JmkEvent(Vk.A, True))
    assert sysout.input_sender.call_count == 1
    assert state[Vk.A] == 1
    sysout(JmkEvent(Vk.A, False))
    assert state[Vk.A] == 0


class TestDelayCall:
    sysin: SystemInput

    def setup_method(self):
        """setup"""
        self.sysin = SystemInput()
        self.sysin.start_worker()

    def teardown_method(self):
        """teardown"""
        self.sysin.stop_worker()

    def test_taphold_timeouted(self, mocker):
        """Test tap-hold timeouted"""
        core = JmkCore(
            layers=[
                {
                    Vk.A: JmkTapHold(hold=Vk.LMENU, tap=Vk.A, term=0.1),
                    Vk.B: JmkTapHold(hold=Vk.LCONTROL, tap=Vk.B, term=0.1),
                },
            ],
        )
        output = mocker.Mock()
        self.sysin.pipe(core).pipe(output)
        # hold A down
        self.sysin.input_event(
            0, hook.KBDLLHOOKMSGID.WM_KEYDOWN, hook.KBDLLHOOKDATA(vkCode=Vk.A)
        )
        time.sleep(0.2)
        assert JmkEvent(Vk.LMENU, True).same(output.call_args[0][0])
        # hold B down
        self.sysin.input_event(
            0, hook.KBDLLHOOKMSGID.WM_KEYDOWN, hook.KBDLLHOOKDATA(vkCode=Vk.B)
        )
        time.sleep(0.2)
        assert JmkEvent(Vk.LCONTROL, True).same(output.call_args[0][0])
        # release B
        self.sysin.input_event(
            0, hook.KBDLLHOOKMSGID.WM_KEYUP, hook.KBDLLHOOKDATA(vkCode=Vk.B)
        )
        time.sleep(0.01)
        assert JmkEvent(Vk.LCONTROL, False).same(output.call_args[0][0])
        # release A
        self.sysin.input_event(
            0, hook.KBDLLHOOKMSGID.WM_KEYUP, hook.KBDLLHOOKDATA(vkCode=Vk.A)
        )
        time.sleep(0.01)
        assert JmkEvent(Vk.LMENU, False).same(output.call_args[0][0])
        # tap A
        call_count = output.call_count
        self.sysin.input_event(
            0, hook.KBDLLHOOKMSGID.WM_KEYDOWN, hook.KBDLLHOOKDATA(vkCode=Vk.A)
        )
        self.sysin.input_event(
            0, hook.KBDLLHOOKMSGID.WM_KEYUP, hook.KBDLLHOOKDATA(vkCode=Vk.A)
        )
        time.sleep(0.2)
        assert output.call_count == call_count + 2
        assert JmkEvent(Vk.A, False).same(output.call_args_list[-1][0][0])
        assert JmkEvent(Vk.A, True).same(output.call_args_list[-2][0][0])
