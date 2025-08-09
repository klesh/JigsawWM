"""An example for nnako"""

#
# CONCEPT
#

# +----------+----------+----------+----------+
# |          |          |          |          |
# |          |          |          |          |
# |     5    |     6    |     7    |          |
# |          |          |          |          |
# |          |          |          |          |
# +----------+--+-----+-+----------+          |
# |             |     |            |          |
# |             |     |            |          |
# |             |     |            |          |
# |             |     |            |     3    |
# |             |  1  |      0     |          |
# |     4       |     |            |          |
# |             |     |            |          |
# |             |     |            |          |
# |             +-----+------------|          |
# |             |                  |          |
# |             |         2        |          |
# +-------------+------------------+----------+

# IDX  LAYER1            LAYER2     LAYER3
# ---------------------------------------------
# 0    NEOVIM
# 1    CMD
# 2    NOTEPAD++
# 3    FREEPLANE
# 4    CHROME
# 5    TEAMS             OUTLOOK    SSH / MUTT
# 6    yED
# 7    EXCEL PLAN        TOTALCMD


from functools import partial

from jigsawwm.app.daemon import Daemon
from jigsawwm.jmk.core import Vk
from jigsawwm.wm.manager import WmConfig
from jigsawwm.wm.config import WmRule


daemon = Daemon()

daemon.wm.hotkeys = [
    ([Vk.WIN, Vk.CTRL, Vk.J], daemon.wm.manager.next_window),
    ([Vk.WIN, Vk.CTRL, Vk.K], daemon.wm.manager.prev_window),
    ([Vk.WIN, Vk.SHIFT, Vk.J], daemon.wm.manager.swap_next),
    ([Vk.WIN, Vk.SHIFT, Vk.K], daemon.wm.manager.swap_prev),
    ("Win+Ctrl+/", daemon.wm.manager.set_master),
    ([Vk.WIN, Vk.CONTROL, Vk.SPACE], daemon.wm.manager.next_theme),
    ([Vk.WIN, Vk.U], daemon.wm.manager.prev_monitor),
    ([Vk.WIN, Vk.I], daemon.wm.manager.next_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.U], daemon.wm.manager.move_to_prev_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.I], daemon.wm.manager.move_to_next_monitor),
    ([Vk.WIN, Vk.CONTROL, Vk.I], daemon.wm.manager.inspect_active_window),
    ("Win+Ctrl+a", partial(daemon.wm.manager.switch_to_workspace, 0)),
    ("Win+Ctrl+s", partial(daemon.wm.manager.switch_to_workspace, 1)),
    ("Win+Ctrl+d", partial(daemon.wm.manager.switch_to_workspace, 2)),
    ("Win+Ctrl+f", partial(daemon.wm.manager.switch_to_workspace, 3)),
    ("Win+Shift+a", partial(daemon.wm.manager.move_to_workspace, 0)),
    ("Win+Shift+s", partial(daemon.wm.manager.move_to_workspace, 1)),
    ("Win+Shift+d", partial(daemon.wm.manager.move_to_workspace, 2)),
    ("Win+Shift+f", partial(daemon.wm.manager.move_to_workspace, 3)),
    ("Win+Shift+Space", daemon.wm.manager.toggle_tilable),
    ("Win+Ctrl+u", daemon.wm.manager.inspect_state),
    (
        "XBUTTON1+RBUTTON",
        daemon.wm.manager.toggle_splash,
    ),  # browser forward button + right button
]

daemon.wm.manager.config = WmConfig(
    rules=[
    
        # list of application windows to be managed
        WmRule(exe="cmd.exe", title="nvim", static_window_index=0),
        WmRule(exe="cmd.exe", static_window_index=1),
        WmRule(exe="notepad++.exe", static_window_index=2),
        WmRule(
            exe="freeplane.exe",
            title="freeplane",
            static_window_index=3,
        ),
        WmRule(exe="chrome.exe", static_window_index=4),
        WmRule(exe="ms-teams.exe", static_window_index=5),
        WmRule(exe="yEd.exe", static_window_index=6),
        WmRule(exe="EXCEL.EXE", static_window_index=7),
        
        # list of application windows not to be regarded
        WmRule(exe="Len.exe", manageable=False),
        WmRule(exe="ApplicationFrameHost.exe", manageable=False),
        WmRule(exe="explorer.exe", manageable=False),
        WmRule(exe="mintty.exe", manageable=False),
        WmRule(exe="Len.exe", manageable=False),
        WmRule(exe="msedge.exe", manageable=False),
        WmRule(exe="OUTLOOK.EXE", manageable=False),
        WmRule(exe="SnagitCapture.exe", manageable=False),
        WmRule(exe="SnagitEditor.exe", manageable=False),
        WmRule(exe="SnippingTool.exe", manageable=False),
        WmRule(exe="TOTALCMD.exe", manageable=False),
    ],
)

daemon.start()
