from jmk import hks
from log import *
from functools import partial

from jigsawwm import daemon, ui
from jigsawwm.tiler import tilers
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import inspect_active_window
from jigsawwm.wm import Theme, WindowManager

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
            name="Dwindle",
            layout_tiler=tilers.dwindle_layout_tiler,
            strict=True,
            gap=2,
            new_window_as_master=True,
            affinity_index=lambda si: (5 if si.inch >= 20 else 0) + (5 if si.ratio < 2 else 0),
        ),
        Theme(
            name="Mono",
            layout_tiler=tilers.mono_layout_tiler,
            strict=True,
            affinity_index=lambda si: 10 if si.inch < 20 else 0,
        ),
        Theme(
            name="WideScreen Dwindle",
            layout_tiler=tilers.widescreen_dwindle_layout_tiler,
            icon_name="wide-dwindle.png",
            gap=2,
            strict=True,
            new_window_as_master=True,
            affinity_index=lambda si: (5 if si.inch >= 20 else 0) + (5 if si.ratio >= 2 else 0),
        ),
    ],
    ignore_exe_names=[
        "7zFM.exe",
        "explorer.exe",
        # "Feishu.exe",
        "fdm.exe",
        # "WeChat.exe",
        "foobar2000.exe",
        "ApplicationFrameHost.exe",
        "notepad++.exe",
        "PotPlayerMini64.exe",
        "mintty.exe",
        "openvpn-gui.exe",
        "Cloudflare WARP.exe",
        "MediaInfo.exe",
        "SnippingTool.exe",
        "WeChat.exe",
    ],
    force_managed_exe_names=["Lens.exe"],
)

hotkeys = [
    ([Vk.WIN, Vk.J], wm.activate_next, ui.hide_windows_splash),
    ([Vk.WIN, Vk.K], wm.activate_prev, ui.hide_windows_splash),
    ([Vk.WIN, Vk.SHIFT, Vk.J], wm.swap_next),
    ([Vk.WIN, Vk.SHIFT, Vk.K], wm.swap_prev),
    ("Win+/", wm.set_master),
    ([Vk.WIN, Vk.CONTROL, Vk.SPACE], wm.next_theme),
    ([Vk.WIN, Vk.U], wm.prev_monitor),
    ([Vk.WIN, Vk.I], wm.next_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.U], wm.move_to_prev_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.I], wm.move_to_next_monitor),
    ([Vk.WIN, Vk.CONTROL, Vk.I], inspect_active_window),
    ("Win+Ctrl+a", partial(wm.switch_desktop, 1)),
    ("Win+Ctrl+s", partial(wm.switch_desktop, 2)),
    ("Win+Ctrl+d", partial(wm.switch_desktop, 3)),
    ("Win+Ctrl+f", partial(wm.switch_desktop, 4)),
    ("Win+Shift+a", partial(wm.move_to_desktop, 1)),
    ("Win+Shift+s", partial(wm.move_to_desktop, 2)),
    ("Win+Shift+d", partial(wm.move_to_desktop, 3)),
    ("Win+Shift+f", partial(wm.move_to_desktop, 4)),
]


class WindowManagerService(daemon.Service):
    name = "Window Manager"
    is_running = False

    def start(self):
        self.is_running = True
        wm.install_hooks()
        for args in hotkeys:
            hks.register(*args)

    def stop(self):
        wm.uninstall_hooks()
        for args in hotkeys:
            hks.unregister(args[0])
        self.is_running = False


daemon.register(WindowManagerService)

if __name__ == "__main__":
    daemon.message_loop()
