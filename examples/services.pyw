from log import *
import time

from jigsawwm import daemon
from jigsawwm.w32.sendinput import send_input, vk_to_input, Vk


class SyncthingService(daemon.ProcessService):
    name = "syncthing"
    args = [
        r"C:\Users\Klesh\Programs\syncthing\syncthing.exe",
        "-no-browser",
        "-no-restart",
        "-no-upgrade",
    ]
    log_path = r"C:\Users\Klesh\Programs\syncthing\syncthing.log"

class CaffeineService(daemon.ThreadedService):
    name = "Caffeine"
    autorun = False
    interval_sec = 60

    def loop(self):
        send_input(
            vk_to_input(Vk.NONAME, pressed=True),
            vk_to_input(Vk.NONAME, pressed=False),
        )

daemon.register(SyncthingService)
daemon.register(CaffeineService)

if __name__ == "__main__":
    daemon.message_loop()
