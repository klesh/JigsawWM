import pystray

from jigsawwm.daemon import Daemon
from jigsawwm.manager import Theme, WindowManager
from jigsawwm.tiler import tilers
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import minimize_active_window, toggle_maximize_active_window


class MyDaemon(Daemon):
    def setup(self):

        # setup the WindowManager
        wm = WindowManager(
            themes=[
                Theme(
                    name="WideScreen Dwindle",
                    layout_tiler=tilers.widescreen_dwindle_layout_tiler,
                    icon_name="wide-dwindle.png",
                    background=r"D:\Documents\wallpapers\IMG_20220816_102143.jpg",
                    gap=2,
                    strict=True,
                ),
                Theme(
                    name="OBS Dwindle",
                    layout_tiler=tilers.obs_dwindle_layout_tiler,
                    icon_name="obs.png",
                    background=r"D:\Documents\wallpapers\obs-green.png",
                    gap=2,
                    strict=True,
                ),
            ],
            ignore_exe_names=[
                "7zFM.exe",
                "explorer.exe",
                "Feishu.exe",
                "fdm.exe",
                "WeChat.exe",
                "foobar2000.exe",
                "ApplicationFrameHost.exe",
                "notepad++.exe",
                "PotPlayerMini64.exe",
            ],
        )

        # setup hotkeys
        self.hotkey([Vk.WIN, Vk.J], wm.activate_next)
        self.hotkey([Vk.WIN, Vk.K], wm.activate_prev)
        self.hotkey([Vk.WIN, Vk.N], minimize_active_window)
        self.hotkey([Vk.WIN, Vk.M], toggle_maximize_active_window)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.J], wm.swap_next)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.K], wm.swap_prev)
        self.hotkey([Vk.WIN, Vk.K], wm.activate_prev)
        self.hotkey("Win+/", wm.swap_master)
        self.hotkey([Vk.WIN, Vk.CONTROL, Vk.R], wm.arrange_all_monitors)
        self.hotkey("Win+q", "LAlt+F4")
        self.hotkey([Vk.WIN, Vk.SPACE], wm.next_theme)
        self.hotkey([Vk.WIN, Vk.U], wm.prev_monitor)
        self.hotkey([Vk.WIN, Vk.I], wm.next_monitor)

        # setup trayicon menu
        self.menu_items = [pystray.MenuItem("Arrange All", wm.arrange_all_monitors)]

        return wm


MyDaemon().start()
