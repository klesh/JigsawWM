"""WorkspaceState maintins the state of a workspace"""

import logging
from typing import List, Optional, Set, Tuple

from jigsawwm.w32.window import Window, Rect

from .theme import Theme
from .const import PREFERRED_WINDOW_INDEX

logger = logging.getLogger(__name__)


class WorkspaceState:
    """WorkspaceState maintins the state of a workspace"""

    monitor_index: int
    index: int
    name: str
    rect: Rect
    theme: Theme
    windows: Set[Window]
    tiling_windows: List[Optional[Window]]
    floating_windows: List[Window]
    minimized_windows: List[Window]
    showing: bool = False
    last_active_window: Optional[Window] = None

    def __init__(
        self, monitor_index: int, index: int, name: str, rect: Rect, theme: Theme
    ):
        self.monitor_index = monitor_index
        self.index = index
        self.name = name
        self.rect = rect
        self.theme = theme
        self.windows = set()
        self.tiling_windows = []
        self.floating_windows = []
        self.minimized_windows = []

    def __repr__(self) -> str:
        return f"<WorkspaceState #{self.monitor_index}.{self.index}>"

    def toggle(self, show: bool):
        """Toggle all windows in the workspace"""
        logger.debug("%s toggle show %s", self, show)
        self.showing = show
        for window in self.windows:
            window.toggle(show)
        self.arrange()

    def set_theme(self, theme: Theme):
        """Set theme for the workspace"""
        logger.debug("%s set theme %s", self, theme.name)
        self.theme = theme
        self.arrange()

    def set_rect(self, rect: Rect):
        """Set the rect of the workspace"""
        self.rect = rect
        self.arrange()

    def sync_windows(self) -> bool:
        """Sync the internal windows list to the incoming windows list"""
        logger.debug("%s sync windows", self)
        tiling_windows, self.floating_windows, self.minimized_windows = (
            self._split_windows()
        )
        if tiling_windows != self.tiling_windows:
            self.tiling_windows = tiling_windows
            self.arrange()

    def _split_windows(self) -> Tuple[Set[Window], Set[Window], Set[Window]]:
        tiling_windows, floating_windows, minimized_windows = set(), set(), set()
        for w in self.windows:
            if w.is_iconic:
                minimized_windows.add(w)
            elif w.tilable:
                tiling_windows.add(w)
            else:
                floating_windows.add(w)
        return (
            self._update_list_from_set(self.tiling_windows, tiling_windows),
            self._update_list_from_set(self.floating_windows, floating_windows),
            self._update_list_from_set(self.minimized_windows, minimized_windows),
        )

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
        n = len(windows)
        if theme.max_tiling_windows > 0:
            n = min(theme.max_tiling_windows, n)
        for left, top, right, bottom in theme.layout_tiler(work_area, n):
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
            window.set_restrict_rect(Rect(left, top, right, bottom))
            i += 1
        # stack the rest
        num_rest = len(windows) - i - 1
        if num_rest <= 0:
            return
        self._stack_the_rest(i, num_rest)

    def _stack_the_rest(self, index: int, num_rest: int):
        # monitor width and height
        wr = self.rect
        mw, mh = wr.right - wr.left, wr.bottom - wr.top
        # window width and height
        w = int(mw * self.theme.stacking_window_width)
        h = int(mh * self.theme.stacking_window_height)
        # stacking boundaries
        x_margin = int(mw * self.theme.stacking_margin_x)
        y_margin = int(mh * self.theme.stacking_margin_y)
        left, top, right, bottom = (
            wr.left + x_margin,
            wr.top + y_margin,
            wr.right - x_margin,
            wr.bottom - y_margin,
        )
        # final stacking area
        x_step = min((right - left - w) // num_rest, self.theme.stacking_max_step)
        y_step = min((bottom - top - h) // num_rest, self.theme.stacking_max_step)
        bw, wh = x_step * num_rest + w, y_step * num_rest + h
        x_margin, y_margin = (mw - bw) // 2, (mh - wh) // 2
        left, top, right, bottom = (
            wr.left + x_margin,
            wr.top + y_margin,
            wr.right - x_margin,
            wr.bottom - y_margin,
        )
        for i in range(index, len(self.tiling_windows)):
            rect = Rect(left, top, left + w, top + h)
            self.tiling_windows[i].set_restrict_rect(rect)
            left += x_step
            top += y_step

    def restrict(self):
        """Restrict all managed windows to their specified rect"""
        logger.debug("%s restrict total %d windows", self, len(self.tiling_windows))
        if not self.theme.strict:
            return
        for window in self.tiling_windows:
            window.restrict()
