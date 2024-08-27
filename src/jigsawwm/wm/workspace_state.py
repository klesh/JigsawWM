"""WorkspaceState maintins the state of a workspace"""
import logging
from typing import List, Set, Optional
from os import path

from jigsawwm.w32.monitor import Monitor, set_cursor_pos
from jigsawwm.w32.window import Window, get_active_window, RECT

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
        self.windows = { w for w in self.windows if w.exists() }
        self.tilable_windows = [ w for w in self.tilable_windows if w.exists() ]
        for window in self.windows:
            if window.exists() and not self.showing:
                window.hide()

    def before_hide(self):
        """Before hiding the workspace"""
        self.last_active_window = None
        fw = get_active_window()
        for w in self.windows:
            w.minimized_by_user = w.is_iconic
            if fw == w.handle:
                self.last_active_window = w

    def after_show(self):
        """After showing the workspace"""
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

    def toggle(self, show: bool, no_activation: bool = False):
        """Toggle all windows in the workspace"""
        logger.debug("%s toggle show %s activation: %s", self, show, not no_activation)
        self.showing = show
        if not show:
            self.before_hide()
        for window in self.windows:
            window.toggle(show)
        if show:
            self.sync_windows()
            if not no_activation:
                self.after_show()

    def set_theme(self, theme: Theme):
        """Set theme for the workspace"""
        logger.debug("%s set theme %s", self, theme.name)
        self.theme = theme
        self.theme_name = theme.name
        self.arrange()

    def add_window(self, window: Window):
        """Add a window to the workspace"""
        logger.debug("%s add window %s", self, window)
        window.attrs["workspace_state"] = self
        if window.is_visible != self.showing:
            window.toggle(self.showing)
        if window in self.windows:
            return
        self.windows.add(window)
        self.sync_windows()
        try:
            return self.tilable_windows.index(window)
        except ValueError:
            return 0

    def remove_window(self, window: Window):
        """Remove a window from the workspace"""
        logger.debug("%s remove window %s", self, window)
        if window not in self.windows:
            return
        self.windows.remove(window)
        self.sync_windows()

    def add_windows(self, windows: Set[Window]):
        """Add windows to the workspace"""
        logger.debug("%s add windows %s", self, windows)
        self.windows = self.windows.union(windows)
        self.sync_windows()

    def remove_windows(self, windows: Window):
        """Remove windows from the workspace"""
        logger.debug("%s remove windows %s", self, windows)
        self.windows = self.windows.difference(windows)
        self.sync_windows()

    def has_window(self, window: Window):
        """Check if the workspace has the window"""
        return window in self.windows

    def sync_windows(self) -> bool:
        """Sync the internal windows list to the incoming windows list"""
        logger.debug("%s sync windows", self)
        self.windows = {w for w in self.windows if w.exists()}

        def _check_tilable(w: Window):
            return w.manageable and w.tilable and not w.is_iconic

        tilable_windows = [w for w in self.tilable_windows if _check_tilable(w) and w in self.windows]
        new_tilable_windows_set = {w for w in self.windows if _check_tilable(w) and w not in tilable_windows}

        new_tilable_windows = []
        # extract predefined-order windows and put them into the new_windows list
        if self.config.init_exe_sequence:
            for [exe, title] in self.config.init_exe_sequence:
                for w in new_tilable_windows_set.copy():
                    if exe.lower() == path.basename(w.exe).lower() and title in w.title.lower():
                        new_tilable_windows.append(w)
                        new_tilable_windows_set.remove(w)
        
        # append the rest new windows
        default_order = 0 if self.theme.new_window_as_master else len(tilable_windows)
        new_tilable_windows = sorted(new_tilable_windows_set, key=lambda w: w.attrs.get("preferred_window_order", default_order))
        # append or prepend new_windows based on the theme setting
        if self.theme.new_window_as_master:
            tilable_windows = new_tilable_windows + tilable_windows
        else:
            tilable_windows += new_tilable_windows
        if tilable_windows == self.tilable_windows:
            self.restrict()
        else:
            self.tilable_windows = tilable_windows
            self.arrange()
        logger.debug("%s sync windows, total: %d, tilable: %d", self, len(self.windows), len(self.tilable_windows))

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
            window.set_restrict_rect(rect)
            i += 1

    def restrict(self):
        """Restrict all managed windows to their specified rect"""
        logger.debug("%s restrict total %d windows", self, len(self.tilable_windows))
        if not self.theme.strict:
            return
        for window in self.tilable_windows:
            window.restrict()
