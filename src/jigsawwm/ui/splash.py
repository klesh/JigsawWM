"""Splash window for the list of windows and current workspace information."""

import logging

from typing import List, Optional
from ctypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import *  # pylint: disable=wildcard-import,unused-wildcard-import

from PySide6.QtCore import QPoint, Qt, Signal, Slot, QByteArray
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget, QHBoxLayout, QVBoxLayout

from jigsawwm.w32.window import Window
from jigsawwm.wm.monitor_state import MonitorState

from .app import app
from .dialog import Dialog

logger = logging.getLogger(__name__)


class Splash(Dialog):
    """The window list splash screen."""

    show_splash = Signal(MonitorState, int, Window)
    hide_splash = Signal()
    monitor_state: QLabel
    workspace_states: QWidget
    windows: List[Window]
    shellhook_msgid = 0
    created_windows = set()
    show_counter = 0

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
        self._register_shellhook()
        logger.info("WindowsSplash init")

    def _register_shellhook(self):
        user32 = WinDLL("user32", use_last_error=True)
        self.shellhook_msgid = user32.RegisterWindowMessageW("SHELLHOOK")
        if not user32.RegisterShellHookWindow(self.winId()):
            raise WinError(get_last_error())

    def nativeEvent(self, eventType: QByteArray | bytes, message: int) -> object:
        if eventType == "windows_generic_MSG":
            msg = MSG.from_address(int(message))
            if msg.message == self.shellhook_msgid:
                if msg.wParam == 1:
                    self.created_windows.add(msg.hWnd)
                    logger.debug("window %s created", msg.hWnd)
                elif msg.wParam == 2:
                    logger.debug("window %s destroyed", msg.hWnd)
                elif msg.wParam == 4:
                    logger.debug("window %s activated", msg.hWnd)
        return super().nativeEvent(eventType, message)

    @Slot(MonitorState, int, Window)
    def show_windows_splash(
        self,
        monitor_state: MonitorState,
        workspace_index: int,
        active_window: Optional[Window] = None,
    ):
        """Show the splash screen"""
        logger.info("WindowsSplash show")
        # monitor
        self.monitor_state.setText(f"Monitor: {monitor_state.name}")
        # workspaces
        self.deleteDirectChildren(self.workspace_states)
        if workspace_index == -1:
            workspace_index = monitor_state.active_workspace_index
        if active_window is None:
            active_window = monitor_state.workspaces[workspace_index].last_active_window
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
            ws_name.setAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
            )
            widget.layout().addWidget(ws_name)
            # theme
            ws_info = QLabel(workspace.theme.name)
            ws_info.setObjectName("workspace_info")
            ws_info.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            ws_info.setAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
            )
            widget.layout().addWidget(ws_info)

            self.workspace_states.layout().addWidget(widget)
        h = self.workspace_states.height()
        w = self.width()
        tilable_windows = monitor_state.workspaces[workspace_index].tiling_windows
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
        r = monitor_state.rect
        rect = app.screenAt(QPoint(r.left, r.top)).geometry()
        x = rect.x() + (rect.width() - w) // 2
        y = rect.y() + (rect.height()) // 3
        self.setGeometry(x, y, w, h)
        self.show_counter += 1
        if self.show_counter % 2 == 0:
            logger.info("ignore show_windows_splash due to hide_before_show")
            return
        self.show()

    @Slot()
    def hide_windows_splash(self):
        """Hide the splash screen"""
        self.show_counter += 1
        logger.info("WindowsSplash hide")
        self.hide()


if __name__ == "__main__":
    import signal

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Splash()
    # splash.show()
    app.exec()