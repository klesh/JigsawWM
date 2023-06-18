import time

from jigsawwm.hotkey import Combination, Holding, Hotkeys
from jigsawwm.w32.vk import Vk

cb = lambda: 1
cb2 = lambda: 2
comb_za = Combination(keys=[Vk.Z, Vk.A], callback=cb, swallow=True)
comb_zb = Combination(keys=[Vk.Z, Vk.B], callback=cb, swallow=False)
comb_win_a = Combination(keys=[Vk.LWIN, Vk.A], callback=cb, swallow=True)
comb_win_b = Combination(keys=[Vk.LWIN, Vk.B], callback=cb, swallow=False)
hold_z = Holding(key=Vk.Z, down=cb, up=cb2, swallow=True)


def test_combination_triggered(mocker):
    hotkeys = Hotkeys()
    hotkeys.combination(comb_za)
    # case 1: combination triggered
    za_callback = mocker.spy(comb_za, "callback")
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
    hotkeys.combination(comb_za)
    hotkeys.combination(comb_zb)
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
    hotkeys.combination(comb_win_a)
    swallow, resend = hotkeys.event(key=Vk.LWIN, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.A, pressed=True)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.A, pressed=False)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.LWIN, pressed=False)
    assert not swallow
    assert not resend
    # case 6: combination with modifiers without swallowing
    hotkeys.combination(comb_win_b)
    swallow, resend = hotkeys.event(key=Vk.LWIN, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.B, pressed=True)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.B, pressed=False)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.LWIN, pressed=False)
    assert not swallow
    assert not resend


def test_holdkey_triggered(mocker):
    hotkeys = Hotkeys()
    hotkeys.holding(hold_z)
    hold_z_down = mocker.spy(hold_z, "down")
    hold_z_up = mocker.spy(hold_z, "up")
    hotkeys.event(key=Vk.Z, pressed=True)
    assert hold_z_down.call_count == 0
    time.sleep(hold_z.term_s + 0.05)
    hold_z_down.assert_called_once()
    swallow, resend = hotkeys.event(key=Vk.Z, pressed=False)
    assert swallow
    assert not resend
    time.sleep(0.05)
    hold_z_up.assert_called_once()


def test_holdkey_passthrough(mocker):
    hotkeys = Hotkeys()
    hotkeys.holding(Holding(Vk.Q, down=cb, up=cb2, swallow=True))
    hold_z_down = mocker.spy(hold_z, "down")
    hold_z_up = mocker.spy(hold_z, "up")
    # case 1: tapping the holding key should be passed through
    swallow, resend = hotkeys.event(key=Vk.Q, pressed=True)
    assert swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.Q, pressed=False)
    assert swallow
    assert resend == [(Vk.Q, True), (Vk.Q, False)]
    # case 2: tap other keys when holding should be passed through
    hotkeys.event(key=Vk.Q, pressed=True)
    swallow, resend = hotkeys.event(key=Vk.A, pressed=True)
    assert swallow
    assert resend == [(Vk.Q, True), (Vk.A, True)]
    swallow, resend = hotkeys.event(key=Vk.Q, pressed=False)
    assert not swallow
    assert not resend
    swallow, resend = hotkeys.event(key=Vk.A, pressed=False)
    assert not swallow
    assert not resend
    time.sleep(hold_z.term_s + 0.05)
    assert not hold_z_down.call_count
    assert not hold_z_up.call_count


def test_combination_and_holdingkey_mutual_exclusive():
    pass
