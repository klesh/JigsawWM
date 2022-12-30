import pystray

from jigsawwm.daemon import Daemon
from jigsawwm.manager import Preference, WindowManager
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import minimize_active_window, toggle_maximize_active_window


class MyDaemon(Daemon):
    wm: WindowManager

    def setup(self):

        # setup the WindowManager
        wm = WindowManager(
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
            pref=Preference(gap=2, strict=True),
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

        # setup trayicon menu
        self.menu_items = [pystray.MenuItem("Arrange All", wm.arrange_all_monitors)]

        return wm


MyDaemon().start()
