"""WorkspaceState maintins the state of a workspace"""
import logging
from typing import List, Set, Optional
from os import path

from jigsawwm.w32.window import RECT, Window, get_active_window
from jigsawwm.w32.process import ProcessDpiAwareness
from jigsawwm.w32.monitor import Monitor, set_cursor_pos
from jigsawwm import workers

from .config import WmConfig
from .theme import Theme
from .pickable_state import PickableState

logger = logging.getLogger(__name__)


class WorkspaceState(PickableState):
    """WorkspaceState maintins the state of a workspace"""
    config: WmConfig
    name: str
    monitor: Monitor
    theme: Theme
    tilable_windows: List[Window]
    windows: Set[Window]
    showing: bool
    theme_name: str # for restoring
    last_active_window: Optional[Window] = None

    def __init__(self, config: WmConfig, name: str, monitor: Monitor):
        self.config = config
        self.name = name
        self.monitor = monitor
        self.theme = self.config.get_theme_for_monitor(monitor)
        self.theme_name = self.theme.name
        self.tilable_windows = []
        self.windows = set()
        self.showing = False
        self.last_active_window = None

    def __repr__(self) -> str:
        return f"<WorkspaceState {self.name} {self.monitor.name}>"

    def __getstate__(self):
        state = super().__getstate__()
        del state['theme']
        return state

    def update_config(self, config: WmConfig):
        """Update the workspace based on configuration"""
        self.config = config
        self.theme = self.config.get_theme_by_name(self.theme_name)
        for window in self.windows:
            if window.exists() and not self.showing:
                window.hide()

    def on_unfocus(self):
        """Unfocus the workspace"""
        fw = get_active_window()
        if fw in self.windows:
            self.last_active_window = fw

    def on_focus(self):
        """Focus on the last active window or the center of the screen"""
        if (
            self.last_active_window
            and self.last_active_window.exists()
            and self.last_active_window in self.windows
            and self.last_active_window.is_visible
        ):
            logger.debug("%s activate last active window %s", self, self.last_active_window)
            self.last_active_window.activate()
        elif self.tilable_windows:
            logger.debug("%s activate first tilable window %s", self, self.tilable_windows[0])
            self.tilable_windows[0].activate()
        else:
            logger.debug("%s activate center of the screen", self)
            rect = self.monitor.get_info().rcWork
            x, y = (
                rect.left + (rect.right - rect.left) / 2,
                rect.top + (rect.bottom - rect.top) / 2,
            )
            set_cursor_pos(x, y)

    def toggle(self, show: bool):
        """Toggle all windows in the workspace"""
        logger.debug("%s toggle show %s", self, show)
        self.showing = show
        if not show:
            self.on_unfocus()
        for window in self.windows:
            window.toggle(show)
        if show:
            self.sync_windows(self.windows)
            self.on_focus()

    def set_theme(self, theme: Theme):
        """Set theme for the workspace"""
        logger.debug("%s set theme %s", self, theme.name)
        self.theme = theme
        self.theme_name = theme.name
        self.arrange()

    def add_window(self, window: Window):
        """Add a window to the workspace"""
        logger.debug("%s add window %s", self, window)
        self.sync_windows(self.windows.union({window}))

    def remove_window(self, window: Window):
        """Remove a window from the workspace"""
        logger.debug("%s remove window %s", self, window)
        self.sync_windows(self.windows.difference({window}))

    def has_window(self, window: Window):
        """Check if the workspace has the window"""
        return window in self.windows

    def sync_windows(self, incoming_windows: Set[Window]):
        """Sync the internal windows list to the incoming windows list"""
        logger.debug("%s sync windows", self)
        # make sure windows are still valid
        incoming_windows = { w for w in incoming_windows if w.exists() }
        # update the internal windows list
        self.windows = incoming_windows
        # process the tilable windows
        incoming_tilable_windows = {
            w for w in incoming_windows
            if w.is_tilable and w.is_visible and self.config.is_window_tilable(w)
        }
        # remove windows that are not in the incoming list
        new_tilable_windows = []
        for w in self.tilable_windows:
            # window does not exist anymore, ingore it
            if w not in incoming_tilable_windows:
                continue
            # put the window back if it is in the incoming list
            new_tilable_windows.append(w)
            incoming_tilable_windows.remove(w)
        # now, only new windows are in the set
        new_tilable_portion = []
        # extract predefined-order windows and put them into the new_windows list
        if self.config.init_exe_sequence:
            for [exe, title] in self.config.init_exe_sequence:
                for w in incoming_tilable_windows:
                    if exe.lower() == path.basename(w.exe).lower() and title in w.title.lower():
                        new_tilable_portion.append(w)
                        incoming_tilable_windows.remove(w)
        # add the rest new windows to the new_windows list
        new_tilable_portion += list(incoming_tilable_windows)
        # append or prepend new_windows based on the theme setting
        if self.theme.new_window_as_master:
            new_tilable_windows = new_tilable_portion + new_tilable_windows
        else:
            new_tilable_windows += new_tilable_portion
        if new_tilable_windows == self.tilable_windows:
            return self.restrict()
        self.tilable_windows = new_tilable_windows
        self.arrange()

    def arrange(self):
        """Arrange windows based on the theme

        :param str theme: optional, fallback to theme of the instance
        """
        logger.debug("%s arrange total %d windows", self, len(self.tilable_windows))
        theme = self.theme
        wr = self.monitor.get_info().rcWork
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self.tilable_windows
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
            i += 1
            if window.dpi_awareness != ProcessDpiAwareness.PROCESS_PER_MONITOR_DPI_AWARE:
                # seems like the `get_extended_frame_bounds` would return physical size
                # for DPI unware window, skip them for now
                # TODO: convert physical size to logical size for DPI unware window
                window.set_restrict_rect(rect)
                continue
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
            window.set_restrict_rect(RECT(*compensated_rect))
        workers.submit_with_delay(self.restrict, 0.2)

    def restrict(self):
        """Restrict all managed windows to their specified rect"""
        logger.debug("%s restrict total %d windows", self, len(self.tilable_windows))
        if not self.theme.strict:
            return
        for window in self.tilable_windows:
            window.restrict()
