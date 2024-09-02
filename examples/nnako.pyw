from jmk import hks
from log import *

from jigsawwm import daemon, ui
from jigsawwm.tiler import tilers
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import inspect_active_window
from jigsawwm.wm import Theme, WindowManager


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


#
# define window manager
#

wm = WindowManager(
    themes=[
        # Theme(
        #     name="OBS Dwindle",
        #     layout_tiler=tilers.obs_dwindle_layout_tiler,
        #     icon_name="obs.png",
        #     gap=2,
        #     strict=True,
        # ),
        Theme(
            name="static_bigscreen_8",
            layout_tiler=tilers.static_bigscreen_8_layout_tiler,
            static_layout=True,
            static_windows_count=8,
            strict=True,
            gap=2,
            new_window_as_master=True,
        ),
        Theme(
            name="Dwindle",
            layout_tiler=tilers.dwindle_layout_tiler,
            strict=True,
            gap=2,
            new_window_as_master=True,
        ),
        Theme(
            name="WideScreen Dwindle",
            layout_tiler=tilers.widescreen_dwindle_layout_tiler,
            icon_name="wide-dwindle.png",
            gap=2,
            strict=True,
            new_window_as_master=True,
        ),
        Theme(
            name="Mono",
            layout_tiler=tilers.mono_layout_tiler,
            strict=True,
        ),
    ],
    ignore_exe_names=[
        "ApplicationFrameHost.exe",  # ?
        #        "chrome.exe",               # Chrome web browser
        #        "Cloudflare WARP.exe",
        #        "cmd.exe",                  # cmd consoles
        #        "EXCEL.EXE",
        "explorer.exe",  # ?
        #        "freeplane.exe",            # mindmap editor
        #        "javaw.exe",                # mindmap editor
        #        "MediaInfo.exe",
        "mintty.exe",  # ?
        "msedge.exe",  # browser
        #        "notepad++.exe",            # text editor
        #        "openvpn-gui.exe",
        "OUTLOOK.EXE",
        "SnagitCapture.exe",
        "SnagitEditor.exe",
        "SnippingTool.exe",
        #        "Teams.exe",
        "TOTALCMD.EXE",
        #        "yEd.exe",
    ],
    force_managed_exe_names=["Lens.exe"],
    # TODO: rewrite by using WmRule with preferred window index
    # here the wished initial sequence of applications in order to correctly
    # fill the windows. these applications will not be ignored, so they don't
    # need to be listed within the ignore_exe_names list.
    init_exe_sequence=[
        ["cmd.exe", "nvim"],  # code editor
        ["cmd.exe", ""],  # debug console
        ["notepad++.exe", ""],  # general text editor
        ["javaw.exe", "freeplane"],  # mindmap editor
        ["chrome.exe", ""],  # internet browser
        ["Teams.exe", ""],  # messaging
        ["yEd.exe", ""],  # diagramming
        ["EXCEL.EXE", ""],  # organizational stuff
    ],
)


#
# define hotkeys
#

hotkeys = [
    ([Vk.WIN, Vk.J], wm.activate_next, ui.hide_windows_splash),
    ([Vk.WIN, Vk.K], wm.activate_prev, ui.hide_windows_splash),
    ([Vk.WIN, Vk.SHIFT, Vk.J], wm.swap_next),
    ([Vk.WIN, Vk.SHIFT, Vk.K], wm.swap_prev),
    ("Win+/", wm.set_master),
    ([Vk.WIN, Vk.SPACE], wm.next_theme),
    ([Vk.WIN, Vk.U], wm.prev_monitor),
    ([Vk.WIN, Vk.I], wm.next_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.U], wm.move_to_prev_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.I], wm.move_to_next_monitor),
    ([Vk.WIN, Vk.CONTROL, Vk.I], inspect_active_window),
]


class WindowManagerService(daemon.Service):
    name = "Window Manager"
    is_running = False

    def start(self):
        self.is_running = True

        #
        # install hooks
        #

        wm.install_hooks()

        #
        # register hotkeys
        #

        for args in hotkeys:
            hks.register(*args)

    def stop(self):

        #
        # uninstall hooks
        #

        wm.uninstall_hooks()

        #
        # register hotkeys
        #

        for args in hotkeys:
            hks.unregister(args[0])
        self.is_running = False


daemon.register(WindowManagerService)

if __name__ == "__main__":
    daemon.message_loop()
