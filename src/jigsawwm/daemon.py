"""Daemon is the core of JigsawWM, it provides a way to run background services and tasks"""
import abc
import logging
import os
import signal
import multiprocessing.pool
from subprocess import PIPE, Popen
from threading import Lock, Thread, Event
from typing import Callable, List, Sequence, TextIO, Union, Iterator

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from jigsawwm import ui

# support for Ctrl+C in console
signal.signal(signal.SIGINT, signal.SIG_DFL)

logger = logging.getLogger(__name__)


class Job(abc.ABC):
    """Job is the fundamental building block of the Daemon, represent a Unit
    of Automation.

    .. code-block::
                        Job
                        /  \
            Service(wm)     Task(daily_routine: open websites, workday_routine: launch thunderbird, im)
                /
        ProcessService(syncthing)
    """

    autorun = True

    @property
    @abc.abstractmethod
    def name(self):
        """Name of the job"""

    @property
    @abc.abstractmethod
    def text(self):
        """Text to be displayed in the traymenu"""

    @abc.abstractmethod
    def launch(self):
        """Launch the job"""

    def stop(self):
        """Stop the job"""


class Service(Job):
    """Service is a kind of Job represents the longlived automation.
    users register arbitrary service to the Daemon and turn them on or off as they pleased
    """

    @property
    @abc.abstractmethod
    def is_running(self) -> bool:
        """Check if the service is running"""

    @abc.abstractmethod
    def start(self):
        """Start the service"""

    @abc.abstractmethod
    def stop(self):
        pass

    def launch(self):
        self.start()

    def toggle(self):
        """Toggle the service"""
        if self.is_running:
            self.stop()
        else:
            self.start()

    def restart(self):
        """Restart the service"""
        self.stop()
        self.start()

    @property
    def text(self):
        status = "running" if self.is_running else "stopped"
        return f"[{status}] {self.name}"


class ThreadedService(Service):
    """ThreadedService is a kind of specialized Service that run a function in the background"""
    interval_sec = 60

    def __init__(self):
        self._thread = None
        self._stop_flag = Event()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            raise ValueError(f"Service {self.name} is already running")
        self._thread = Thread(target=self.run, daemon=True)
        self._stop_flag.clear()
        self._thread.start()

    def run(self):
        """Run the service"""
        while not self._stop_flag.wait(self.interval_sec):
            self.loop()

    @abc.abstractmethod
    def loop(self):
        """The main loop of the service"""

    def stop(self):
        if not self.is_running:
            return
        thread, self._thread = self._thread, None
        self._stop_flag.set()
        thread.join()


class ProcessService(Service):
    """ProcessService is a kind of specialized Service that run a CLI program in the
    background"""

    log_path: str
    log_append_only: bool = False
    _process: Popen = None
    _log_file: TextIO = None
    _lock: Lock

    def __init__(self):
        self._lock = Lock()

    @property
    @abc.abstractmethod
    def args(self) -> List[str]:
        """CLI arguments to start the program"""
        pass

    @property
    def is_running(self) -> bool:
        with self._lock:
            if self._process is None:
                return False
            if self._process.poll() is None:
                return True
        return False

    def start(self):
        """Start the program in the background"""
        with self._lock:
            if self._process is not None:
                raise ValueError(f"Service {self.name} is already running")
            log_file = PIPE
            if self.log_path:
                log_file = open(
                    self.log_path,
                     "a+" if self.log_append_only else "w+",
                     encoding="utf-8"
                )
                self._log_file = log_file
            self._process = Popen(
                self.args, stdout=log_file, stdin=log_file, shell=True
            )

    def stop(self):
        """Stop the program"""
        with self._lock:
            if self._process is None:
                return
            Popen(f"TASKKILL /F /PID {self._process.pid} /T")
            self._process = None
            if self._log_file:
                self._log_file.close()
            self._log_file = None


class Task(Job):
    """Task is a shortlived automation in constrast to Service"""
    pool = multiprocessing.pool.ThreadPool()

    def condition(self) -> bool:
        """Check if the task should be launched"""
        return True

    @abc.abstractmethod
    def run(self) -> bool:
        """Run the task"""

    def launch(self):
        if self.condition():
            self.launch_anyway()

    def launch_anyway(self):
        """Launch the task without checking the condition"""
        self.pool.apply_async(self.run)

    @property
    def text(self):
        return self.name


class ServiceMenu:
    """ServiceMenu is a kind of Service that has submenus"""

    @abc.abstractmethod
    def service_menu_items(self) -> Iterator[Union[QMenu, QAction]]:
        """Return the submenu items"""

class Daemon:
    """JigsawWM Daemon serivce, you must inherite this class and override the `setup` function
    to configurate the Manager.
    """

    trayicon: QSystemTrayIcon = None
    traymenu: QMenu = None
    jobs: Sequence[Job] = []

    def __init__(self):
        script_dir = os.path.dirname(__file__)
        icon_path = os.path.join(script_dir, "assets", "logo.png")
        self.icon = QIcon(icon_path)
        self.create_trayicon()

    def create_trayicon(self):
        """Start trayicon"""
        # to prevent menu item being garbage collected
        self.menuitems = []

        self.trayicon = QSystemTrayIcon(self.icon)
        self.trayicon.setToolTip("JigsawWM")
        self.traymenu = QMenu()
        self.trayicon.setContextMenu(self.traymenu)
        # self.trayicon.activated.connect(self.update_traymenu)
        self.trayicon.activated.connect(self.update_traymenu)
        self.update_traymenu()
        self.trayicon.show()

    def update_traymenu(self):
        """Update traymenu"""
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
                if isinstance(job, ServiceMenu):
                    submenu = QMenu()
                    submenu.setTitle(job.text)
                    act.setText("Enable")
                    submenu.addAction(act)
                    self.traymenu.addMenu(submenu)
                    self.menuitems.append(submenu)
                    if job.is_running:
                        submenu.addSeparator()
                        for service_menu in job.service_menu_items():
                            if isinstance(service_menu, QAction):
                                submenu.addAction(service_menu)
                            else:
                                submenu.addMenu(service_menu)
                            self.menuitems.append(service_menu)
                else:
                    act.setText(job.text)
                    self.traymenu.addAction(act)
        self.traymenu.addSeparator()
        # quit
        quit_act = QAction("&Quit")
        quit_act.triggered.connect(self.stop)
        self.menuitems.append(quit_act)
        self.traymenu.addAction(quit_act)

    def stop(self):
        """Stop daemon service"""
        logger.info("stopping daemon")
        for job in self.jobs:
            job.stop()
        ui.app.quit()
        signal.raise_signal(signal.SIGINT)

    def register(self, job: Callable[[], Job]):
        """Register a job to the daemon service"""
        logger.info("registering %s", job.name)
        job: Job = job()
        if job.autorun:
            logger.info("autorun %s", job.name)
            job.launch()
        self.jobs.append(job)

    def message_loop(self):
        """Start message loop"""
        logger.info("start message loop")
        self.create_trayicon()
        ui.app.exec()


if os.environ.get("DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
instance = Daemon()
register = instance.register
message_loop = instance.message_loop
stop = instance.stop
