import logging

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from jigsawwm.w32.window import Window
from jigsawwm.wm import MonitorState

from .app import app
from .dialog import Dialog

logger = logging.getLogger(__name__)


class WindowsSplash(Dialog):
    """The window list splash screen."""

    show_splash = Signal(MonitorState, Window)
    hide_splash = Signal()

    def __init__(self):
        super().__init__()
        self.windows = []
        self.show_splash.connect(self.show_windows_splash)
        self.hide_splash.connect(self.hide)
        logger.debug("WindowsSplash init")

    @Slot(MonitorState, Window)
    def show_windows_splash(self, monitor_state: MonitorState, active_window: Window):
        logger.debug("WindowsSplash show")
        if self.windows != monitor_state.windows:
            self.deleteDirectChildren(self.container)
            self.windows = monitor_state.windows.copy()
            h = 0
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

            if h == 0:
                self.spacer = QLabel("No shortcut available")
                self.spacer.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.spacer.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
                )
                self.container_layout.addWidget(self.spacer)
            r = monitor_state.monitor.get_rect()
            rect = app.screenAt(QPoint(r.left, r.top)).geometry()

            x = rect.x() + (rect.width() - self.width()) // 2
            y = rect.y() + (rect.height() - h) // 2
            self.setGeometry(x, y, self.width(), h)
        for i in range(self.container_layout.count()):
            widget = self.container_layout.itemAt(i).widget()
            if widget.property("handle") == active_window.handle:
                widget.setProperty("active", True)
            else:
                widget.setProperty("active", False)
            widget.setStyleSheet("")
        self.show()


instance = WindowsSplash()
show_windows_splash = instance.show_splash.emit
hide_windows_splash = instance.hide_splash.emit
