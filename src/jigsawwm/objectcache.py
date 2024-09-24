"""
A cache to cache Window instances based on HWND values so that the same Window instance can be
resued between different calls to the same HWND value
"""

import abc
from typing import Dict, Any, Tuple
from threading import Lock
from .worker import ThreadWorker


class ObjectCache(ThreadWorker):
    """A cache of all windows"""

    _lock: Lock
    cache: Dict[Any, Any]
    vacuum_interval: int

    def __init__(
        self,
        vacuum_interval: int = 3600,
    ):
        self.cache = {}
        self.vacuum_interval = vacuum_interval
        self._lock = Lock()

    def start(self):
        """Start the vacuum thread"""
        self.start_worker()
        self.periodic_call(self.vacuum_interval, self.vaccum)

    def stop(self):
        """Stop the vacuum thread"""
        self.stop_worker()

    def get(self, key: Any) -> Any:
        """Get a object from the cache"""
        if key not in self.cache:
            created = False
            with self._lock:
                if key not in self.cache:
                    self.cache[key] = self._create(key)
                    created = True
            if created:
                self._created(self.cache[key])
        return self.cache[key]

    @abc.abstractmethod
    def _create(self, key: Any) -> Any:
        """Create a object for the cache"""

    def _created(self, val: Any):
        """A callback when a new object is created"""

    def vaccum(self):
        """Remove all invalid windows from the cache"""
        with self._lock:
            self.cache = {
                key: val for key, val in self.cache.items() if self.is_valid(val)
            }

    @abc.abstractmethod
    def is_valid(self, val: Any) -> bool:
        """Check if the object is still valid"""


class ChangeDetector:
    """A class to detect changes in a set of keys"""

    previous_keys: set = None

    def detect_changes(self) -> Tuple[bool, set, set]:
        """Detect changes since the previous detection"""
        current_keys = self.current_keys()
        if self.previous_keys is None:
            self.previous_keys = current_keys
            return True, current_keys, set()
        new_keys = current_keys - self.previous_keys
        removed_keys = self.previous_keys - current_keys
        self.previous_keys = current_keys
        return new_keys or removed_keys, new_keys, removed_keys

    @abc.abstractmethod
    def current_keys(self) -> set:
        """Retrieve all interested keys at the moment"""
