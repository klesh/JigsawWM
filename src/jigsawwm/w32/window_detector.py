"""
A cache to cache Window instances based on HWND values so that the same Window instance can be
resued between different calls to the same HWND value
"""

from dataclasses import dataclass
from typing import Set, Optional
from jigsawwm.objectcache import ObjectCache, ChangeDetector
from .window import HWND, Window, filter_windows, get_foreground_window


@dataclass
class WindowsChange:
    """A dataclass to hold the changes of windows"""

    changed: bool
    new_windows: Set[Window]
    removed_windows: Set[Window]


class WindowDetector(ObjectCache, ChangeDetector):
    """A cache of all windows"""

    def __init__(self, vacuum_interval: int = 3600):
        ObjectCache.__init__(self, vacuum_interval=vacuum_interval)
        ChangeDetector.__init__(self)

    def create(self, key: HWND) -> Window:
        """Create a window for the cache based on the HWND value"""
        return Window(key)

    def is_valid(self, val: Window) -> bool:
        """Check if the window is still valid"""
        return val.exists()

    def get_window(self, hwnd: HWND) -> Window:
        """Retrieve a window from the cache"""
        return self.get(hwnd)

    def current_keys(self) -> set:
        """Retrieve all interested keys at the moment"""
        return filter_windows(lambda hwnd: self.get_window(hwnd).manageable)

    def detect_window_changes(self) -> WindowsChange:
        """Detect changes since the previous detection"""
        changed, new_keys, removed_keys = self.detect_changes()
        return WindowsChange(
            changed,
            set(map(self.get_window, new_keys)),
            set(map(self.get_window, removed_keys)),
        )

    def foreground_window(self) -> Optional[Window]:
        """Get the current foreground window"""
        return self.get_window(get_foreground_window())

    def minimize_active_window(self):
        """Minize active window"""
        w = self.foreground_window()
        if w:
            w.minimize()

    def toggle_maximize_active_window(self):
        """Maximize/Unmaximize active window"""
        w = self.foreground_window()
        if w:
            w.toggle_maximize()
