"""Test wm.config module."""

from jigsawwm.wm.config import WmRule, WmConfig


def test_find_rule(mocker):
    """Test find_rule"""
    config = WmConfig()
    config.rules = [
        WmRule(exe_regex=r"\bWindowsTerminal\.exe$", manageable=False),
        WmRule(title_regex=r"Windows Terminal", tilable=False),
    ]
    config.prepare()
    window = mocker.Mock()
    window.exe = None
    window.title = None
    assert config.find_rule_for_window(window) is None

    window.exe = "WindowsTerminal.exe"
    r = config.find_rule_for_window(window)
    assert r.manageable is False
    assert r.tilable is None

    window.exe = None
    window.title = "Windows Terminal"
    r = config.find_rule_for_window(window)
    assert r.manageable is None
    assert r.tilable is False
