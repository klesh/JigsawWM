"""
A cache to cache Window instances based on HWND values so that the same Window instance can be
resued between different calls to the same HWND value
"""

from dataclasses import dataclass
from typing import Set, Optional, Callable
from jigsawwm.objectcache import ObjectCache, ChangeDetector
from .window import HWND, Window, filter_windows, get_foreground_window
from .monitor import get_cursor_pos


@dataclass
class WindowsChange:
    """A dataclass to hold the changes of windows"""

    changed: bool
    new_windows: Set[Window]
    removed_windows: Set[Window]


class WindowDetector(ObjectCache, ChangeDetector):
    """A cache of all windows"""

    windows: Set[Window]
    created: Optional[Callable[[Window], None]] = None

    def __init__(
        self,
        created: Optional[Callable[[Window], None]] = None,
        vacuum_interval: int = 3600,
    ):
        ObjectCache.__init__(self, vacuum_interval=vacuum_interval)
        ChangeDetector.__init__(self)
        self.windows = set()
        self.created = created

    def create(self, key: HWND) -> Window:
        """Create a window for the cache based on the HWND value"""
        w = Window(key)
        if self.created:
            return self.created(w) or w
        return w

    def is_valid(self, val: Window) -> bool:
        """Check if the window is still valid"""
        return val.exists()

    def get_window(self, hwnd: HWND) -> Window:
        """Retrieve a window from the cache"""
        return self.get(hwnd)

    def current_keys(self) -> set:
        """Retrieve all interested keys at the moment"""

        def check(hwnd: HWND):
            w = self.get_window(hwnd)
            return w.is_visible and w.manageable

        return filter_windows(check)

    def detect_window_changes(self) -> WindowsChange:
        """Detect changes since the previous detection"""
        changed, new_keys, removed_keys = self.detect_changes()
        if changed:
            self.windows = set(map(self.get_window, self.previous_keys))
        return WindowsChange(
            changed,
            set(map(self.get_window, new_keys)),
            set(map(self.get_window, removed_keys)),
        )

    def foreground_window(self) -> Optional[Window]:
        """Get the current foreground window"""
        return self.get_window(get_foreground_window())

    def window_restricted_at_cursor(self) -> Optional[Window]:
        """Get the window under the cursor"""
        pos = get_cursor_pos()
        for w in self.windows:
            if w.restricted_rect and w.restricted_rect.contains(pos.x, pos.y):
                return w


if __name__ == "__main__":
    window_detector = WindowDetector()
    print(window_detector.detect_window_changes())
