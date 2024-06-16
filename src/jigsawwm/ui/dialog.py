"""Dialog class for creating custom dialog with shadow effect"""
# pylint: disable=invalid-name
import os
import typing

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QCursor, QImage, QKeyEvent, QPixmap, QScreen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Dialog(QDialog):
    """Dialog class for creating custom dialog with shadow effect"""
    radius: int = 10

    def __init__(
        self,
        radius: int = 15,
        theme: str = "dark",
        spacer: bool = True,
    ):
        super().__init__()
        self.radius = radius
        self.theme = theme

        # window style
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.Tool)
        self.setWindowFlag(Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setModal(True)

        # create common widgets
        # self.central = QWidget(self)
        # self.central.setObjectName("central")
        # self.central_layout = QVBoxLayout(self.central)
        # self.setCentralWidget(self.central)
        self.central = self
        self.central_layout = QVBoxLayout(self)

        self.root = QWidget(self.central)
        self.root.setObjectName("root")
        self.root.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum if spacer else QSizePolicy.Policy.Expanding,
        )
        self.root_layout = QVBoxLayout(self.root)
        self.container = QFrame(self.root)
        self.container.setObjectName("container")
        self.container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.container_layout = QVBoxLayout(self.container)
        self.root_layout.addWidget(self.container)
        self.central_layout.addWidget(self.root)
        if spacer:
            self.spacer = QWidget(self)
            self.spacer.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self.central_layout.addWidget(self.spacer)

        # setup common widgets
        self.central_layout.setContentsMargins(
            self.radius, self.radius, self.radius, self.radius
        )
        self.root_layout.setContentsMargins(0, self.radius, 0, self.radius)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        # drop shadow
        self.root_shadow = QGraphicsDropShadowEffect()
        self.root_shadow.setBlurRadius(self.radius)
        self.root_shadow.setColor(QColor(0, 0, 0, 100))
        self.root.setGraphicsEffect(self.root_shadow)

        # load theme
        with open(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "assets",
                f"{self.theme}.css",
            ),
            "r",
            encoding="utf-8",
        ) as f:
            self.setStyleSheet(f.read())

    def screenFromCursor(self) -> typing.Tuple[QScreen, QPoint]:
        """get the screen from the cursor position"""
        pos = QCursor.pos()
        app = QApplication.instance()
        for screen in app.screens():
            if screen.geometry().contains(pos):
                return screen

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """handle key press event"""
        if a0.key() == Qt.Key.Key_Escape:
            self.onEscPresssed()
            return
        return super().keyPressEvent(a0)

    def onEscPresssed(self) -> None:
        """handle escape key pressed event"""
        self.hide()

    @staticmethod
    def deleteDirectChildren(
        container: QWidget,
        keep: typing.Optional[typing.Callable[[QWidget], bool]] = None,
    ):
        """delete all direct children of the QWidget"""
        for w in container.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            if keep and keep(w):
                continue
            w.deleteLater()

    def create_row_widget(self, width: int, text: str, icon: QImage = None) -> QWidget:
        """create a row QtWidget"""
        frame_widget = QFrame()
        frame_widget.setObjectName("menuitem")
        frame_layout = QHBoxLayout(frame_widget)
        frame_layout.setContentsMargins(5, 2, 5, 2)
        frame_layout.setSpacing(10)
        width -= 10
        # icon
        icon_widget = QLabel(frame_widget)
        icon_widget.setObjectName("icon")
        icon_widget.setFixedSize(32, 32)
        width -= 32
        icon_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        frame_layout.addWidget(icon_widget, stretch=0)
        if icon:
            icon_widget.setPixmap(QPixmap.fromImage(icon))
            icon_widget.setScaledContents(True)
            icon_widget.setAlignment(Qt.AlignmentFlag.AlignTop)
        # text
        content_widget = QLabel(frame_widget)
        content_widget.setObjectName("content")
        content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        content_widget.setText(text)
        frame_layout.addWidget(content_widget)
        return frame_widget
