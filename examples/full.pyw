"""An example of setting up all features"""

import os
import time
from functools import partial

from jigsawwm.app.daemon import Daemon
from jigsawwm.app.job import ProcessService
from jigsawwm.app.services import CaffeineService
from jigsawwm.app.tasks import DailyWebsites, WorkdayAutoStart
from jigsawwm.jmk.core import JmkKey, JmkTapHold, Vk
from jigsawwm.jmk.jmk_service import (ctrl_shift_w, ctrl_w, send_now,
                                      send_now_compact, send_today,
                                      send_today_compact)
from jigsawwm.w32.sendinput import send_combination
from jigsawwm.w32.vk import Vk, parse_combination
from jigsawwm.w32.window import (Window, get_foreground_window,
                                 minimize_active_window)
from jigsawwm.wm.config import WmRule
from jigsawwm.wm.manager import WmConfig

# Window.enable_bound_compensation = False

daemon = Daemon()


daemon.jmk.core.register_layers(
    [
        {  # layer 0
            # map capslock to ctrl when held and `  when tapped
            Vk.CAPITAL: JmkTapHold(tap=Vk.ESCAPE, hold=Vk.LCONTROL),
            Vk.RETURN: JmkTapHold(tap=Vk.RETURN, hold=Vk.LCONTROL),
            # hold TAB to switch to layer 1
            Vk.TAB: JmkTapHold(tap=Vk.TAB, hold=1),
            # hold ' to switch to layer 2
            Vk.OEM_PERIOD: JmkTapHold(tap=Vk.OEM_PERIOD, hold=2),
            # hold space for SHIFT, tap for space
            Vk.SPACE: JmkTapHold(tap=Vk.SPACE, hold=Vk.LSHIFT),
            # hold backward mouse button to switch to layer 2
            Vk.XBUTTON1: JmkTapHold(tap=Vk.XBUTTON1, hold=2, term=0.4),
        },
        {  # layer 1
            # left hand
            Vk.A: JmkKey(Vk.HOME),
            Vk.E: JmkKey(Vk.END),
            Vk.D: JmkKey(Vk.DELETE),
            Vk.B: JmkKey("LCtrl+Left"),
            Vk.F: JmkKey("LCtrl+Right"),
            # right hand
            Vk.H: JmkKey(Vk.LEFT),
            Vk.J: JmkKey(Vk.DOWN),
            Vk.K: JmkKey(Vk.UP),
            Vk.L: JmkKey(Vk.RIGHT),
            Vk.U: JmkKey("LCtrl+Prior"),
            Vk.I: JmkKey("LCtrl+Next"),
            Vk.N: JmkKey(Vk.MEDIA_NEXT_TRACK),
            Vk.P: JmkKey(Vk.MEDIA_PREV_TRACK),
            Vk.OEM_COMMA: JmkKey(Vk.VOLUME_DOWN),
            Vk.OEM_PERIOD: JmkKey(Vk.VOLUME_UP),
            Vk.SLASH: JmkKey(Vk.MEDIA_PLAY_PAUSE),
            # helper
            Vk.T: JmkTapHold(on_tap=send_today, on_hold_down=send_now),
            Vk.C: JmkTapHold(on_tap=send_today_compact, on_hold_down=send_now_compact),
            # Vk.BACK: JmkKey(suspend_system),
            Vk.CAPITAL: JmkKey(Vk.CAPITAL),
        },
        {  # layer 2
            Vk.MBUTTON: JmkTapHold(on_tap=ctrl_w, hold=ctrl_shift_w),
            Vk.RBUTTON: JmkKey(daemon.wm.manager.toggle_splash),
        },
    ]
)
daemon.jmk.sysin.bypass_mouse_event = True


def send_comb_then_center_cursor_to_the_active_window(comb: str, delay: float = 0.5):
    """Send a hotkey combination then focus the active window"""
    send_combination(*parse_combination(comb))
    time.sleep(delay)
    fgw = get_foreground_window()
    if fgw:
        Window(fgw).center_cursor()


