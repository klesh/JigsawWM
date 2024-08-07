"""Splash window for the list of windows and current workspace information."""
import logging

from typing import List, Optional
from ctypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import * # pylint: disable=wildcard-import,unused-wildcard-import

from PySide6.QtCore import QByteArray, QPoint, Qt, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from jigsawwm.w32.window import Window
from jigsawwm.wm.monitor_state import MonitorState

from .app import app
from .dialog import Dialog

logger = logging.getLogger(__name__)


class WindowsSplash(Dialog):
    """The window list splash screen."""

    show_splash = Signal(MonitorState, Window)
    hide_splash = Signal()
    worspace_widget: QLabel
    windows: List[Window]
    shellhook_msgid = 0
    created_windows = set()

    def __init__(self):
        super().__init__()
        self.windows = []
        self.show_splash.connect(self.show_windows_splash)
        self.hide_splash.connect(self.hide_windows_splash)

        self.worspace_widget = QLabel(self.root)
        self.worspace_widget.setObjectName("workspace")
        self.worspace_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.worspace_widget.setText("Workspace: ?")
        self.worspace_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root_layout.insertWidget(0, self.worspace_widget)
        logger.debug("WindowsSplash init")

    @Slot(MonitorState, Window)
    def show_windows_splash(self, monitor_state: MonitorState, active_window: Optional[Window]=None):
        """Show the splash screen"""
        logger.debug("WindowsSplash show")
        self.worspace_widget.setText(f"Workspace: {monitor_state.workspace.name} (theme: {monitor_state.workspace.theme_name})")
        h = 0
        w = self.width()
        if self.windows != monitor_state.tilable_windows:
            self.deleteDirectChildren(self.container)
            self.windows = monitor_state.tilable_windows.copy()
            for window in self.windows:
                icon = QImage.fromHICON(window.icon_handle)
                widget: QWidget = self.create_row_widget(
                    self.container.width(), window.title, icon
                )
                widget.setObjectName("row")
                widget.setProperty("handle", window.handle)
                widget.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
                self.container_layout.addWidget(widget)
                widget.setFixedHeight(36)
                h += 36
                if w < widget.width():
                    w = widget.width()
        if len(self.windows) == 0:
            self.deleteDirectChildren(self.container)
            self.spacer = QLabel("Nothing here")
            self.spacer.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.spacer.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self.container_layout.addWidget(self.spacer)
        if active_window:
            for i in range(self.container_layout.count()):
                widget = self.container_layout.itemAt(i).widget()
                if widget.property("handle") == active_window.handle:
                    widget.setProperty("active", True)
                else:
                    widget.setProperty("active", False)
                widget.setStyleSheet("")
        # centering the window
        r = monitor_state.monitor.get_rect()
        rect = app.screenAt(QPoint(r.left, r.top)).geometry()
        x = rect.x() + (rect.width() - w) // 2
        y = rect.y() + (rect.height()) // 3
        self.setGeometry(x, y, w, h)
        self.show()

    @Slot()
    def hide_windows_splash(self):
        """Hide the splash screen"""
        logger.debug("WindowsSplash hide")
        self.hide()

    def nativeEvent(self, eventType: QByteArray | bytes, message: int) -> object:
        if eventType == "windows_generic_MSG":
            msg = MSG.from_address(int(message))
            if msg.message == self.shellhook_msgid:
                if msg.wParam == 1:
                    self.created_windows.add(msg.hWnd)
                    fire_shell_window_changed("created", msg.hWnd)
                elif msg.wParam == 2:
                    if msg.hWnd in self.created_windows:
                        self.created_windows.remove(msg.hWnd)
                    else:
                        return
                    fire_shell_window_changed("destroyed", msg.hWnd)
                elif msg.wParam == 4:
                    fire_shell_window_changed("activated", msg.hWnd)
        return super().nativeEvent(eventType, message)


instance = WindowsSplash()

user32 = WinDLL("user32", use_last_error=True)
instance.shellhook_msgid = user32.RegisterWindowMessageW("SHELLHOOK")
user32.RegisterShellHookWindow(instance.winId())
shell_windows_changed: callable = None

def on_shell_window_changed(callback):
    """Registers a callback function to be called when any shell window gets created or destroyed."""
    global shell_windows_changed # pylint: disable=global-statement
    shell_windows_changed = callback

def fire_shell_window_changed(event, window):
    """Fires the screenChanged event."""
    logger.debug("shell window change event: %s window: %s", event, window)
    if shell_windows_changed:
        shell_windows_changed(event, window)

show_windows_splash = instance.show_splash.emit
hide_windows_splash = instance.hide_splash.emit
