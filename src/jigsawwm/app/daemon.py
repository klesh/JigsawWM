"""Daemon is the core of JigsawWM, it provides a way to run background services and tasks"""

import logging
import os
import signal
import sys
import traceback
from typing import Sequence

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from jigsawwm import ui
from jigsawwm.jmk.jmk_service import JmkService
from jigsawwm.w32.vk import Vk
from jigsawwm.wm.wm_service import WmService

from .job import Job, Service, Task, TrayIconTriggerred

# support for Ctrl+C in console
signal.signal(signal.SIGINT, signal.SIG_DFL)


logFormatter = logging.Formatter(
    "%(asctime)s [%(name)s] [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
)
logging_path = os.getenv("JWM_LOGGING_PATH")
if not logging_path:
    logging_path = os.path.join(os.getenv("LOCALAPPDATA"), "jigsawwm", "jigsawwm.log")
logging_dir = os.path.dirname(logging_path)
if not os.path.exists(logging_dir):
    os.mkdir(logging_dir)
fileHandler = logging.FileHandler(logging_path, mode="w+", encoding="utf-8")
fileHandler.setFormatter(logFormatter)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)

rootLogger = logging.getLogger()
rootLogger.addHandler(fileHandler)
rootLogger.addHandler(consoleHandler)

debugging = os.environ.get("DEBUG_JIGSAWWM")
if debugging:
    rootLogger.setLevel(logging.DEBUG)
    if debugging != "*":

        loggers = set(debugging.split(","))

        def f(record: logging.LogRecord) -> bool:
            return (
                any(record.name.startswith(logger) for logger in loggers)
                or record.levelno >= logging.INFO
            )

        consoleHandler.addFilter(f)
        fileHandler.addFilter(f)
else:
    rootLogger.setLevel(logging.INFO)


logger = logging.getLogger(__name__)


class Daemon:
    """JigsawWM Daemon: A singleton class that manages the tray icon and is responsible for starting and stopping jobs."""

    sysexcepthook: callable = None
    trayicon: QSystemTrayIcon = None
    traymenu: QMenu = None
    quit_act: QAction
    jobs: Sequence[Job] = []
    jmk: JmkService
    wm: WmService

    def __init__(self):
        logger.info("Daemon initializing")
        script_dir = os.path.dirname(__file__)
        icon_path = os.path.join(script_dir, "..", "assets", "logo.png")
        self.icon = QIcon(icon_path)
        self.create_trayicon()
        self.jmk = JmkService()
        self.wm = WmService(self.jmk)
        self.register(self.jmk)
        self.register(self.wm)

    def start(self):
        """Start the Daemon"""
        logger.info("Daemon starting")
        self.sysexcepthook = sys.excepthook
        sys.excepthook = self.on_uncaught_exception
        skip_tasks = self.jmk.sysout.state.get(Vk.LSHIFT)
        logger.info("skip tasks: %s", skip_tasks)
        for job in self.jobs:
            if job.autorun:
                if isinstance(job, Task) and skip_tasks:
                    logger.info("skip autorun tasks %s", job.name)
                else:
                    logger.info("autorun %s", job.name)
                    job.launch()
        if skip_tasks:
            self.trayicon.showMessage(
                "JigsawWM",
                "skip autorun tasks",
                QSystemTrayIcon.MessageIcon.Information,
            )
        self.message_loop()

    def stop(self):
        """Stop the Daemon"""
        logger.info("Daemon stopping")
        sys.excepthook = self.sysexcepthook
        self.sysexcepthook = None
        for job in self.jobs:
            job.stop()
            job.shutdown()
        ui.app.quit()
        signal.raise_signal(signal.SIGINT)

    def on_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """Function handling uncaught exceptions.
        It is triggered each time an uncaught exception occurs.
        """
        if issubclass(exc_type, KeyboardInterrupt):
            # ignore keyboard interrupt to support console applications
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        else:
            exc_info = (exc_type, exc_value, exc_traceback)
            log_msg = "\n".join(
                [
                    "".join(traceback.format_tb(exc_traceback)),
                    f"{exc_type.__name__}: {exc_value}",
                ]
            )
            logger.critical("Uncaught exception:\n %s", log_msg, exc_info=exc_info)
            self.trayicon.showMessage(
                "JigsawWM,", log_msg, icon=QSystemTrayIcon.MessageIcon.Critical
            )

    def create_trayicon(self):
        """Start trayicon"""
        # to prevent menu item being garbage collected
        self.trayicon = QSystemTrayIcon(self.icon)
        self.trayicon.setToolTip("JigsawWM")
        # permant menu items
        self.quit_act = QAction("&Quit")
        self.quit_act.triggered.connect(self.stop)
        self.traymenu = QMenu()
        self.menuitems = []
        self.refresh_traymenu()
        self.trayicon.setContextMenu(self.traymenu)
        # self.trayicon.activated.connect(self.update_traymenu)
        self.trayicon.activated.connect(self.trayicon_activated)
        self.trayicon.show()

    def refresh_traymenu(self):
        """Refresh traymenu"""
        # quit
        self.traymenu.clear()
        self.menuitems.clear()
        # tasks
        for job in self.jobs:
            if isinstance(job, Task):
                act = QAction(job.text)
                act.triggered.connect(job.launch_anyway)
                self.traymenu.addAction(act)
                self.menuitems.append(act)
        self.traymenu.addSeparator()
        # services
        for job in self.jobs:
            if isinstance(job, Service):
                act = QAction()
                act.setCheckable(True)
                act.setChecked(job.is_running)
                act.triggered.connect(job.toggle)
                self.menuitems.append(act)
                act.setText(job.text)
                self.traymenu.addAction(act)
        self.traymenu.addSeparator()
        self.traymenu.addAction(self.quit_act)
        self.menuitems.append(self.quit_act)

    def trayicon_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Update traymenu"""
        logger.info("trayicon activated, reason: %s", reason)
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            for job in self.jobs:
                if isinstance(job, TrayIconTriggerred):
                    try:
                        job.trayicon_triggerred()
                    except StopIteration:
                        return
                    except:  # pylint: disable=bare-except
                        logger.exception(
                            "trayicon_triggerred", exc_info=True, stack_info=True
                        )
            return
        self.refresh_traymenu()

    def register(self, job: Job):
        """Register a job to the daemon service"""
        logger.info("registering %s", job.name)
        self.jobs.append(job)
        self.refresh_traymenu()

    def message_loop(self):
        """Start message loop"""
        logger.info("start message loop")
        self.create_trayicon()
        ui.app.exec()
