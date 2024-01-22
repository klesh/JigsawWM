import os.path
import re
from ctypes.wintypes import DWORD, HWND, LONG
from queue import SimpleQueue
from typing import List, Set, Union

from jigsawwm.w32 import hook
from jigsawwm.w32.sendinput import is_synthesized, send_input, vk_to_input
from jigsawwm.w32.window import Window, get_active_window

from .core import *

q = SimpleQueue()


class SystemInput:
    """A handler that handles system input events.

    :param next_handler: the next handler in the chain, normally a JmkCore instance
    :param bypass_exe: a list of regular expression patterns that matches the exe path
        some applications (e.g. Windows 10's touch keyboard, emoji input) will not
        work properly, so we need to bypass them
    """

    hook_handles: List[hook.HHOOK] = None
    next_handler: JmkHandler
    focused_window: Window = None
    disabled: bool = False
    bypass_exe: Set[str] = None
    pressed_key: Set[Vk] = set()

    def __init__(self, next_handler: JmkHandler, bypass_exe: List[re.Pattern] = None):
        """Initialize a system input handler"""
        self.next_handler = next_handler
        self.bypass_exe = {
            "Snipaste.exe",
            "TextInputHost.exe",
            "vmplayer.exe",
        }
        if bypass_exe:
            self.bypass_exe.update(bypass_exe)
        self.pressed_key = set()

    def install(self):
        self.hook_handles = [
            hook.hook_keyboard(self.input_event_handler),
            hook.hook_mouse(self.input_event_handler),
            hook.hook_winevent(
                hook.WinEvent.EVENT_OBJECT_HIDE,
                hook.WinEvent.EVENT_OBJECT_FOCUS,
                self.winevent,
            ),
        ]

    def uninstall(self):
        for hook_handle in self.hook_handles:
            hook.unhook(hook_handle)

    def winevent(
        self,
        event: hook.WinEvent,
        hwnd: HWND,
        id_obj: LONG,
        id_chd: LONG,
        id_evt_thread: DWORD,
        time: DWORD,
    ):
        evt = hook.WinEvent(event)
        if evt != hook.WinEvent.EVENT_OBJECT_FOCUS:
            return
        if self.focused_window and self.focused_window.handle == hwnd:
            logger.debug("focused window not changed, ignore")
            return
        self.focused_window = get_active_window()
        logger.debug("event: %s, the active window: %s", evt.name, hwnd)
        if self.focused_window.is_evelated:
            logger.debug("focused window is elevated, disable jmk")
            self.disabled = True
            return
        logger.debug("focused window is not elevated")
        if self.bypass_exe:
            fwe = self.focused_window.exe
            if fwe and os.path.basename(fwe) in self.bypass_exe:
                logger.debug(
                    "focused window is in bypass list, disable jmk"
                )
                self.disabled = True
                return
        logger.debug("focused window is not in bypass list")
        logger.debug("jmk ENABLED!!!")
        self.disabled = False

    def input_event_handler(
        self,
        msgid: Union[hook.KBDLLHOOKMSGID, hook.MSLLHOOKMSGID],
        msg: Union[hook.KBDLLHOOKDATA, hook.MSLLHOOKDATA],
    ) -> bool:
        """Handles keyboard events and call callback if the combination
        had been registered
        """
        if is_synthesized(msg):
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
            return
        # bypass events when disabled unless it's a keyup event of a pressed key
        if self.disabled and (
            pressed or (not pressed and vkey not in self.pressed_key)
        ):
            return

        if pressed:
            self.pressed_key.add(vkey)
        elif vkey in self.pressed_key:
            self.pressed_key.remove(vkey)
        evt = JmkEvent(
            vkey, pressed, system=True, flags=msg.flags, extra=msg.dwExtraInfo
        )
        logger.debug("sys >>> %s", evt)
        swallow = self.next_handler(evt)
        return swallow


class SystemOutput(JmkHandler):
    """A system output handler that send input to system

    :param always_swallow: whether to always swallow the event, should be `True`
        when use as a Mouse/Keyboard transformer to keep the input order as expect,
        or `False` if you just need to register a system hotkey. default to True
    """

    always_swallow: bool

    def __init__(self, always_swallow: bool = True):
        self.always_swallow = always_swallow

    def __call__(self, evt: JmkEvent) -> bool:
        if evt.system and not self.always_swallow:
            logger.debug("nil <<< %s", evt)
            return False
        logger.debug("sys <<< %s", evt)
        q.put(evt)
        return True


def consume_queue():
    while True:
        evt = q.get()
        send_input(vk_to_input(evt.vk, evt.pressed, flags=evt.flags))


executor.submit(consume_queue)
