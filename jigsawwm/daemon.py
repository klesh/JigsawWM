import sys

sys.coinit_flags = 0x0
from jigsawwm.hotkey import hook, hotkey
from typing import Dict, Callable, Sequence
from jigsawwm.w32.vk import Vk
from traceback import print_exception
from threading import Thread
from tkinter import messagebox
from PIL import Image
import pystray
import time
import os.path
import io


class Daemon:
    _timers: Dict[Callable, Thread] = {}
    _timer_thread: Thread
    _trayicon: pystray.Icon
    _trayicon_thread: Thread
    _started: bool = False
    menu_items: Sequence[pystray.MenuItem] = []

    def __init__(self):
        self._timers = {}
        self._timer_thread = None
        self._trayicon = None
        self._trayicon_thread = None

    def error_handler(self, e: Exception):
        file = io.StringIO()
        print_exception(e, file=file)
        text = file.getvalue()
        print(text, file=sys.stderr)
        messagebox.showerror("JigsawWM", text)

    def hotkey(
        self, combkeys: Sequence[Vk] | str, target: Callable | str, swallow: bool = True
    ):
        try:
            hotkey(combkeys, target, swallow, self.error_handler)
        except Exception as e:
            self.error_handler(e)

    def start_hotkeys(self):
        hook.start()

    def stop_hotkeys(self):
        hook.stop()

    def timer(self, interval: float, callback: Callable):
        """Run callback function with a fixed time interval repeatedly"""
        # wrap func with in try-catch for safty
        def run():
            # global _timers
            while callback in self._timers:
                try:
                    callback()
                except Exception as e:
                    self.error_handler(e)
                time.sleep(interval)

        self._timers[callback] = Thread(target=run)

    def start_timers(self):
        for timer_thread in self._timers.values():
            timer_thread.start()

    def stop_timers(self):
        self._timers.clear()

    def start_trayicon(self):
        script_dir = os.path.dirname(__file__)
        icon_path = os.path.join(script_dir, "assets", "logo.png")
        icon = Image.open(icon_path)
        tray_icon = pystray.Icon(
            "JigsawWM",
            icon=icon,
            menu=pystray.Menu(
                *self.menu_items,
                pystray.MenuItem("Exit", self.stop),
            ),
        )
        self._trayicon = tray_icon
        self._trayicon_thread = Thread(target=tray_icon.run)
        self._trayicon_thread.start()

    def stop_trayicon(self):
        self._trayicon.stop()

    def setup(self):
        pass

    def start(self):
        try:
            self.setup()
        except Exception as e:
            self.error_handler(e)
            return
        self._started = True
        self.start_trayicon()
        self.start_timers()
        self.start_hotkeys()
        while self._started:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
                break

    def stop(self):
        self._started = False
        self.stop_hotkeys()
        self.stop_timers()
        self.stop_trayicon()
