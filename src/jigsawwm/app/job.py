"""Defines basic interfaces between daemon and services"""

import abc
import logging
from subprocess import PIPE, Popen
from threading import Lock, Thread, Event
from concurrent.futures import ThreadPoolExecutor
from typing import List, TextIO, Union, Iterator

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


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

    def shutdown(self):
        """System shutting down"""


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
        """Stop the service"""

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

    _name: str
    args: List[str]
    log_path: str
    log_append_only: bool = False
    _process: Popen = None
    _log_file: TextIO = None
    _lock: Lock

    def __init__(self, name: str, args: List[str], log_path: str) -> None:
        super().__init__()
        self._name = name
        self.args = args
        self.log_path = log_path
        self._lock = Lock()

    @property
    def name(self) -> str:
        return self._name

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
                raise ValueError(f"Service {self._name} is already running")
            log_file = PIPE
            if self.log_path:
                log_file = open(
                    self.log_path,
                    "a+" if self.log_append_only else "w+",
                    encoding="utf-8",
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

    executor = ThreadPoolExecutor()

    def condition(self) -> bool:
        """Check if the task should be launched"""
        return True

    @abc.abstractmethod
    def run(self) -> bool:
        """Run the task"""

    def launch(self):
        self.executor.submit(self.check_launch)

    def check_launch(self):
        """Check the condition and launch the task"""
        if self.condition():
            self.launch_anyway()

    def launch_anyway(self):
        """Launch the task without checking the condition"""
        self.executor.submit(self.run)

    @property
    def text(self):
        return self.name


class TrayIconTriggerred:
    """TrayIconTriggerred is a kind of Service that has submenu items"""

    @abc.abstractmethod
    def trayicon_triggerred(self) -> Iterator[Union[QMenu, QAction]]:
        """Return the submenu items"""
