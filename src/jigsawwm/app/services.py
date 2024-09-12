"""Useful services"""

from jigsawwm.w32.sendinput import send_input, vk_to_input, Vk
from .job import ThreadedService


class CaffeineService(ThreadedService):
    """Caffeine keeps your PC awake"""

    name = "Caffeine"
    autorun = False
    interval_sec = 60

    def loop(self):
        send_input(
            vk_to_input(Vk.NONAME, pressed=True),
            vk_to_input(Vk.NONAME, pressed=False),
        )
