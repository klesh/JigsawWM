"""This module provides a QApplication instance and a custom exception hook for handling uncaught exceptions."""

import sys

from PySide6 import QtWidgets


app = QtWidgets.QApplication(sys.argv)

# basic logger functionality
# logger = logging.getLogger(__name__)


# def show_exception_box(log_msg):
#     """Checks if a QApplication instance is available and shows a messagebox with the exception message.
#     If unavailable (non-console application), log an additional notice.
#     """
#     # if QtWidgets.QApplication.instance() is not None:
#     errorbox = QtWidgets.QMessageBox()
#     errorbox.setText(f"Oops. An unexpected error occured:\n{log_msg}")
#     errorbox.exec_()
#     # else:
#     #     log.debug("No QApplication instance available.")


# class UncaughtHook(QtCore.QObject):
#     """Custom exception hook class to handle uncaught exceptions."""

#     _exception_caught = QtCore.Signal(object)

#     def __init__(self, *args, **kwargs):
#         super(UncaughtHook, self).__init__(*args, **kwargs)

#         # this registers the exception_hook() function as hook with the Python interpreter
#         sys.excepthook = self.exception_hook

#         # connect signal to execute the message box function always on main thread
#         self._exception_caught.connect(show_exception_box)

#     def exception_hook(self, exc_type, exc_value, exc_traceback):
#         """Function handling uncaught exceptions.
#         It is triggered each time an uncaught exception occurs.
#         """
#         if issubclass(exc_type, KeyboardInterrupt):
#             # ignore keyboard interrupt to support console applications
#             sys.__excepthook__(exc_type, exc_value, exc_traceback)
#         else:
#             exc_info = (exc_type, exc_value, exc_traceback)
#             log_msg = "\n".join(
#                 [
#                     "".join(traceback.format_tb(exc_traceback)),
#                     f"{exc_type.__name__}: {exc_value}",
#                 ]
#             )
#             logger.critical("Uncaught exception:\n %s", log_msg, exc_info=exc_info)

#             # trigger message box show
#             self._exception_caught.emit(log_msg)


# create a global instance of our class to register the hook


# if __name__ == "__main__":
#     import signal

#     qt_exception_hook = UncaughtHook()
#     signal.signal(signal.SIGINT, signal.SIG_DFL)
#     for s in app.screens():
#         print(s.name(), s.geometry())
#     app.screenAdded.connect(lambda s: print("Screen added", s.name(), s.geometry()))
#     app.screenRemoved.connect(lambda s: print("Screen removed", s.name(), s.geometry()))
#     app.exec()
