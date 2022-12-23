from jigsawwm.manager import WindowManager, timer, stop_all_timers
from jigsawwm.hotkey import hotkey, stop_all_hotkeys
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import toggle_maximize_active_window, minimize_active_window

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
    ]
)

# register hotkey
hotkey([Vk.LWIN, Vk.J], wm.activate_next)
hotkey([Vk.RWIN, Vk.J], wm.activate_next)

hotkey([Vk.LWIN, Vk.K], wm.activate_prev)
hotkey([Vk.RWIN, Vk.K], wm.activate_prev)

hotkey([Vk.LWIN, Vk.N], minimize_active_window)
hotkey([Vk.RWIN, Vk.N], minimize_active_window)

hotkey([Vk.LWIN, Vk.M], toggle_maximize_active_window)
hotkey([Vk.RWIN, Vk.M], toggle_maximize_active_window)

hotkey([Vk.LWIN, Vk.LSHIFT, Vk.J], wm.swap_next)
hotkey([Vk.RWIN, Vk.LSHIFT, Vk.J], wm.swap_next)
hotkey([Vk.LWIN, Vk.RSHIFT, Vk.J], wm.swap_next)
hotkey([Vk.RWIN, Vk.RSHIFT, Vk.J], wm.swap_next)

hotkey([Vk.LWIN, Vk.LSHIFT, Vk.K], wm.swap_prev)
hotkey([Vk.RWIN, Vk.LSHIFT, Vk.K], wm.swap_prev)
hotkey([Vk.LWIN, Vk.RSHIFT, Vk.K], wm.swap_prev)
hotkey([Vk.RWIN, Vk.RSHIFT, Vk.K], wm.swap_prev)

hotkey([Vk.LWIN, Vk.K], wm.activate_prev)
hotkey([Vk.RWIN, Vk.K], wm.activate_prev)

hotkey([Vk.LWIN, Vk.OEM_2], wm.swap_master)
hotkey([Vk.RWIN, Vk.OEM_2], wm.swap_master)

hotkey([Vk.LWIN, Vk.R], wm.arrange_all_monitors)
# polling
timer(1, wm.sync)


# test
import time

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        stop_all_hotkeys()
        stop_all_timers()
        break
