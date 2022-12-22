from jigsawwm.manager import WindowManager, timer, stop_all_timers
from jigsawwm.hotkey import register_hotkey, stop_all_hotkeys
from jigsawwm.w32.vk import VirtualKey
from jigsawwm.w32.window import toggle_maximize_active_window, minimize_active_window

# setup the WindowManager
wm = WindowManager(ignore_exe_names=["Feishu.exe"])

# register hotkey
register_hotkey([VirtualKey.VK_LWIN, VirtualKey.VK_KEY_J], wm.activate_next)
register_hotkey([VirtualKey.VK_RWIN, VirtualKey.VK_KEY_J], wm.activate_next)

register_hotkey([VirtualKey.VK_LWIN, VirtualKey.VK_KEY_K], wm.activate_prev)
register_hotkey([VirtualKey.VK_RWIN, VirtualKey.VK_KEY_K], wm.activate_prev)

register_hotkey([VirtualKey.VK_LWIN, VirtualKey.VK_KEY_N], minimize_active_window)
register_hotkey([VirtualKey.VK_RWIN, VirtualKey.VK_KEY_N], minimize_active_window)

register_hotkey(
    [VirtualKey.VK_LWIN, VirtualKey.VK_KEY_M], toggle_maximize_active_window
)
register_hotkey(
    [VirtualKey.VK_RWIN, VirtualKey.VK_KEY_M], toggle_maximize_active_window
)

register_hotkey(
    [VirtualKey.VK_LWIN, VirtualKey.VK_LSHIFT, VirtualKey.VK_KEY_J], wm.swap_next
)
register_hotkey(
    [VirtualKey.VK_RWIN, VirtualKey.VK_LSHIFT, VirtualKey.VK_KEY_J], wm.swap_next
)
register_hotkey(
    [VirtualKey.VK_LWIN, VirtualKey.VK_RSHIFT, VirtualKey.VK_KEY_J], wm.swap_next
)
register_hotkey(
    [VirtualKey.VK_RWIN, VirtualKey.VK_RSHIFT, VirtualKey.VK_KEY_J], wm.swap_next
)

register_hotkey(
    [VirtualKey.VK_LWIN, VirtualKey.VK_LSHIFT, VirtualKey.VK_KEY_K], wm.swap_prev
)
register_hotkey(
    [VirtualKey.VK_RWIN, VirtualKey.VK_LSHIFT, VirtualKey.VK_KEY_K], wm.swap_prev
)
register_hotkey(
    [VirtualKey.VK_LWIN, VirtualKey.VK_RSHIFT, VirtualKey.VK_KEY_J], wm.swap_prev
)
register_hotkey(
    [VirtualKey.VK_RWIN, VirtualKey.VK_RSHIFT, VirtualKey.VK_KEY_K], wm.swap_prev
)

register_hotkey([VirtualKey.VK_LWIN, VirtualKey.VK_KEY_K], wm.activate_prev)
register_hotkey([VirtualKey.VK_RWIN, VirtualKey.VK_KEY_K], wm.activate_prev)

register_hotkey([VirtualKey.VK_LWIN, VirtualKey.VK_OEM_2], wm.swap_master)
register_hotkey([VirtualKey.VK_RWIN, VirtualKey.VK_OEM_2], wm.swap_master)

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
