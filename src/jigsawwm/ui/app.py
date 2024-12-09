"""This module provides a QApplication instance and a custom exception hook for handling uncaught exceptions."""

import logging
import sys
from ctypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import *  # pylint: disable=wildcard-import,unused-wildcard-import

from PySide6 import QtWidgets
from PySide6.QtCore import Signal as Signal
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)
app = QtWidgets.QApplication(sys.argv)

WM_POWERBROADCAST = 0x0218
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012


class SystemEventListener(QWidget):
    """A QWidget that listens for system events."""

    on_system_resumed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JigsawWM Event Listener")
        self.resize(300, 100)
        # show then hide in orde to receive events properly
        self.show()
        self.hide()

    def nativeEvent(self, eventType, message):
        if eventType == "windows_generic_MSG":
            msg = MSG.from_address(int(message))
            if msg.message == WM_POWERBROADCAST:
                if msg.wParam == PBT_APMRESUMESUSPEND:
                    print("System resumed from suspension (manual intervention).")
                elif msg.wParam == PBT_APMRESUMEAUTOMATIC:
                    self.on_system_resumed.emit()
        return super().nativeEvent(eventType, message)


system_event_listener = SystemEventListener()
