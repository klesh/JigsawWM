import time

from jigsawwm.hotkey import Holdkey, Hotkey, Hotkeys
from jigsawwm.w32.vk import Vk

cb = lambda: 1
cb2 = lambda: 2
hotkey_za = Hotkey(keys=[Vk.Z, Vk.A], callback=cb, swallow=True)
hotkey_zb = Hotkey(keys=[Vk.Z, Vk.B], callback=cb, swallow=False)
hotkey_win_a = Hotkey(keys=[Vk.LWIN, Vk.A], callback=cb, swallow=True)
hotkey_ctrl_b = Hotkey(keys=[Vk.LCONTROL, Vk.B], callback=cb, swallow=False)
hold_z = Holdkey(key=Vk.Z, down=cb, up=cb2, swallow=True)
hold_x = Holdkey(key=Vk.X, down=cb, up=cb2, swallow=False)


def test_combination_triggered(mocker):
    hotkeys = Hotkeys()
    hotkeys.hotkey(hotkey_za)
    # case 1: combination triggered
    za_callback = mocker.spy(hotkey_za, "callback")
    hotkeys.event(key=Vk.Z, pressed=True)
    hotkeys.event(key=Vk.A, pressed=True)
    hotkeys.event(key=Vk.A, pressed=False)
    hotkeys.event(key=Vk.Z, pressed=False)
    time.sleep(0.01)
    za_callback.assert_called_once()
    # case 2: combination not triggered
    hotkeys.event(key=Vk.Z, pressed=True)
    hotkeys.event(key=Vk.A, pressed=True)
    hotkeys.event(key=Vk.Z, pressed=False)
    hotkeys.event(key=Vk.A, pressed=False)
    time.sleep(0.01)
    za_callback.assert_called_once()


def test_combinations_passthrough():
    hotkeys = Hotkeys()
    hotkeys.hotkey(hotkey_za)
    hotkeys.hotkey(hotkey_zb)
    # case 1: last key in combinations should be passed through
    swallow, resend = hotkeys.event(key=Vk.A, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.A, pressed=False)
    assert not swallow
    assert not resend
    # case 2: the event should be swallowed when ordinary keys are used as modifiers
    #         if no combination matches, the event should be swallow first, and then resent
    swallow, resend = hotkeys.event(key=Vk.Z, pressed=True)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.Z, pressed=False)
    assert swallow
    assert resend == [(Vk.Z, True), (Vk.Z, False)]
    # case 3: repeat case 2 with different combination
    swallow, resend = hotkeys.event(key=Vk.Z, pressed=True)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.C, pressed=True)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.C, pressed=False)
    assert resend == [(Vk.Z, True), (Vk.C, True), (Vk.C, False)]
    hotkeys.event(key=Vk.Z, pressed=False)
    # case 4: all modifiers should be passed through
    for key in [
        Vk.LSHIFT,
        Vk.LCONTROL,
        Vk.LMENU,
        Vk.LWIN,
        Vk.RSHIFT,
        Vk.RCONTROL,
        Vk.RMENU,
        Vk.RWIN,
    ]:
        swallow, resend = hotkeys.event(key=key, pressed=True)
        assert not swallow
        assert not resend
        swallow, resend = hotkeys.event(key=key, pressed=False)
        assert not swallow
        assert not resend
    # case 5: combination with modifiers
    hotkeys.hotkey(hotkey_win_a)
    swallow, resend = hotkeys.event(key=Vk.LWIN, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.A, pressed=True)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.A, pressed=False)
    assert swallow
    assert resend == [(Vk.NONAME, False)]
    swallow, resend = hotkeys.event(key=Vk.LWIN, pressed=False)
    assert not swallow
    assert not resend
    # case 6: combination with modifiers without swallowing
    hotkeys.hotkey(hotkey_ctrl_b)
    swallow, resend = hotkeys.event(key=Vk.LCONTROL, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.B, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.B, pressed=False)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.LCONTROL, pressed=False)
    assert not swallow
    assert not resend


def test_holdkey_triggered(mocker):
    hotkeys = Hotkeys()
    hotkeys.holdkey(hold_z)
    hold_z_down = mocker.spy(hold_z, "down")
    hold_z_up = mocker.spy(hold_z, "up")
    hotkeys.holdkey(hold_x)
    hold_x_down = mocker.spy(hold_x, "down")
    hold_x_up = mocker.spy(hold_x, "up")
    # down event gets fired after term_s
    hotkeys.event(key=Vk.Z, pressed=True)
    assert hold_z_down.call_count == 0
    time.sleep(hold_z.term_s + 0.05)
    hold_z_down.assert_called_once()
    # test for non-swallowing holdkey
    swallow, resend = hotkeys.event(key=Vk.X, pressed=True)
    assert not swallow
    assert not resend
    time.sleep(hold_x.term_s + 0.05)
    assert hold_x_down.call_count == 1
    # up event gets fired once down was fired and key is released no matter what
    swallow, resend = hotkeys.event(key=Vk.Z, pressed=False)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.X, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.X, pressed=False)
    assert not swallow
    assert not resend
    time.sleep(0.05)
    hold_z_up.assert_called_once()
    hold_x_up.assert_called_once()


def test_holdkey_passthrough(mocker):
    hotkeys = Hotkeys()
    hotkeys.holdkey(Holdkey(Vk.Q, down=cb, up=cb2, swallow=True))
    hold_z_down = mocker.spy(hold_z, "down")
    hold_z_up = mocker.spy(hold_z, "up")
    # case 1: tapping the holding key should be passed through
    swallow, resend = hotkeys.event(key=Vk.Q, pressed=True)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.Q, pressed=False)
    assert swallow
    assert resend == [(Vk.Q, True), (Vk.Q, False)]


def test_combination_and_holdingkey_mutual_exclusive():
    pass
