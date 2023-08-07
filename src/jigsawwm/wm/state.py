import logging
from typing import Dict, List, Optional, Set

from jigsawwm.tiler.tilers import *
from jigsawwm.w32.monitor import Monitor, get_monitor_from_window
from jigsawwm.w32.window import RECT, Window, get_active_window

from .theme import Theme

logger = logging.getLogger(__name__)


class MonitorState:
    """MonitorState holds variables needed by a Monitor


    :param VirtDeskState virtdesk_state: associated virtual desktop
    :param Monitor monitor: associated system monitor
    :param str theme: the active theme for the monitor in the virtual desktop
    """

    virtdesk_state: "VirtDeskState"
    monitor: Monitor
    theme: Optional[str]
    windows: List[Window]
    last_active_window: Optional[Window] = None

    def __init__(
        self,
        virtdesk_state: "VirtDeskState",
        monitor: Monitor,
        theme: Optional[str] = None,
    ):
        self.virtdesk_state = virtdesk_state
        self.monitor = monitor
        self.theme = theme
        self.windows = []
        self.last_active_window = None
        self.hook_ids = []

    def get_existing_windows(self) -> List[Window]:
        """Retrieves current managed windows"""
        return self.windows

    def sync(self, windows: Set[Window], restrict=False):
        """Synchronize managed windows with given actual windows currently visible and arrange them accordingly

        :param Set[Window] windows: latest visible windows
        :param bool restrict: optional, restrict windows to their specified rect no matter what
        """
        theme = self.virtdesk_state.get_theme(self.theme)
        old_list = self.windows
        new_list = []
        for w in old_list:
            if w not in windows:
                continue
            windows.remove(w)
            if not w.exists():
                continue
            new_list.append(w)
        # and then, prepend or append the new windows
        if theme.new_window_as_master:
            new_list = list(windows) + new_list
        else:
            new_list = new_list + list(windows)
        # skip if there is nothing changed, unless Strict mode is enable
        if new_list == old_list:
            if restrict:
                self.restrict(theme)
            return
        self.windows = new_list
        self.arrange(theme)

    def arrange(self, theme: Optional[Theme] = None):
        """Arrange windows based on the theme

        :param str theme: optional, fallback to theme of the instance
        """
        theme = theme or self.get_theme()
        wr = self.monitor.get_info().rcWork
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self.get_existing_windows()
        i = 0
        gap = theme.gap
        for left, top, right, bottom in theme.layout_tiler(work_area, len(windows)):
            window = windows[i]
            # add gap
            if gap:
                if left == wr.left:
                    left += gap
                if top == wr.top:
                    top += gap
                if right == wr.right:
                    right -= gap
                if bottom == wr.bottom:
                    bottom -= gap
            left += gap
            top += gap
            right -= gap
            bottom -= gap
            rect = RECT(left, top, right, bottom)
            logger.debug("arrange %s %s", window, rect)
            window.set_rect(rect)
            # compensation
            r = window.get_rect()
            b = window.get_extended_frame_bounds()
            compensated_rect = (
                round(left + r.left - b.left),
                round(top + r.top - b.top),
                round(right + r.right - b.right),
                round(bottom + r.bottom - b.bottom),
            )
            window.set_rect(RECT(*compensated_rect))
            i += 1

    def restrict(self, theme: Optional[Theme] = None):
        """Restrict all managed windows to their specified rect"""
        theme = theme or self.get_theme()
        if not theme.strict:
            return
        for window in self.windows:
            window.restrict()


class VirtDeskState:
    """VirtDeskState holds variables needed by a Virtual Desktop

    :param WindowManager manager: associated WindowManager
    :param bytearray desktop_id: virtual desktop id
    """

    desktop_id: bytearray
    managed_windows: Set[Window]
    monitors: Dict[Monitor, MonitorState]
    last_active_window: Optional[Window] = None

    def __init__(self, get_theme: Callable[[str], Theme], desktop_id: bytearray):
        self.desktop_id = desktop_id
        self.managed_windows = set()
        self.monitors = {}
        self.last_active_window = None
        self.get_theme = get_theme

    def get_monitor(self, monitor: Monitor) -> MonitorState:
        """Retrieves the monitor state for the specified monitor in the virtual desktop

        :param Monitor monitor: monitor
        :returns: monitor state
        :rtype: MonitorState
        """
        monitor_state = self.monitors.get(monitor)
        if monitor_state is None:
            monitor_state = MonitorState(self, monitor)
            self.monitors[monitor] = monitor_state
        return monitor_state

    def get_managed_active_window(self) -> Optional[Window]:
        """Retrieves the managed forground window if any"""
        window = get_active_window()
        logger.debug("get_managed_active_window: active window %s", window)
        if window is None:
            return None
        if window not in self.managed_windows:
            logger.debug(
                "get_managed_active_window: active window is NOT managed %s", window
            )
            return None
        return window

    def get_last_managed_active_window(self) -> Optional[Window]:
        """Retrieves the latest managed forground window if any"""
        if self.last_active_window and (
            self.last_active_window not in self.managed_windows
            or not self.last_active_window.exists()
        ):
            return None
        return self.last_active_window

    def find_owner(self, window: Window) -> Optional[MonitorState]:
        """Retrieves the windows list containing specified window and its index in the list"""
        monitor = get_monitor_from_window(window.handle)
        monitor_state = self.get_monitor(monitor)
        if window in monitor_state.windows:
            return monitor_state
        return None
