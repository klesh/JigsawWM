from enum import Enum
from subprocess import PIPE, Popen
from threading import Lock
from typing import List, Optional, TextIO


class ServiceStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"


class ServiceItem:
    name: str
    desc: str
    args: List[str]
    log_path: str
    autostart: bool
    append_only: bool
    _process: Popen = None
    _log_file: TextIO = None
    _lock: Lock

    def __init__(
        self, name, args, log_path=None, desc=None, autostart=True, append_only=False
    ):
        self.name = name
        self.desc = desc
        self.args = args
        self.log_path = log_path
        self.autostart = autostart
        self.append_only = append_only
        self._lock = Lock()

    @property
    def status(self) -> ServiceStatus:
        with self._lock:
            if self._process is None:
                return ServiceStatus.STOPPED
            if self._process.poll() is None:
                return ServiceStatus.RUNNING

    def start(self):
        with self._lock:
            if self._process is not None:
                raise ValueError(f"Service {self.name} is already running")
            log_file = PIPE
            if self.log_path:
                log_file = open(self.log_path, "a+" if self.append_only else "w+")
                self._log_file = log_file
            self._process = Popen(
                self.args, stdout=log_file, stdin=log_file, shell=True
            )

    @property
    def status_text(self) -> str:
        return "running" if self.status == ServiceStatus.RUNNING else "stopped"

    def stop(self):
        with self._lock:
            if self._process is None:
                return
            Popen("TASKKILL /F /PID {pid} /T".format(pid=self._process.pid))
            self._process = None
            if self._log_file:
                self._log_file.close()
            self._log_file = None

    def restart(self):
        self.stop()
        self.start()

    def toggle(self):
        if self.status == ServiceStatus.STOPPED:
            self.start()
        else:
            self.stop()


class ServiceManager:
    """Simple service manager to help you run programs as a service, especially
    helpful for console software like `syncthing`."""

    _services: List[ServiceItem]
    _lock: Lock

    def __init__(self):
        self._services = []
        self._lock = Lock()

    def find_by_name(self, name: str) -> Optional[ServiceItem]:
        for service in self._services:
            if service.name == name:
                return service

    def register(self, service: ServiceItem):
        with self._lock:
            if self.find_by_name(service.name):
                raise ValueError(f"Service {service.name} already exists")
            self._services.append(service)

    def start(self):
        with self._lock:
            for service in self._services:
                if service.autostart:
                    service.restart()

    def stop(self):
        with self._lock:
            for service in self._services:
                service.stop()

    def get_all(self) -> List[ServiceItem]:
        with self._lock:
            return self._services.copy()
