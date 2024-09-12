"""An example for nnako"""

#
# CONCEPT
#

# +----------+----------+----------+----------+
# |          |          |          |          |
# |          |          |          |          |
# |     1    |     2    |     3    |          |
# |          |          |          |          |
# |          |          |          |          |
# +----------+--+-----+-+----------+          |
# |             |     |            |          |
# |             |     |            |          |
# |             |     |            |          |
# |             |     |            |     4    |
# |             |  6  |      7     |          |
# |     5       |     |            |          |
# |             |     |            |          |
# |             |     |            |          |
# |             +-----+------------|          |
# |             |                  |          |
# |             |         8        |          |
# +-------------+------------------+----------+

# IDX  LAYER1            LAYER2   LAYER3
# ---------------------------------------------
# 1    OUTLOOK           TEAMS    SSH / MUTT
# 2    TOTAL COMMANDER
# 3    EXCEL PLAN        yED
# 4    FREEPLANE
# 5    CHROME
# 6    NOTEPAD++
# 7    NEOVIM
# 8    CMD


from functools import partial

from jigsawwm.app.daemon import Daemon
from jigsawwm.jmk.core import Vk
from jigsawwm.wm.manager import WmConfig
from jigsawwm.wm.config import WmRule


daemon = Daemon()

daemon.wm.hotkeys = [
    ([Vk.WIN, Vk.J], daemon.wm.manager.next_window),
    ([Vk.WIN, Vk.K], daemon.wm.manager.prev_window),
    ([Vk.WIN, Vk.SHIFT, Vk.J], daemon.wm.manager.swap_next),
    ([Vk.WIN, Vk.SHIFT, Vk.K], daemon.wm.manager.swap_prev),
    ("Win+/", daemon.wm.manager.set_master),
    ([Vk.WIN, Vk.CONTROL, Vk.SPACE], daemon.wm.manager.next_theme),
    ([Vk.WIN, Vk.U], daemon.wm.manager.prev_monitor),
    ([Vk.WIN, Vk.I], daemon.wm.manager.next_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.U], daemon.wm.manager.move_to_prev_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.I], daemon.wm.manager.move_to_next_monitor),
    ([Vk.WIN, Vk.CONTROL, Vk.I], daemon.wm.manager.inspect_active_window),
    ("Win+Ctrl+a", partial(daemon.wm.manager.switch_workspace, 0)),
    ("Win+Ctrl+s", partial(daemon.wm.manager.switch_workspace, 1)),
    ("Win+Ctrl+d", partial(daemon.wm.manager.switch_workspace, 2)),
    ("Win+Ctrl+f", partial(daemon.wm.manager.switch_workspace, 3)),
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
        WmRule(exe="cmd.exe", title="nvim", static_window_index=0),  # code editor
        WmRule(exe="cmd.exe", static_window_index=1),  # debug console
        WmRule(exe="notepad++.exe", static_window_index=2),  # general text editor
        WmRule(
            exe="javaw.exe", title="freeplane", static_window_index=3
        ),  # mindmap editor
        WmRule(exe="chrome.exe", static_window_index=4),  # internet browser
        WmRule(exe="Teams.exe", static_window_index=5),  # messaging
        WmRule(exe="yEd.exe", static_window_index=6),  # diagramming
        WmRule(exe="EXCEL.EXE", static_window_index=7),  # organizational stuff
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
