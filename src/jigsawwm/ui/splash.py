"""Splash window for the list of windows and current workspace information."""

import logging
import time
from ctypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from typing import List

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import QCursor, QImage
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from jigsawwm.jmk.core import JmkEvent, Vk
from jigsawwm.jmk.jmk_service import JmkService
from jigsawwm.w32 import hook
from jigsawwm.w32.window import Window, get_foreground_window
from jigsawwm.wm.monitor_state import MonitorState

from .app import app
from .dialog import Dialog

logger = logging.getLogger(__name__)


class Splash(Dialog):
    """The window list splash screen."""

    jmk: JmkService
    show_splash = Signal(MonitorState)
    hide_splash = Signal()
    on_move_to_workspace = Signal(int)
    on_mouse_up_signal = Signal()
    monitor_state: QLabel
    workspace_states: QWidget
    windows: List[Window]
    shellhook_msgid = 0
    mouse_hookid = 0
    created_windows = set()
    workspaces: List[QWidget] = []
    hidden_at: float = 0

    def __init__(self, jmk_service: JmkService):
        super().__init__()
        self.jmk = jmk_service
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
        # self._register_shellhook()
        self._register_hooks()
        logger.info("WindowsSplash init")

    def _register_hooks(self):
        logger.info("register hooks")
        self.mouse_hookid = hook.hook_mouse(self._on_system_mouse_move)
        self.on_mouse_up_signal.connect(self.on_mouse_up)
        self.jmk.sysout.callbacks.add(self._on_system_key_event)

    def _unregister_hooks(self):
        logger.info("unregister hooks")
        if self._on_system_key_event in self.jmk.sysout.callbacks:
            self.jmk.sysout.callbacks.remove(self._on_system_key_event)
        if self.mouse_hookid:
            hook.unhook(self.mouse_hookid)
            self.mouse_hookid = 0

    def _on_system_mouse_move(
        self, _ncode: int, msg_id: hook.MSLLHOOKMSGID, _data: hook.MSLLHOOKDATA
    ):
        if msg_id == hook.MSLLHOOKMSGID.WM_MOUSEMOVE and not self.isHidden():
            self.on_mouse_move()

    def _on_system_key_event(self, evt: JmkEvent):
        if evt.vk == Vk.LBUTTON and evt.pressed is False and not self.isHidden():
            self.on_mouse_up_signal.emit()

    @Slot(MonitorState)
    def show_windows_splash(self, monitor_state: MonitorState):
        """Show the splash screen"""
        logger.info("WindowsSplash show")
        # monitor
        self.monitor_state.setText(f"Monitor: {monitor_state.name}")
        # workspaces
        self.deleteDirectChildren(self.workspace_states)
        workspace_index = monitor_state.active_workspace_index
        self.workspaces = []
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
            self.workspaces.append(widget)

            self.workspace_states.layout().addWidget(widget)
        h = self.workspace_states.height()
        w = self.width()
        tiling_windows = [
            w for w in monitor_state.workspaces[workspace_index].tiling_windows if w
        ]
        if self.windows != tiling_windows:
            self.deleteDirectChildren(self.container)
            self.windows = tiling_windows.copy()
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
        self.refresh_foreground_window()
        # centering the window
        r = monitor_state.monitor.get_work_rect()
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
        self.hidden_at = time.time()

    def refresh_foreground_window(self):
        """Refresh the foreground window"""
        fg_hwnd = get_foreground_window()
        for i in range(self.container_layout.count()):
            ws_name = self.container_layout.itemAt(i).widget()
            if ws_name.property("handle") == fg_hwnd:
                ws_name.setProperty("active", True)
            else:
                ws_name.setProperty("active", False)
            ws_name.setStyleSheet("")

    def on_mouse_move(self):
        """On system cursor move"""
        logger.debug("on_mouse_move")
        pos = self.workspace_states.mapFromGlobal(QCursor.pos())
        for wsw in self.workspaces:
            wsw.setProperty("hover", wsw.geometry().contains(pos))
            wsw.setStyleSheet("")

    def on_mouse_up(self):
        """On system mouse button up"""
        logger.debug("on_mouse_up")
        if self.isHidden():
            return
        sys_pos = QCursor.pos()
        pos = self.workspace_states.mapFromGlobal(sys_pos)
        for i, wsw in enumerate(self.workspaces):
            if wsw.geometry().contains(pos):
                self.on_move_to_workspace.emit(i)
                return
        if not self.geometry().contains(sys_pos):
            self.hide_windows_splash()

    # def _register_shellhook(self):
    #     user32 = WinDLL("user32", use_last_error=True)
    #     self.shellhook_msgid = user32.RegisterWindowMessageW("SHELLHOOK")
    #     if not user32.RegisterShellHookWindow(self.winId()):
    #         raise WinError(get_last_error())

    # def nativeEvent(self, eventType: QByteArray | bytes, message: int) -> object:
    #     if eventType == "windows_generic_MSG":
    #         msg = MSG.from_address(int(message))
    #         if msg.message == self.shellhook_msgid:
    #             if msg.wParam == 1:
    #                 self.created_windows.add(msg.hWnd)
    #                 logger.debug("window %s created", msg.hWnd)
    #             elif msg.wParam == 2:
    #                 logger.debug("window %s destroyed", msg.hWnd)
    #             elif msg.wParam == 4:
    #                 logger.debug("window %s activated", msg.hWnd)
    #     return super().nativeEvent(eventType, message)

    # def eventFilter(self, src: QObject, evt: QEvent) -> bool:
    #     logger.debug("obj: %s, evt: %s", src, evt)
    #     super().eventFilter(src, evt)

    # def event(self, evt: QEvent) -> bool:
    #     logger.debug("evt: %s", evt)
    #     super().event(evt)


if __name__ == "__main__":
    import signal

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    # logger.info(QRect(159, 9, 143, 82).contains(QPoint(295, 80)))
    # exit()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Splash()
    # splash.show()
    app.exec()
