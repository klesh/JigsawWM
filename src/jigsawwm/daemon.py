import abc
import logging
import os
import signal
import sys
import traceback
from subprocess import PIPE, Popen
from threading import Lock
from tkinter import messagebox
from typing import Callable, List, Sequence, TextIO

import pystray
from PIL import Image

from jigsawwm import jmk

# support for Ctrl+C in console
signal.signal(signal.SIGINT, signal.SIG_DFL)

logger = logging.getLogger(__name__)


# show exception both CLI/GUI
def handle_exc(exc_type, exc_value, exc_traceback):
    msg = traceback.format_exception(exc_type, exc_value, exc_traceback)
    print(msg, file=sys.stderr)
    messagebox.showerror("JigsawWM", msg)


jmk.handle_exc = handle_exc


class Job(abc.ABC):
    autorun = True

    """Job is the fundamental building block of the Daemon, represent a Unit
    of Automation.

    .. code-block::
                        Job
                        /  \
            Service(wm)     Task(daily_routine: open websites, workday_routine: launch thunderbird, im)
                /
        ProcessService(syncthing)
    """

    @abc.abstractproperty
    def name(self):
        pass

    @abc.abstractproperty
    def text(self):
        pass

    @abc.abstractmethod
    def launch(self):
        pass


class Service(Job):
    """Service is a kind of Job represents the longlived automation.
    users register arbitrary service to the Daemon and turn them on or off as they pleased
    """

    @abc.abstractproperty
    def is_running(self) -> bool:
        pass

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    def launch(self):
        self.start()

    def toggle(self):
        self.stop() if self.is_running else self.start()

    def restart(self):
        self.stop()
        self.start()

    @property
    def text(self):
        status = "running" if self.is_running else "stopped"
        return f"[{status}] {self.name}"


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

    @abc.abstractproperty
    def args(self) -> List[str]:
        pass

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
                log_file = open(self.log_path, "a+" if self.log_append_only else "w+")
                self._log_file = log_file
            self._process = Popen(
                self.args, stdout=log_file, stdin=log_file, shell=True
            )

    def stop(self):
        """Stop the program"""
        with self._lock:
            if self._process is None:
                return
            Popen("TASKKILL /F /PID {pid} /T".format(pid=self._process.pid))
            self._process = None
            if self._log_file:
                self._log_file.close()
            self._log_file = None


class Task(Job):
    """Task is a shortlived automation in constrast to Service"""

    def condition(self) -> bool:
        return True

    @abc.abstractmethod
    def run(self) -> bool:
        pass

    def launch(self):
        if self.condition():
            self.run()

    @property
    def text(self):
        return self.name


class Daemon:
    """JigsawWM Daemon serivce, you must inherite this class and override the `setup` function
    to configurate the Manager.
    """

    trayicon: pystray.Icon = None
    jobs: Sequence[Job] = []

    def __init__(self):
        jmk.handle_exc = handle_exc

    def create_trayicon(self):
        """Start trayicon"""
        script_dir = os.path.dirname(__file__)
        icon_path = os.path.join(script_dir, "assets", "logo.png")
        icon = Image.open(icon_path)

        tray_icon = pystray.Icon(
            "JigsawWM",
            icon=icon,
            menu=pystray.Menu(self.tray_menu_items),
        )
        self.trayicon = tray_icon
        self.trayicon.run()

    def tray_menu_items(self) -> List[pystray.MenuItem]:
        service_menu_items = [
            pystray.MenuItem(
                service.text,
                service.toggle,
            )
            for service in self.jobs
            if isinstance(service, Service)
        ]
        task_menu_items = [
            pystray.MenuItem(
                task.text,
                task.run,
            )
            for task in self.jobs
            if isinstance(task, Task)
        ]
        return [
            *task_menu_items,
            pystray.Menu.SEPARATOR,
            *service_menu_items,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.stop),
        ]

    def stop(self):
        """Stop daemon service"""
        logger.info(f"stopping daemon")
        self.trayicon.stop()
        self.trayicon = None
        signal.raise_signal(signal.SIGINT)

    def register(self, job: Callable[[], Job]):
        logger.info(f"registering {job.name}")
        job: Job = job()
        if job.autorun:
            logger.info(f"autorun {job.name}")
            job.launch()
        self.jobs.append(job)

    def message_loop(self):
        logger.info(f"start message loop")
        self.create_trayicon()


if os.environ.get("DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
instance = Daemon()
register = instance.register
message_loop = instance.message_loop
stop = instance.stop
