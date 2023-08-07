import sys

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

if __name__ == "__main__":
    for s in app.screens():
        print(s.name(), s.geometry())
    # app.exec()
