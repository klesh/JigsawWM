"""Jmk Service"""

from datetime import datetime
from jigsawwm.app.job import Service
from jigsawwm.w32.sendinput import send_combination, send_text, Vk

from .sysinout import SystemInput, SystemOutput
from .core import JmkCore
from .hotkey import JmkHotkeys


class JmkService(Service):
    """JMK service"""

    name = "jmk"
    is_running = False

    def __init__(self):
        self.sysin = SystemInput()
        self.core = JmkCore()
        self.hotkeys = JmkHotkeys()
        self.sysout = SystemOutput()
        self.sysin.pipe(self.core).pipe(self.hotkeys).pipe(self.sysout)
        self.sysin.next_handler_when_disabled = self.sysout
        self.sysin.start()

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False
        self.sysin.disabled = True
        self.sysout.disabled = True

    def shutdown(self):
        self.sysin.stop()


def send_today():
    """Send today's date as text input, e.g.: 2024-09-12"""
    send_text(datetime.now().strftime("%Y-%m-%d"))


def send_today_compact():
    """Send today's date in compact form as text input, e.g.: 20240912"""
    send_text(datetime.now().strftime("%Y-%m-%d"))


def send_now():
    """Send current date and time as text input, e.g.: 2024-09-12 13:53:03"""
    send_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def send_now_compact():
    """Send current date and time in compact form as text input, e.g.: 20240912135303"""
    send_text(datetime.now().strftime("%Y%m%d%H%M%S"))


def ctrl_w():
    """Send Ctrl+w"""
    send_combination(Vk.LCONTROL, Vk.W)


def ctrl_shift_w():
    """Send Ctrl+w"""
    send_combination(Vk.LCONTROL, Vk.SHIFT, Vk.W)