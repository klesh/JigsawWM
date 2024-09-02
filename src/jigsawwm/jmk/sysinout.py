"""System input/output interfacing"""

import re
import logging
from ctypes.wintypes import DWORD, HWND, LONG
from typing import List, Set, Union

from jigsawwm.w32 import hook
from jigsawwm.w32.sendinput import is_synthesized, vk_to_input, send_input
from jigsawwm.w32.window_detector import Window, WindowDetector
from jigsawwm.worker import ThreadWorker

from .core import JmkHandler, JmkEvent, Vk

state = {}
logger = logging.getLogger(__name__)

JMK_MSG_CLOSE = 0
JMK_MSG_CALL = 1


class SystemInput(ThreadWorker, JmkHandler):
    """A handler that handles system input events.

    :param bypass_exe: a list of regular expression patterns that matches the exe path
        some applications (e.g. Windows 10's touch keyboard, emoji input) will not
        work properly, so we need to bypass them
    """

    hook_handles: List[hook.HHOOK] = None
    focused_window: Window = None
    disabled: bool = False
    disabled_reason: str = None
    bypass_exe: Set[str] = None
    pressed_key: Set[Vk] = set()
    window_detector: WindowDetector = None

    def __init__(
        self,
        bypass_exe: Set[re.Pattern] = None,
        window_cache: WindowDetector = None,
    ):
        self.bypass_exe = {
            "Snipaste.exe",
            "TextInputHost.exe",
            "vmplayer.exe",
        }
        if bypass_exe:
            self.bypass_exe |= bypass_exe
        self.pressed_key = set()
        self.window_detector = window_cache or WindowDetector()

    def start(self):
        """Start the system input handler"""
        self.start_worker()
        self.hook_handles = [
            hook.hook_keyboard(self.input_event),
            hook.hook_mouse(self.input_event),
            hook.hook_winevent(
                hook.WinEvent.EVENT_OBJECT_FOCUS,
                hook.WinEvent.EVENT_OBJECT_FOCUS,
                self.winevent,
            ),
        ]

    def stop(self):
        """Stop the system input handler"""
        for hook_handle in self.hook_handles:
            hook.unhook(hook_handle)
        self.stop_worker()

    def on_consume_queue_error(self, fn: callable, err: Exception):
        """Handle an error in the consume queue"""
        self.disabled = True
        self.disabled_reason = f"error calling {fn.__name__}: %s" % err

    def winevent(
        self,
        _event: hook.WinEvent,
        hwnd: HWND,
        _id_obj: LONG,
        _id_chd: LONG,
        _id_evt_thread: DWORD,
        _time: DWORD,
    ):
        """Handles window events and update the focused window"""
        self.enqueue(self.on_focus_changed, hwnd)

    def on_focus_changed(self, hwnd: HWND):
        """Handles the window focus change event"""
        window = self.window_detector.get_window(hwnd)
        if window.is_elevated:
            logger.debug("focused window %s is elevated", window)
            self.disabled = True
            self.disabled_reason = "elevated window focused"
            return
        if self.bypass_exe and window.exe_name.lower() in self.bypass_exe:
            logger.debug("focused window %s is blacklisted", window)
            self.disabled = True
            return
        logger.debug("focused window %s is a normal, jmk ENABLED !!!", window)
        self.disabled = False

    def input_event(
        self,
        _code: int,
        msgid: Union[hook.KBDLLHOOKMSGID, hook.MSLLHOOKMSGID],
        msg: Union[hook.KBDLLHOOKDATA, hook.MSLLHOOKDATA],
    ) -> bool:
        """Handles keyboard events and call callback if the combination
        had been registered
        """
        if is_synthesized(msg):
            logger.debug("synthesized event %s, skipping", msg)
            return False
        if self.disabled:
            logger.debug("disabled due to %s, skipping %s", self.disabled_reason, msg)
            return False
        # convert keyboard/mouse event to a unified virtual key representation
        vkey, pressed = None, None
        if isinstance(msgid, hook.KBDLLHOOKMSGID):
            vkey = Vk(msg.vkCode)
            if vkey == Vk.PACKET:
                return False
            # if msg.flags & 0b10000:  # skip injected events
            #     return True
            if msgid == hook.KBDLLHOOKMSGID.WM_KEYDOWN:
                pressed = True
            elif msgid == hook.KBDLLHOOKMSGID.WM_KEYUP:
                pressed = False
            else:
                return False
        elif isinstance(msgid, hook.MSLLHOOKMSGID):
            # return False # chrome 126.0.6478.63 select not accepting synthetic mouse events correctly
            if msgid == hook.MSLLHOOKMSGID.WM_LBUTTONDOWN:
                vkey = Vk.LBUTTON
                pressed = True
            elif msgid == hook.MSLLHOOKMSGID.WM_LBUTTONUP:
                vkey = Vk.LBUTTON
                pressed = False
            elif msgid == hook.MSLLHOOKMSGID.WM_RBUTTONDOWN:
                vkey = Vk.RBUTTON
                pressed = True
            elif msgid == hook.MSLLHOOKMSGID.WM_RBUTTONUP:
                vkey = Vk.RBUTTON
                pressed = False
            elif msgid == hook.MSLLHOOKMSGID.WM_MBUTTONDOWN:
                vkey = Vk.MBUTTON
                pressed = True
            elif msgid == hook.MSLLHOOKMSGID.WM_MBUTTONUP:
                vkey = Vk.MBUTTON
                pressed = False
            elif msgid == hook.MSLLHOOKMSGID.WM_XBUTTONDOWN:
                vkey = Vk.XBUTTON1 if msg.hiword() == 1 else Vk.XBUTTON2
                pressed = True
            elif msgid == hook.MSLLHOOKMSGID.WM_XBUTTONUP:
                vkey = Vk.XBUTTON1 if msg.hiword() == 1 else Vk.XBUTTON2
                pressed = False
            elif msgid == hook.MSLLHOOKMSGID.WM_MOUSEWHEEL:
                delta = msg.get_wheel_delta()
                if delta > 0:
                    vkey = Vk.WHEEL_UP
                else:
                    vkey = Vk.WHEEL_DOWN
                pressed = False
        # skip events that out of our interest
        if vkey is None or pressed is None:
            # logger.debug("unknown event %s, skipping", msg)
            return False
        self.enqueue(self.on_input, vkey, pressed, msg.flags, msg.dwExtraInfo)

        return True

    def on_input(self, vkey: Vk, pressed: bool, flags=0, extra=0):
        """Handles the keyboard keys/mouse buttons events"""
        # bypass events when disabled unless it's a keyup event of a pressed key

        if pressed:
            self.pressed_key.add(vkey)
        elif vkey in self.pressed_key:
            self.pressed_key.remove(vkey)
        evt = JmkEvent(vkey, pressed, system=True, flags=flags, extra=extra)
        logger.debug("sys >>> %s", evt)
        self.next_handler(evt)


class SystemOutput(JmkHandler):
    """A system output handler that send input to system"""

    def __init__(self, input_sender=send_input):
        """Initialize a system output handler"""
        self.input_sender = input_sender

    def __call__(self, evt: JmkEvent) -> bool:
        logger.debug("%s >>> sys", evt)
        state[evt.vk] = evt.pressed
        self.input_sender(vk_to_input(evt.vk, evt.pressed, flags=evt.flags))