COPY_PASTE = (parse_combination("LCtrl+c"), parse_combination("LCtrl+v"))
COPY_PASTE_SHIFT = (
    parse_combination("LCtrl+LShift+c"),
    parse_combination("LCtrl+LShift+v"),
)


def smart_copy_paste(op: str = "copy"):
    """Send Ctrl+c/v or Ctrl+Shift+c/v base on the active window"""
    combs = COPY_PASTE
    fgwh = get_foreground_window()
    if fgwh:
        fgw = Window(fgwh)
        if fgw.exe_name.lower() in ("windowsterminal.exe", "code.exe"):
            combs = COPY_PASTE_SHIFT
    comb = combs[0 if op == "copy" else 1]
    send_combination(*comb)

def system_sleep():
    send_combination(Vk.LWIN, Vk.X)
    time.sleep(0.3)
    send_combination(Vk.U)
    send_combination(Vk.S)


daemon.jmk.hotkeys.register_triggers(
    [
        ("Win+q", "LAlt+F4"),
        ("Win+s", "RCtrl+s"),
        ("Win+z", "RCtrl+z"),
        ("Win+c", partial(smart_copy_paste, "copy")),
        ("Win+v", partial(smart_copy_paste, "paste")),
        ("Win+Shift+v", "RWin+v"),
        (
            "Win+Ctrl+w",
            partial(send_comb_then_center_cursor_to_the_active_window, "RCtrl+RAlt+w"),
        ),
        (
            "Win+Ctrl+e",
            partial(send_comb_then_center_cursor_to_the_active_window, "RCtrl+RAlt+e"),
        ),
        ("Win+Ctrl+l", "LWin+LCtrl+Right"),
        ("Win+Ctrl+h", "LWin+LCtrl+Left"),
        ("Win+Ctrl+q", daemon.quit_act.triggered.emit),
        ("Win+Ctrl+f1", system_sleep),
        ([Vk.WIN, Vk.N], minimize_active_window),
        ([Vk.RCONTROL, Vk.SLASH], "RCtrl+x"),
        ([Vk.RCONTROL, Vk.PERIOD], "RCtrl+c"),
        ([Vk.RCONTROL, Vk.COMMA], "RCtrl+v"),
    ]
)

daemon.wm.hotkeys = [
    ([Vk.WIN, Vk.CTRL, Vk.J], daemon.wm.manager.next_window),
    ([Vk.WIN, Vk.CTRL, Vk.K], daemon.wm.manager.prev_window),
    ([Vk.WIN, Vk.SHIFT, Vk.J], daemon.wm.manager.swap_next),
    ([Vk.WIN, Vk.SHIFT, Vk.K], daemon.wm.manager.swap_prev),
    ("Win+Ctrl+/", daemon.wm.manager.set_master),
    ("Win+Ctrl+.", daemon.wm.manager.roll_next),
    ("Win+Ctrl+,", daemon.wm.manager.roll_prev),
    ([Vk.WIN, Vk.CONTROL, Vk.SPACE], daemon.wm.manager.next_theme),
    ([Vk.WIN, Vk.CTRL, Vk.U], daemon.wm.manager.prev_monitor),
    ([Vk.WIN, Vk.CTRL, Vk.I], daemon.wm.manager.next_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.U], daemon.wm.manager.move_to_prev_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.I], daemon.wm.manager.move_to_next_monitor),
    ("Win+Ctrl+a", partial(daemon.wm.manager.switch_to_workspace, 0)),
    ("Win+Ctrl+s", partial(daemon.wm.manager.switch_to_workspace, 1)),
    ("Win+Ctrl+d", partial(daemon.wm.manager.switch_to_workspace, 2)),
    ("Win+Ctrl+f", partial(daemon.wm.manager.switch_to_workspace, 3)),
    # ("Win+Ctrl+j", partial(daemon.wm.manager.next_workspace)),
    # ("Win+Ctrl+k", partial(daemon.wm.manager.prev_workspace)),
    ("Win+Shift+a", partial(daemon.wm.manager.move_to_workspace, 0)),
    ("Win+Shift+s", partial(daemon.wm.manager.move_to_workspace, 1)),
    ("Win+Shift+d", partial(daemon.wm.manager.move_to_workspace, 2)),
    ("Win+Shift+f", partial(daemon.wm.manager.move_to_workspace, 3)),
    ("Win+Ctrl+Shift+j", partial(daemon.wm.manager.move_to_next_workspace)),
    ("Win+Ctrl+Shift+k", partial(daemon.wm.manager.move_to_prev_workspace)),
    ("Win+Shift+Space", daemon.wm.manager.toggle_tilable),
    ("Win+Ctrl+p", daemon.wm.manager.inspect_state),
    ([Vk.WIN, Vk.CONTROL, Vk.O], daemon.wm.manager.inspect_active_window),
    ([Vk.WIN, Vk.CONTROL, Vk.M], daemon.wm.manager.toggle_mono),
    (
        [Vk.WIN, Vk.CONTROL, Vk.SHIFT, Vk.S],
        partial(daemon.wm.manager.set_theme, "Stack"),
    ),
    (
        [Vk.WIN, Vk.CONTROL, Vk.SHIFT, Vk.D],
        partial(daemon.wm.manager.set_theme, "Dwindle"),
    ),
    ([Vk.CTRL, Vk.ESCAPE], daemon.wm.manager.show_floating_windows),
]

