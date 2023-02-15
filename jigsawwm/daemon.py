import sys

sys.coinit_flags = 0x0
import io
import os.path
import time
from ctypes.wintypes import DWORD, HWND, LONG
from datetime import datetime
from threading import Thread
from tkinter import messagebox
from traceback import print_exception
from typing import Callable, Dict, Optional, Sequence, Union

import pystray
from PIL import Image

from jigsawwm.hotkey import hotkey, keyboard_event_handler
from jigsawwm.manager import WindowManager
from jigsawwm.w32.hook import Hook
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import Window, is_app_window, is_window
from jigsawwm.w32.winevent import WinEvent


class Daemon:
    _hook: Hook
    _timers: Dict[Callable, Thread] = {}
    _timer_thread: Thread
    _trayicon: pystray.Icon
    _started: bool = False
    _wm: WindowManager
    menu_items: Sequence[pystray.MenuItem] = []

    def __init__(self):
        self._hook = Hook()
        self._timers = {}
        self._timer_thread = None
        self._trayicon = None

    def error_handler(self, e: Exception):
        file = io.StringIO()
        print_exception(e, e, None, file=file)
        text = file.getvalue()
        print(text, file=sys.stderr)
        messagebox.showerror("JigsawWM", text)

    def hotkey(
        self,
        combkeys: Union[Sequence[Vk], str],
        target: Union[Callable, str],
        swallow: bool = True,
    ):
        try:
            hotkey(combkeys, target, swallow, self.error_handler)
        except Exception as e:
            self.error_handler(e)

    def start_hooks(self):
        self._hook.install_keyboard_hook(keyboard_event_handler)
        self._hook.install_winevent_hook(
            self.winevent_callback,
            WinEvent.EVENT_OBJECT_SHOW,
            WinEvent.EVENT_OBJECT_HIDE,
        )
        self._hook.install_winevent_hook(
            self.winevent_callback,
            WinEvent.EVENT_OBJECT_CLOAKED,
            WinEvent.EVENT_OBJECT_UNCLOAKED,
        )
        self._hook.install_winevent_hook(
            self.winevent_callback,
            WinEvent.EVENT_SYSTEM_MINIMIZESTART,
            WinEvent.EVENT_SYSTEM_MINIMIZEEND,
        )
        self._hook.install_winevent_hook(
            self.winevent_callback, WinEvent.EVENT_SYSTEM_MOVESIZEEND
        )
        self._hook.start()

    def winevent_callback(
        self,
        event: WinEvent,
        hwnd: HWND,
        id_obj: LONG,
        id_chd: LONG,
        id_evt_thread: DWORD,
        evt_time: DWORD,
    ):
        if (
            id_obj
            or id_chd
            or not is_window(hwnd)
            or not is_app_window(hwnd)
            or self._wm.is_ignored(Window(hwnd))
        ):
            return
        print(
            "[{now}] {event:30s} {hwnd:8d} {title}".format(
                now=datetime.now().strftime("%M:%S.%f"),
                event=event.name,
                hwnd=hwnd,
                #  ido: {id_obj:6d} idc: {id_chd:6d}
                # id_obj=id_obj,
                # id_chd=id_chd,
                title=Window(hwnd).title,
            )
        )
        self._wm.sync(restrict=event == WinEvent.EVENT_SYSTEM_MOVESIZEEND)

    def stop_hooks(self):
        self._hook.stop()

    def timer(self, interval: float, callback: Callable, once: Optional[bool] = False):
        """Run callback function with a fixed time interval repeatedly"""
        # wrap func with in try-catch for safty
        def run():
            # global _timers
            while callback in self._timers:
                time.sleep(interval)
                try:
                    callback()
                except Exception as e:
                    self.error_handler(e)
                if once:
                    del self._timers[callback]

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
        self._trayicon.run_detached()

    def stop_trayicon(self):
        self._trayicon.stop()
        self._trayicon = None

    def setup(self):
        pass

    def start(self):
        try:
            self._wm = self.setup()
        except Exception as e:
            self.error_handler(e)
            return
        self._started = True
        self.start_trayicon()
        self.start_timers()
        self.start_hooks()
        while self._started:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
                break

    def stop(self):
        self._started = False
        self.stop_hooks()
        self.stop_timers()
        self.stop_trayicon()
