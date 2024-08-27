"""Splash window for the list of windows and current workspace information."""
import logging

from typing import List, Optional
from ctypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import * # pylint: disable=wildcard-import,unused-wildcard-import

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget,QHBoxLayout, QVBoxLayout

from jigsawwm.w32.window import Window
from jigsawwm.wm.monitor_state import MonitorState

from .app import app
from .dialog import Dialog

logger = logging.getLogger(__name__)


class WindowsSplash(Dialog):
    """The window list splash screen."""

    show_splash = Signal(MonitorState, int, Window)
    hide_splash = Signal()
    monitor_state: QLabel
    workspace_states: QWidget
    windows: List[Window]
    shellhook_msgid = 0
    created_windows = set()

    def __init__(self):
        super().__init__()
        self.windows = []
        self.show_splash.connect(self.show_windows_splash)
        self.hide_splash.connect(self.hide_windows_splash)
        # monitor
        self.monitor_state = QLabel(self.root)
        self.monitor_state.setObjectName("monitor")
        self.monitor_state.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.monitor_state.setText("Monitor: ?")
        self.monitor_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root_layout.insertWidget(0, self.monitor_state)
        # workspace
        self.workspace_states = QWidget(self.root)
        self.workspace_states.setLayout(QHBoxLayout())
        self.workspace_states.setFixedHeight(100)
        self.root_layout.insertWidget(1, self.workspace_states)
        logger.info("WindowsSplash init")

    @Slot(MonitorState, Window)
    def show_windows_splash(self, monitor_state: MonitorState, workspace_index: int, active_window: Optional[Window]=None):
        """Show the splash screen"""
        logger.info("WindowsSplash show")
        # monitor
        self.monitor_state.setText(f"Monitor: {monitor_state.monitor.name}")
        # workspaces
        self.deleteDirectChildren(self.workspace_states)
        for i, workspace in enumerate(monitor_state.workspaces):
            widget = QWidget()
            widget.setObjectName("workspace")
            widget.setLayout(QVBoxLayout())
            widget.setProperty("active", i == workspace_index)
            # name
            ws_name = QLabel(workspace.name)
            ws_name.setObjectName("workspace_name")
            ws_name.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            ws_name.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignBottom)
            widget.layout().addWidget(ws_name)
            # theme
            ws_info = QLabel(workspace.theme_name)
            ws_info.setObjectName("workspace_info")
            ws_info.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            ws_info.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
            widget.layout().addWidget(ws_info)

            self.workspace_states.layout().addWidget(widget)
        h = self.workspace_states.height()
        w = self.width()
        tilable_windows = monitor_state.workspaces[workspace_index].tilable_windows
        if self.windows != tilable_windows:
            self.deleteDirectChildren(self.container)
            self.windows = tilable_windows.copy()
            for window in self.windows:
                icon = QImage.fromHICON(window.icon_handle)
                ws_name: QWidget = self.create_row_widget(
                    self.container.width(), window.title, icon
                )
                ws_name.setObjectName("row")
                ws_name.setProperty("handle", window.handle)
                ws_name.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
                self.container_layout.addWidget(ws_name)
                ws_name.setFixedHeight(36)
                h += 36
                if w < ws_name.width():
                    w = ws_name.width()
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
                ws_name = self.container_layout.itemAt(i).widget()
                if ws_name.property("handle") == active_window.handle:
                    ws_name.setProperty("active", True)
                else:
                    ws_name.setProperty("active", False)
                ws_name.setStyleSheet("")
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
        logger.info("WindowsSplash hide")
        self.hide()

    # def nativeEvent(self, eventType: QByteArray | bytes, message: int) -> object:
    #     if eventType == "windows_generic_MSG":
    #         msg = MSG.from_address(int(message))
    #         if msg.message == self.shellhook_msgid:
    #             if msg.wParam == 1:
    #                 self.created_windows.add(msg.hWnd)
    #                 fire_shell_window_changed("created", msg.hWnd)
    #             elif msg.wParam == 2:
    #                 if msg.hWnd in self.created_windows:
    #                     self.created_windows.remove(msg.hWnd)
    #                 else:
    #                     return
    #                 fire_shell_window_changed("destroyed", msg.hWnd)
    #             elif msg.wParam == 4:
    #                 fire_shell_window_changed("activated", msg.hWnd)
    #     return super().nativeEvent(eventType, message)

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

# show_windows_splash = instance.show_splash.emit
# hide_windows_splash = instance.hide_splash.emit

hide_before_show = False
showing = False

def show_windows_splash(monitor_state: MonitorState, workspace_index: int, active_window: Optional[Window] = None):
    global hide_before_show, showing
    if hide_before_show:
        hide_before_show = False
        showing = True
        return
    showing = True
    instance.show_splash.emit(monitor_state, workspace_index, active_window)

def hide_windows_splash():
    global hide_before_show, showing
    if not showing:
        hide_before_show = True
        return
    hide_before_show = False
    showing = False
    instance.hide_splash.emit()