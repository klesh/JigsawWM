"""
A cache to cache Window instances based on HWND values so that the same Window instance can be
resued between different calls to the same HWND value
"""

from dataclasses import dataclass
from typing import Set, Optional, Callable, Iterator
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

    def _create(self, key: HWND) -> Window:
        """Create a window for the cache based on the HWND value"""
        w = Window(key)
        return w

    def _created(self, val: Window):
        """A callback when a new object is created"""
        if val.parent_handle:
            val.parent = self.get_window(val.parent_handle)
        if self.created:
            return self.created(val) or val

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
            return (w.is_visible or w.off) and w.manageable

        return filter_windows(check)

    def detect_window_changes(self) -> WindowsChange:
        """Detect changes since the previous detection"""
        changed, new_keys, removed_keys = self.detect_changes()
        if changed:
            self.windows = set(map(self.get_window, self.previous_keys))
        removed_windows = set(map(self.get_window, removed_keys))
        new_windows = set(map(self.get_window, new_keys))
        for w in removed_windows:
            if w.parent:
                w.parent.manageable_children.remove(w)
        for w in new_windows:
            if w.parent:
                w.parent.manageable_children.add(w)
        return WindowsChange(
            changed,
            new_windows,
            removed_windows,
        )

    def get_invisible_windows(self) -> Iterator[Window]:
        """Get all invisible manageable windows"""
        for w in self.cache.values():
            if w.manageable and not w.is_visible:
                yield w

    def foreground_window(self) -> Optional[Window]:
        """Get the current foreground window"""
        return self.get_window(get_foreground_window())


if __name__ == "__main__":
    window_detector = WindowDetector()
    window_detector.detect_window_changes()
    print(list(window_detector.get_invisible_windows()))
