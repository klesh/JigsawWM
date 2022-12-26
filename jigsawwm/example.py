from jigsawwm.manager import WindowManager
from jigsawwm.hotkey import hotkey
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import toggle_maximize_active_window, minimize_active_window
from jigsawwm.daemon import daemon, timer

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

# register hotkey
hotkey([Vk.WIN, Vk.J], wm.activate_next)
hotkey([Vk.WIN, Vk.K], wm.activate_prev)
hotkey([Vk.WIN, Vk.N], minimize_active_window)
hotkey([Vk.WIN, Vk.M], toggle_maximize_active_window)
hotkey([Vk.WIN, Vk.SHIFT, Vk.J], wm.swap_next)
hotkey([Vk.WIN, Vk.SHIFT, Vk.K], wm.swap_prev)
hotkey([Vk.WIN, Vk.K], wm.activate_prev)
hotkey("Win+/", wm.swap_master)
hotkey([Vk.WIN, Vk.R], wm.arrange_all_monitors)
hotkey("Win+q", "LAlt+F4")
hotkey([Vk.WIN, Vk.SPACE], wm.next_layout_tiler)

# polling
timer(1, wm.sync)

# kickstart
daemon(console=True)
