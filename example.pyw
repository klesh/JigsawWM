from jigsawwm.manager import WindowManager
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import toggle_maximize_active_window, minimize_active_window
from jigsawwm.daemon import Daemon


class MyDaemon(Daemon):
    wm: WindowManager

    def setup(self):
        super().__init__()
        # setup the WindowManager
        wm = WindowManager(
            new_window_as_master=False,
            ignore_exe_names=[
                "7zFM.exe",
                "explorer.exe",
                "Feishu.exe",
                "fdm.exe",
                "WeChat.exe",
                "foobar2000.exe",
                "ApplicationFrameHost.exe",
            ],
        )

        self.hotkey([Vk.WIN, Vk.J], wm.activate_next)
        self.hotkey([Vk.WIN, Vk.K], wm.activate_prev)
        self.hotkey([Vk.WIN, Vk.N], minimize_active_window)
        self.hotkey([Vk.WIN, Vk.M], toggle_maximize_active_window)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.J], wm.swap_next)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.K], wm.swap_prev)
        self.hotkey([Vk.WIN, Vk.K], wm.activate_prev)
        self.hotkey("Win+/", wm.swap_master)
        self.hotkey([Vk.WIN, Vk.R], wm.arrange_all_monitors)
        self.hotkey("Win+q", "LAlt+F4")
        self.hotkey([Vk.WIN, Vk.SPACE], wm.next_layout_tiler)
        self.timer(1, wm.sync)


MyDaemon().start()
