"""System input/output interfacing"""

import logging
import re
from ctypes.wintypes import DWORD, HWND, LONG
from typing import Callable, Dict, List, Optional, Set, Union

from jigsawwm.ui import system_event_listener
from jigsawwm.w32 import hook
from jigsawwm.w32.sendinput import is_synthesized, send_input, vk_to_input
from jigsawwm.w32.vk import Vk, is_key_down
from jigsawwm.w32.window_detector import Window, WindowDetector
from jigsawwm.worker import ThreadWorker

from .core import JmkEvent, JmkHandler

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
    is_running: bool = True
    next_handler_when_disabled: Optional[JmkHandler]
    bypass_exe: Set[str] = None
    pressed_evts: Dict[Vk, JmkEvent] = {}
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
        self.pressed_evts = {}
        self.window_detector = window_cache or WindowDetector()
        system_event_listener.on_system_resumed.connect(self.on_system_resumed)

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
            logger.info("focused window %s is elevated", window)
            self.disabled = True
            self.disabled_reason = "elevated window focused"
            return
        if window.exe == "TextInputHost.exe":
            logger.info("focused window %s is TextInputHost, ignore !!!", window)
            return
        if self.bypass_exe and window.exe_name.lower() in self.bypass_exe:
            logger.info("focused window %s is blacklisted", window)
            self.disabled = True
            return
        logger.info("focused window %s is a normal window, jmk ENABLED !!!", window)
        if self.disabled:
            self.on_system_resumed()
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
        if self.is_running is False:
            return False
        if is_synthesized(msg):
            logger.debug("synthesized event %s, skipping", msg)
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
        # we still need to keep track of system input for the following modules:
        #   - UI: detect mouse up on workspace widget
        #   - WM: detect merging chrome tabs
        if self.disabled:
            logger.debug("disabled due to %s, skipping %s", self.disabled_reason, msg)
            return False

        return True

    def on_system_resumed(self):
        """Handles the system resumed event"""
        logger.info("system resumed, fixing release events")
        self.enqueue(self.fix_release)

    def on_input(self, vkey: Vk, pressed: bool, flags=0, extra=0):
        """Handles the keyboard keys/mouse buttons events"""
        # keyup events might be missed, so we need to keep track of pressed keys
        evt = JmkEvent(vkey, pressed, system=True, flags=flags, extra=extra)
        if pressed:
            self.pressed_evts[vkey] = evt
        elif vkey in self.pressed_evts:
            del self.pressed_evts[vkey]
        # bypass events when disabled unless it's a keyup event of a pressed key
        logger.debug("sys >>> %s", evt)
        if self.disabled:
            if self.next_handler_when_disabled:
                self.next_handler_when_disabled(evt)
        else:
            self.next_handler(evt)

    def fix_release(self):
        """Fix the release event of a key that was missed"""
        for pk in list(self.pressed_evts.keys()):
            if not is_key_down(pk):
                logger.info("fixing release of %s", pk.name)
                # pevt = self.pressed_evts[pk]
                # self.on_input(pk, False, flags=pevt.flags, extra=pevt.extra)
                pevt = self.pressed_evts.pop(pk)
                pevt.pressed = False
                self.next_handler(pevt)


class SystemOutput(JmkHandler):
    """A system output handler that send input to system"""

    disabled: bool = False
    callbacks: Set[Callable[[JmkEvent], bool]]
    state: Dict[Vk, bool] = {}

    def __init__(self, input_sender=send_input):
        """Initialize a system output handler"""
        self.input_sender = input_sender
        self.callbacks = set()

    def __call__(self, evt: JmkEvent) -> bool:
        self.state[evt.vk] = evt.pressed
        swallow = False
        for callback in self.callbacks.copy():
            swallow |= bool(callback(evt))
        if swallow or self.disabled:
            return
        logger.debug("%s >>> sys", evt)
        self.input_sender(vk_to_input(evt.vk, evt.pressed, flags=evt.flags))
