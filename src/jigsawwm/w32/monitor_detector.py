"""
A cache to cache Monitor instances based on HMONITOR values so that the same monitor instance can be
resued between different calls to the same HMONITOR value
"""

from dataclasses import dataclass
from typing import Set, List, Optional
from jigsawwm.objectcache import ObjectCache, ChangeDetector
from .monitor import (
    HMONITOR,
    Monitor,
    enum_display_monitors,
    monitor_from_point,
    monitor_from_cursor,
    monitor_from_window,
    Rect,
)


@dataclass
class MonitorsChange:
    """A dataclass to hold the changes of monitors"""

    changed: bool
    new_monitors: Set[Monitor]
    removed_monitors: Set[Monitor]


class MonitorDetector(ObjectCache, ChangeDetector):
    """A cache of all monitors"""

    monitors: List[Monitor]
    full_rect: Rect

    def __init__(self, vacuum_interval: int = 3600):
        ObjectCache.__init__(self, vacuum_interval=vacuum_interval)
        ChangeDetector.__init__(self)
        self.monitors = []

    def _create(self, key: HMONITOR) -> Monitor:
        """Create a monitor for the cache based on the HMONITOR value"""
        return Monitor(key)

    def is_valid(self, val: Monitor) -> bool:
        """Check if the monitor is still valid"""
        return val.exists()

    def get_monitor(self, hmon: HMONITOR) -> Monitor:
        """Retrieve a monitor from the cache"""
        return self.get(hmon)

    def current_keys(self) -> set:
        """Retrieve all interested keys at the moment"""
        return enum_display_monitors()

    def detect_monitor_changes(self) -> MonitorsChange:
        """Detect changes since the previous detection"""
        changed, new_keys, removed_keys = self.detect_changes()
        if changed:
            self.monitors = sorted(
                map(self.get_monitor, self.previous_keys),
                # key=lambda m: m.get_monitor_central(),
                key=lambda m: m.name,
            )
            self.refresh_full_rect()
        return MonitorsChange(
            changed,
            set(map(self.get_monitor, new_keys)),
            set(map(self.get_monitor, removed_keys)),
        )

    def monitor_from_point(self, x: int, y: int) -> Monitor:
        """Retrieves monitor from X/Y coordinates"""
        return self.get_monitor(monitor_from_point(x, y))

    def monitor_from_cursor(self) -> Monitor:
        """Retrieves monitor from the cursor"""
        return self.get_monitor(monitor_from_cursor()) or self.monitors[0]

    def monitor_from_window(self, hwnd: int) -> Optional[Monitor]:
        """Retrieves monitor from a window"""
        hmon = monitor_from_window(hwnd)
        if not hmon:
            return None
            # return self.monitor_from_cursor()
        return self.get_monitor(hmon)

    def refresh_full_rect(self) -> Rect:
        """Refresh the full rect of all monitors"""
        rects = [m.get_rect() for m in self.monitors]
        left = min(r.left for r in rects)
        top = min(r.top for r in rects)
        right = max(r.right for r in rects)
        bottom = max(r.bottom for r in rects)
        self.full_rect = Rect(left, top, right, bottom)
        return self.full_rect