daemon.wm.manager.config = WmConfig(
    rules=[
        # WmRule(exe="WindowsTerminal.exe", manageable=False),
        WmRule(exe="SnippingTool.exe", manageable=False),
        WmRule(exe="Flow.Launcher.exe", manageable=False),
        WmRule(exe="msedgewebview2.exe", manageable=False),
        WmRule(exe="WeChat.exe", manageable=False),
        WmRule(exe="Weixin.exe", manageable=False),
        WmRule(exe="MediaInfo.exe", tilable=False),
        WmRule(exe="Cloudflare WARP.exe", tilable=False),
        WmRule(exe="7zFM.exe", tilable=False),
        WmRule(exe="fdm.exe", tilable=False),
        WmRule(exe="foobar2000.exe", tilable=False),
        WmRule(exe="notepad++.exe", tilable=False),
        WmRule(exe="PotPlayerMini64.exe", tilable=False),
        WmRule(exe="openvpn-gui.exe", tilable=False),
        WmRule(exe="Obsidian.exe", preferred_monitor_index=1),
        # WmRule(
        #     exe="Feishu.exe",
        #     title="(Feishu Meetings|飞书会议)",
        #     title_is_literal=False,
        #     manageable=True,
        #     tilable=False,
        # ),
        WmRule(exe="Feishu.exe", manageable=False),
        WmRule(exe="peazip.exe", tilable=False),
        WmRule(exe="clash-verge.exe", manageable=False),
        WmRule(exe="WXWork.exe", manageable=False),
        WmRule(exe="vmware.exe", tilable=False),
        # WmRule(
        #     exe="ApplicationFrameHost.exe", title="PDF Reader by Xodo", tilable=True
        # ),
        # WmRule(exe="ApplicationFrameHost.exe", tilable=False),
        WmRule(exe="YouTube Music.exe", manageable=False),
    ],
    # themes=["Dwindle", "Stack", "Mono"],
)

daemon.register(
    ProcessService(
        name="syncthing",
        args=[
            r"syncthing.exe",
            "--no-browser",
            "--no-restart",
            "--no-upgrade",
        ],
        log_path=os.path.join(os.getenv("LOCALAPPDATA"), "syncthing.log"),
    )
)

daemon.register(CaffeineService())

daemon.register(
    DailyWebsites(
        browser_name="brave",
        fav_folder="daily",
        test_url="https://google.com",
        proxy_url="http://localhost:7890",
    )
)
daemon.register(
    WorkdayAutoStart(
        country_code="CN",
        apps=[
            r"C:\Users\Klesh\AppData\Local\Feishu\Feishu.exe",
            r"C:\Program Files\Betterbird\betterbird.exe",
            r"C:\Users\Klesh\AppData\Local\Programs\obsidian\Obsidian.exe",
        ],
    )
)

daemon.start()
