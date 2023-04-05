from enum import Enum
from subprocess import PIPE, Popen
from threading import Lock
from typing import List, Optional, TextIO


class ServiceStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"


class ServiceEntry:
    """ServiceEntry represents a service, holds the meta data and running state

    :param str name: name of the service
    :param str desc: description
    :param List[str] args: the arguments used to launch the process.
    :param bool autostart: start the service automatically
    :param str log_path: log file path
    :param bool log_append_only: append log to the file or overwrite
    """

    name: str
    desc: str
    args: List[str]
    autostart: bool
    log_path: str
    log_append_only: bool
    _process: Popen = None
    _log_file: TextIO = None
    _lock: Lock

    def __init__(
        self,
        name,
        args,
        log_path=None,
        log_append_only=False,
        desc=None,
        autostart=True,
    ):
        self.name = name
        self.desc = desc
        self.args = args
        self.log_path = log_path
        self.autostart = autostart
        self.log_append_only = log_append_only
        self._lock = Lock()

    @property
    def status(self) -> ServiceStatus:
        """Retrieves the status of the service"""
        with self._lock:
            if self._process is None:
                return ServiceStatus.STOPPED
            if self._process.poll() is None:
                return ServiceStatus.RUNNING
        return ServiceStatus.STOPPED

    def start(self):
        """Start the service"""
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

    @property
    def status_text(self) -> str:
        """Retrieves the status of the service in plaintext format"""
        return "running" if self.status == ServiceStatus.RUNNING else "stopped"

    def stop(self):
        """Stop the service"""
        with self._lock:
            if self._process is None:
                return
            Popen("TASKKILL /F /PID {pid} /T".format(pid=self._process.pid))
            self._process = None
            if self._log_file:
                self._log_file.close()
            self._log_file = None

    def restart(self):
        """Restart the service"""
        self.stop()
        self.start()

    def toggle(self):
        """Start or stop the service"""
        if self.status == ServiceStatus.STOPPED:
            self.start()
        else:
            self.stop()


class ServiceManager:
    """Simple service manager to help you run programs as a service, especially
    helpful for console software like `syncthing`."""

    _services: List[ServiceEntry]
    _lock: Lock

    def __init__(self):
        self._services = []
        self._lock = Lock()

    def find_by_name(self, name: str) -> Optional[ServiceEntry]:
        """Find a service by name, return None if not found"""
        for service in self._services:
            if service.name == name:
                return service

    def register(self, service: ServiceEntry):
        """Register a new service"""
        with self._lock:
            if self.find_by_name(service.name):
                raise ValueError(f"Service {service.name} already exists")
            self._services.append(service)

    def start(self):
        """Starts all services that have autostart enabled"""
        with self._lock:
            for service in self._services:
                if service.autostart:
                    service.restart()

    def stop(self):
        """Stops all running services"""
        with self._lock:
            for service in self._services:
                service.stop()

    def get_all(self) -> List[ServiceEntry]:
        """Retrieves a copy of all registered services"""
        with self._lock:
            return self._services.copy()
