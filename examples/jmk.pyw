from datetime import datetime

from jigsawwm import daemon, jmk
from jigsawwm.w32.sendinput import send_text
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import minimize_active_window, toggle_maximize_active_window


def send_today_date():
    import time

    time.sleep(0.01)
    send_text(datetime.now().strftime("%Y-%m-%d"))


class JmkService(daemon.Service):
    name = "jmk"
    is_running = False

    def __init__(self):
        jmk.install_hotkey_hooks()
        self.jmk_group = jmk.Group("jmk")

    def start(self):
        self.is_running = True
        # map Win+q to Alt+F4
        self.jmk_group.hotkey("Win+q", "LAlt+F4")
        # forward button + middle button = ctrl + w (close tab)
        self.jmk_group.hotkey([Vk.XBUTTON2, Vk.LBUTTON], "LControl+w")
        # forward button + whell up  = ctrl + page up (previous tab)
        self.jmk_group.hotkey([Vk.XBUTTON2, Vk.WHEEL_UP], "LControl+prior")
        # forward button + wheel down  = ctrl + page down (next tab)
        self.jmk_group.hotkey([Vk.XBUTTON2, Vk.WHEEL_DOWN], "LControl+next")
        # press Win+Alt+d to enter today's date
        self.jmk_group.hotkey("Win+Alt+d", send_today_date)
        # map capslock to ctrl when held and `  when tapped
        self.jmk_group.holdtap(Vk.CAPITAL, tap="`", hold="LControl")
        # Win+n to minimize active window
        self.jmk_group.hotkey([Vk.WIN, Vk.N], minimize_active_window)
        # Win+m to maximize active window
        self.jmk_group.hotkey([Vk.WIN, Vk.M], toggle_maximize_active_window)

    def stop(self):
        self.jmk_group.uninstall()
        self.is_running = False


daemon.register(JmkService)

if __name__ == "__main__":
    daemon.message_loop()
