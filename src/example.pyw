from jigsawwm.daemon import Daemon


class MyDaemon(Daemon):
    def setup(self):
        from datetime import timedelta

        from mailcalaid.cal.holiday import ChinaHolidayBook

        from jigsawwm.manager import Theme, WindowManager
        from jigsawwm.services import ServiceEntry, register_service
        from jigsawwm.smartstart import (
            SmartStartEntry,
            daily_once,
            open_chrome_fav_folder,
            register_smartstart,
        )
        from jigsawwm.tiler import tilers
        from jigsawwm.w32.vk import Vk
        from jigsawwm.w32.window import (
            inspect_active_window,
            minimize_active_window,
            toggle_maximize_active_window,
        )

        # setup the WindowManager
        wm = WindowManager(
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

        # setup hotkeys
        self.hotkey([Vk.WIN, Vk.J], wm.activate_next)
        self.hotkey([Vk.WIN, Vk.K], wm.activate_prev)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.J], wm.swap_next)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.K], wm.swap_prev)
        self.hotkey([Vk.WIN, Vk.N], minimize_active_window)
        self.hotkey([Vk.WIN, Vk.M], toggle_maximize_active_window)
        self.hotkey("Win+/", wm.set_master)
        self.hotkey("Win+q", "LAlt+F4")
        # self.hotkey([Vk.WIN, Vk.SPACE], wm.next_theme)
        self.hotkey([Vk.WIN, Vk.U], wm.prev_monitor)
        self.hotkey([Vk.WIN, Vk.I], wm.next_monitor)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.U], wm.move_to_prev_monitor)
        self.hotkey([Vk.WIN, Vk.SHIFT, Vk.I], wm.move_to_next_monitor)
        self.hotkey([Vk.WIN, Vk.CONTROL, Vk.I], inspect_active_window)
        # forward button + middle button = ctrl + w (close tab)
        self.hotkey([Vk.XBUTTON2, Vk.LBUTTON], "LControl+w")
        # forward button + whell up  = ctrl + page up (previous tab)
        self.hotkey([Vk.XBUTTON2, Vk.WHEEL_UP], "LControl+prior")
        # forward button + whell down  = ctrl + page down (next tab)
        self.hotkey([Vk.XBUTTON2, Vk.WHEEL_DOWN], "LControl+next")

        # setup trayicon menu
        # self.menu_items = [pystray.MenuItem("Arrange All", wm.arrange_all_monitors)]

        # launch console programs (i.e. syncthing) as background service at startup
        register_service(
            ServiceEntry(
                name="syncthing",
                args=[
                    r"C:\Programs\syncthing-windows-amd64-v1.23.2\syncthing.exe",
                    "-no-browser",
                    "-no-restart",
                    "-no-upgrade",
                ],
                log_path=r"C:\Programs\syncthing-windows-amd64-v1.23.2\syncthing.log",
            )
        )

        # launch apps smartly at startup
        holiday_book = ChinaHolidayBook()

        # def open_worklog():
        #     """Open a worklog (markdown file) for today."""
        #     next_workday = holiday_book.next_workday()
        #     latest_workday = holiday_book.latest_workday()
        #     worklog_path = os.path.join(
        #         os.path.expanduser("~/Documents/Sync/worklog"),
        #         f"{next_workday.isoformat()}.md",
        #     )
        #     if not os.path.exists(worklog_path):
        #         with open(worklog_path, "w") as f:
        #             prevdate = latest_workday.strftime("%m/%d")
        #             nextdate = next_workday.strftime("%m/%d")
        #             f.write(f"{prevdate}\n1. \n\n{nextdate}\n1. ")
        #     os.startfile(worklog_path)

        register_smartstart(
            SmartStartEntry(
                name="daily routine",
                launch=lambda: open_chrome_fav_folder("bookmark_bar", "daily"),
                condition=lambda: daily_once("daily websites"),
            )
        )
        register_smartstart(
            SmartStartEntry(
                name="workhour routine",
                launch=[
                    r"C:\Users\Klesh\AppData\Local\Feishu\Feishu.exe",
                    r"C:\Program Files\Mozilla Thunderbird\thunderbird.exe",
                    r"C:\Users\Klesh\AppData\Local\Obsidian\Obsidian.exe",
                    # open_worklog,
                ],
                condition=lambda: holiday_book.is_workhour(extend=timedelta(hours=2)),
            )
        )

        return wm


MyDaemon().start()
