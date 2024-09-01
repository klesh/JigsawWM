"""WorkspaceState maintins the state of a workspace"""

import logging
from typing import List, Optional, Set

from jigsawwm.w32.window import Window, RECT

from .theme import Theme
from .pickable_state import PickableState
from .const import PREFERRED_WINDOW_INDEX

logger = logging.getLogger(__name__)


class WorkspaceState(PickableState):
    """WorkspaceState maintins the state of a workspace"""

    monitor_index: int
    index: int
    name: str
    rect: RECT
    theme: Theme
    windows: Set[Window]
    tiling_windows: List[Optional[Window]]
    floating_windows: List[Window]
    showing: bool = False
    last_active_window: Optional[Window] = None

    def __init__(
        self, monitor_index: int, index: int, name: str, rect: RECT, theme: Theme
    ):
        self.monitor_index = monitor_index
        self.index = index
        self.name = name
        self.rect = rect
        self.theme = theme
        self.tiling_windows = []
        self.other_windows = []

    def __repr__(self) -> str:
        return f"<WorkspaceState #{self.monitor_index}.{self.index}>"

    def toggle(self, show: bool):
        """Toggle all windows in the workspace"""
        logger.debug("%s toggle show %s", self, show)
        self.showing = show
        for window in self.windows:
            window.toggle(show)

    def set_theme(self, theme: Theme):
        """Set theme for the workspace"""
        logger.debug("%s set theme %s", self, theme.name)
        self.theme = theme
        self.arrange()

    def sync_windows(self) -> bool:
        """Sync the internal windows list to the incoming windows list"""
        logger.debug("%s sync windows", self)
        tilable_windows, floating_windows = set(), set()
        for w in self.windows:
            if w.is_iconic:
                continue
            if w.tilable:
                tilable_windows.add(w)
            else:
                floating_windows.add(w)
        self.floating_windows = self._update_list_from_set(
            self.floating_windows, floating_windows
        )
        tiling_windows = self._update_list_from_set(
            self.tiling_windows, tilable_windows
        )
        if tilable_windows != self.tiling_windows:
            self.tiling_windows = tiling_windows
            self.arrange()

    def _update_list_from_set(
        self, windows_list: List[Window], windows_set: Set[Window]
    ) -> List[Window]:
        windows_list = [w for w in windows_list if w in windows_set]
        old_set = set(windows_list)
        new_set = windows_set - old_set
        new_list = sorted(new_set, key=lambda w: w.attrs.get(PREFERRED_WINDOW_INDEX, 0))
        if self.theme.new_window_as_master:
            windows_list = new_list + windows_list
        else:
            windows_list += new_list
        for i, window in enumerate(windows_list):
            window.attrs[PREFERRED_WINDOW_INDEX] = i
        return windows_list

    def arrange(self):
        """Arrange windows based on the theme

        :param str theme: optional, fallback to theme of the instance
        """
        logger.debug("%s arrange total %d windows", self, len(self.tiling_windows))
        theme = self.theme
        wr = self.rect
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self.tiling_windows
        i = 0
        gap = theme.gap
        # tile the first n windows
        for left, top, right, bottom in theme.layout_tiler(
            work_area, min(theme.max_tiling_windows, len(windows))
        ):
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
        # stack the rest
        num_rest = len(windows) - i - 1
        if num_rest <= 0:
            return
        x_margin = int((wr.right - wr.left) * 0.1)
        y_margin = int((wr.bottom - wr.top) * 0.1)
        left, top, right, bottom = (
            wr.left + x_margin,
            wr.top + y_margin,
            wr.right - x_margin,
            wr.bottom - y_margin,
        )
        x_step, y_step = 40, 40
        right, bottom = right - x_step * num_rest, bottom - y_step * num_rest
        while i < len(windows):
            rect = RECT(left, top, right, bottom)
            windows[i].set_restrict_rect(rect)
            left, top, right, bottom = (
                left + x_step,
                top + y_step,
                right + x_step,
                bottom + y_step,
            )
            i += 1

    def restrict(self):
        """Restrict all managed windows to their specified rect"""
        logger.debug("%s restrict total %d windows", self, len(self.tiling_windows))
        if not self.theme.strict:
            return
        for window in self.tiling_windows:
            window.restrict()
