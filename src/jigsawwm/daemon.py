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
from typing import Callable, Dict, List, Optional, Sequence, Union

import pystray
from PIL import Image

from jigsawwm.hotkey import hotkey, install_hotkey_hooks
from jigsawwm.manager import WindowManager
from jigsawwm.services import get_services
from jigsawwm.smartstart import get_smartstarts
from jigsawwm.w32 import hook
from jigsawwm.w32.vk import Vk
from jigsawwm.w32.window import Window, is_app_window, is_window
from jigsawwm.w32.winevent import WinEvent


class Daemon:
    """JigsawWM Daemon serivce, you must inherite this class and override the `setup` function
    to configurate the Manager.
    """

    _timers: Dict[Callable, Thread] = {}
    _timer_thread: Thread
    _trayicon: pystray.Icon
    _started: bool = False
    _wm: WindowManager
    menu_items: Sequence[pystray.MenuItem] = []

    def __init__(self):
        self._timers = {}
        self._timer_thread = None
        self._trayicon = None

    def _error_handler(self, e: Exception):
        file = io.StringIO()
        # print_exception(e, e, None, file=file)
        print_exception(*sys.exc_info(), file=file)
        text = file.getvalue()
        print(text, file=sys.stderr)
        messagebox.showerror("JigsawWM", text)

    def hotkey(
        self,
        combkeys: Union[Sequence[Vk], str],
        target: Union[Callable, str],
        swallow: bool = True,
    ):
        """Register a global hotkey

        :param Union[Sequence[Vk], str] combkeys: key combination, i.e. ``[Vk.WIN, Vk.J]`` or ``Win + j``
        :param Union[Callback, str] target: can be a callback function or another key combination
        :param bool swallow: stop event propagation to prevent combkeys being processed by other programs
        """
        try:
            hotkey(combkeys, target, swallow, self._error_handler)
        except Exception as e:
            self._error_handler(e)

    def start_hooks(self):
        """Start all hooks"""
        hook.hook_winevent(
            WinEvent.EVENT_OBJECT_SHOW,
            WinEvent.EVENT_OBJECT_HIDE,
            self._winevent_callback,
        )
        hook.hook_winevent(
            WinEvent.EVENT_OBJECT_CLOAKED,
            WinEvent.EVENT_OBJECT_UNCLOAKED,
            self._winevent_callback,
        )
        hook.hook_winevent(
            WinEvent.EVENT_SYSTEM_MINIMIZESTART,
            WinEvent.EVENT_SYSTEM_MINIMIZEEND,
            self._winevent_callback,
        )
        hook.hook_winevent(
            WinEvent.EVENT_SYSTEM_MOVESIZEEND,
            WinEvent.EVENT_SYSTEM_MOVESIZEEND,
            self._winevent_callback,
        )
        hook.hook_keyboard(hook.exit_on_key_q)
        install_hotkey_hooks()

    def _winevent_callback(
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

    def timer(self, interval: float, callback: Callable, once: Optional[bool] = False):
        """Run callback function with a fixed time interval repeatedly

        :param float interval: interval between calls
        :param Callable callback: function to be called
        :param bool once: function would be called only once
        """

        # wrap func with in try-catch for safty
        def run():
            # global _timers
            while callback in self._timers:
                time.sleep(interval)
                try:
                    callback()
                except Exception as e:
                    self._error_handler(e)
                if once:
                    del self._timers[callback]

        self._timers[callback] = Thread(target=run)

    def start_timers(self):
        """Start all timers"""
        for timer_thread in self._timers.values():
            timer_thread.start()

    def stop_timers(self):
        """Stop all timers"""
        self._timers.clear()

    def start_trayicon(self):
        """Start trayicon"""
        script_dir = os.path.dirname(__file__)
        icon_path = os.path.join(script_dir, "assets", "logo.png")
        icon = Image.open(icon_path)

        def dynamic_menu() -> List[pystray.MenuItem]:
            service_menu_items = [
                pystray.MenuItem(
                    f"[{service.status_text}] {service.name}",
                    service.toggle,
                )
                for service in get_services()
            ]
            smartstart_menu_items = [
                pystray.MenuItem(
                    f"{smartstart.name}",
                    smartstart.run_anyway,
                )
                for smartstart in get_smartstarts()
            ]
            return [
                *self.menu_items,
                *smartstart_menu_items,
                pystray.Menu.SEPARATOR,
                *service_menu_items,
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self.stop),
            ]

        tray_icon = pystray.Icon(
            "JigsawWM",
            icon=icon,
            menu=pystray.Menu(dynamic_menu),
        )
        self._trayicon = tray_icon
        self._trayicon.run()

    def stop_trayicon(self):
        """Stop trayicon"""
        self._trayicon.stop()
        self._trayicon = None

    def setup(self):
        """To be overrided by the users to configure the Window Manager"""
        pass

    def start(self):
        """Start daemon service"""
        try:
            self._wm = self.setup()
        except Exception as e:
            self._error_handler(e)
            sys.exit(1)
            return
        self._started = True
        self.start_timers()
        self.start_hooks()
        self.start_trayicon()
        # while self._started:
        #     try:
        #         time.sleep(1)
        #     except KeyboardInterrupt:
        #         self.stop()
        #         break

    def stop(self):
        """Stop daemon service"""
        self.stop_timers()
        self.stop_trayicon()
        self._started = False
