"""WorkspaceState maintins the state of a workspace"""
import logging
from typing import List, Set
from os import path

from jigsawwm.w32.window import RECT, Window
from jigsawwm.w32.process import ProcessDpiAwareness
from jigsawwm.w32.monitor import Monitor

from .config import WmConfig
from .theme import Theme

logger = logging.getLogger(__name__)


class WorkspaceState:
    """WorkspaceState maintins the state of a workspace"""
    config: WmConfig
    name: str
    monitor: Monitor
    theme: Theme
    windows: List[Window]

    def __init__(self, config: WmConfig, name: str, monitor: Monitor):
        self.config = config
        self.name = name
        self.monitor = monitor
        self.theme = self.config.get_theme_for_workspace(monitor, name)
        self.windows = []

    def toggle(self, show: bool):
        """Toggle all windows in the workspace"""
        logger.debug("toggle workspace %s show %s", self.name, show)
        for window in self.windows:
            if show:
                window.show()
            else:
                window.hide()

    def set_theme(self, theme: Theme):
        """Set theme for the workspace"""
        logger.debug("set theme %s for workspace %s", theme.name, self.name)
        self.theme = theme
        self.config.set_theme_for_workspace(self.monitor, self.name, theme)
        self.arrange()

    def add_window(self, window: Window):
        """Add a window to the workspace"""
        logger.debug("add window %s to workspace %s", window, self.name)
        windows = self.windows
        if self.theme.new_window_as_master:
            windows = [window] + self.windows
        else:
            windows = self.windows + [window] 
        self.set_windows(windows)

    def remove_window(self, window: Window):
        """Remove a window from the workspace"""
        logger.debug("remove window %s from workspace %s", window, self.name)
        windows = [w for w in self.windows if w != window]
        self.set_windows(windows)

    def has_window(self, window: Window):
        """Check if the workspace has the window"""
        for w in self.windows:
            if w == window:
                return True
        return False

    def sync_windows(self, windows: Set[Window]):
        """Sync the internal windows list to the incoming windows list"""
        logger.debug("sync windows for workspace %s", self.name)
        # remove windows that are not in the incoming list
        new_list = []
        for w in self.windows:
            # window does not exist anymore, ingore it
            if w not in windows:
                continue
            # put the window back if it is in the incoming list
            new_list.append(w)
            windows.remove(w)
        # now, only new windows are in the set
        new_windows = []
        # extract predefined-order windows and put them into the new_windows list
        if self.config.init_exe_sequence:
            for [exe, title] in self.config.init_exe_sequence:
                for w in windows:
                    if exe.lower() == path.basename(w.exe).lower() and title in w.title.lower():
                        new_windows.append(w)
                        windows.remove(w)
        # add the rest new windows to the new_windows list
        new_windows += list(windows)
        # append or prepend new_windows based on the theme setting
        if self.theme.new_window_as_master:
            new_list = new_windows + new_list
        else:
            new_list += new_windows
        self.set_windows(new_list)

    def set_windows(self, windows: List[Window]):
        """Set windows for the workspace"""
        logger.debug("set windows %s for workspace %s", self.name, windows)
        windows = [w for w in windows if w.exists()]
        if windows == self.windows:
            return self.restrict()
        self.windows = windows
        self.arrange()

    def arrange(self):
        """Arrange windows based on the theme

        :param str theme: optional, fallback to theme of the instance
        """
        logger.debug("arrange workspace %s of %s with %d windows", self.name, self.monitor, len(self.windows))
        theme = self.theme
        wr = self.monitor.get_info().rcWork
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self.windows
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
            window.set_rect(rect)
            i += 1
            if window.dpi_awareness != ProcessDpiAwareness.PROCESS_PER_MONITOR_DPI_AWARE:
                # seems like the `get_extended_frame_bounds` would return physical size
                # for DPI unware window, skip them for now
                # TODO: convert physical size to logical size for DPI unware window
                continue
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

    def restrict(self):
        """Restrict all managed windows to their specified rect"""
        logger.debug("restrict workspace %s", self.name)
        if not self.theme.strict:
            return
        for window in self.windows:
            window.restrict()
