from jigsawwm.hotkey import hotkey_thread
from typing import Dict, Callable
from traceback import print_exception
from threading import Thread
import time

error_handler = print_exception

# it is import to hold reference to the timer
# or they will be freed right away
_timers: Dict[Callable, Thread] = {}


def timer(interval: float, callback: Callable):
    """Run callback function with a fixed time delay between each call"""
    global _timers

    def run():
        # global _timers
        while callback in _timers:
            try:
                callback()
            except Exception as e:
                error_handler(e)
            time.sleep(interval)

    thread = Thread(target=run, daemon=True)
    _timers[callback] = thread
    thread.start()


def stop_all_timers():
    global _timers
    _timers.clear()


def daemon(console=True):
    hotkey_thread.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            hotkey_thread.stop()
            stop_all_timers()
            break
