from datetime import datetime

from jigsawwm import daemon, hotkey
from jigsawwm.w32.sendinput import send_text
from jigsawwm.w32.vk import Vk


def setup_bindings():
    # map Win+q to Alt+F4
    hotkey.hotkey("Win+q", "LAlt+F4")
    # forward button + middle button = ctrl + w (close tab)
    hotkey.hotkey([Vk.XBUTTON2, Vk.LBUTTON], "LControl+w")
    # forward button + whell up  = ctrl + page up (previous tab)
    hotkey.hotkey([Vk.XBUTTON2, Vk.WHEEL_UP], "LControl+prior")
    # forward button + whell down  = ctrl + page down (next tab)
    hotkey.hotkey([Vk.XBUTTON2, Vk.WHEEL_DOWN], "LControl+next")
    # press Win+Alt+d to enter today's date
    hotkey.hotkey("Win+Alt+d", lambda: send_text(datetime.now().strftime("%Y-%m-%d")))
    hotkey.holding_hotkey


daemon.task(setup_bindings)
