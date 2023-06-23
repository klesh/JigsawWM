from jigsawwm import daemon, jmk
from jigsawwm.tiler import tilers
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import inspect_active_window
from jigsawwm.wm import Theme, WindowManager


class WindowManagerService(daemon.Service):
    name = "Window Manager"
    is_running = False

    def __init__(self):
        jmk.install_hotkey_hooks()
        self.wm = WindowManager(
            themes=[
                Theme(
                    name="WideScreen Dwindle",
                    layout_tiler=tilers.widescreen_dwindle_layout_tiler,
                    icon_name="wide-dwindle.png",
                    # background=r"D:\Documents\wallpapers\IMG_20220816_102143.jpg",
                    gap=2,
                    strict=True,
                    new_window_as_master=True,
                ),
                Theme(
                    name="OBS Dwindle",
                    layout_tiler=tilers.obs_dwindle_layout_tiler,
                    icon_name="obs.png",
                    # background=r"D:\Documents\wallpapers\obs-green.png",
                    gap=2,
                    strict=True,
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
            ],
            force_managed_exe_names=["Lens.exe"],
        )
        self.jmk_group = jmk.Group("window manager")

    def start(self):
        self.wm.install_hooks()
        self.jmk_group.hotkey([Vk.WIN, Vk.J], self.wm.activate_next)
        self.jmk_group.hotkey([Vk.WIN, Vk.K], self.wm.activate_prev)
        self.jmk_group.hotkey([Vk.WIN, Vk.SHIFT, Vk.J], self.wm.swap_next)
        self.jmk_group.hotkey([Vk.WIN, Vk.SHIFT, Vk.K], self.wm.swap_prev)
        self.jmk_group.hotkey("Win+/", self.wm.set_master)
        self.jmk_group.hotkey([Vk.WIN, Vk.SPACE], self.wm.next_theme)
        self.jmk_group.hotkey([Vk.WIN, Vk.U], self.wm.prev_monitor)
        self.jmk_group.hotkey([Vk.WIN, Vk.I], self.wm.next_monitor)
        self.jmk_group.hotkey([Vk.WIN, Vk.SHIFT, Vk.U], self.wm.move_to_prev_monitor)
        self.jmk_group.hotkey([Vk.WIN, Vk.SHIFT, Vk.I], self.wm.move_to_next_monitor)
        self.jmk_group.hotkey([Vk.WIN, Vk.CONTROL, Vk.I], inspect_active_window)
        self.is_running = True

    def stop(self):
        self.jmk_group.uninstall()
        self.wm.uninstall_hooks()
        self.is_running = False


daemon.register(WindowManagerService)

if __name__ == "__main__":
    daemon.message_loop()
