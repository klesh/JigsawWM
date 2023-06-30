from queue import Queue
from typing import List, Union

from jigsawwm.w32 import hook
from jigsawwm.w32.sendinput import is_synthesized, send_input, vk_to_input

from .core import *

q = Queue()


class SystemInput:
    hook_handles: List[hook.HHOOK] = None
    next_handler: JmkHandler
    always_swallow: bool

    def __init__(self, next_handler: JmkHandler, always_swallow: bool = True):
        """Initialize a system input handler

        :param next_handler: the next handler in the chain
        :param always_swallow: whether to always swallow the event, should be `True`
            when use as a Mouse/Keyboard transformer to keep the input order as expect,
            or `False` if you just need to register a system hotkey. default to True
        """
        self.next_handler = next_handler
        self.always_swallow = always_swallow

    def install(self):
        self.hook_handles = [
            hook.hook_keyboard(self.input_event_handler),
            hook.hook_mouse(self.input_event_handler),
        ]

    def uninstall(self):
        for hook_handle in self.hook_handles:
            hook.unhook(hook_handle)

    def input_event_handler(
        self,
        msgid: Union[hook.KBDLLHOOKMSGID, hook.MSLLHOOKMSGID],
        msg: Union[hook.KBDLLHOOKDATA, hook.MSLLHOOKDATA],
    ) -> bool:
        """Handles keyboard events and call callback if the combination
        had been registered
        """
        # skip key we sent out
        if is_synthesized(msg):
            return False
        # convert keyboard/mouse event to a unified virtual key representation
        vkey, pressed = None, None
        if isinstance(msgid, hook.KBDLLHOOKMSGID):
            vkey = Vk(msg.vkCode)
            if vkey == Vk.PACKET:
                return False
            if (
                msgid == hook.KBDLLHOOKMSGID.WM_KEYDOWN
                or msgid == hook.KBDLLHOOKMSGID.WM_SYSKEYDOWN
            ):
                pressed = True
            elif (
                msgid == hook.KBDLLHOOKMSGID.WM_KEYUP
                or msgid == hook.KBDLLHOOKMSGID.WM_SYSKEYUP
            ):
                pressed = False
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
        evt = JmkEvent(vkey, pressed, system=True, extra=msg.dwExtraInfo)
        logger.debug("sys >>> %s", evt)
        swallow = self.next_handler(evt)
        return self.always_swallow or swallow


class SystemOutput(JmkHandler):
    def __call__(self, evt: JmkEvent) -> bool:
        logger.debug("sys <<< %s", evt)
        q.put(evt)
        return True


def consume_queue():
    while True:
        evt = q.get()
        send_input(vk_to_input(evt.vk, evt.pressed), extra=evt.extra)
        q.task_done()


executor.submit(consume_queue)
