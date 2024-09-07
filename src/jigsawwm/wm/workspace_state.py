"""WorkspaceState maintins the state of a workspace"""

import logging
from typing import List, Optional, Set, Tuple

from jigsawwm.w32.window import Window, Rect
from jigsawwm.w32.monitor import get_cursor_pos

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
    tiling_areas: List[Rect] = []

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
        logger.debug("%s toggle %s", self, show)
        self.showing = show
        for window in self.windows:
            window.toggle(show)
        if show:
            w = self.last_active_window
            if not w and self.tiling_windows:
                w = self.tiling_windows[0]
            if w:
                w.activate()

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
            self._group_windows()
        )
        if tiling_windows != self.tiling_windows:
            self.tiling_windows = tiling_windows
            self.arrange()

    def _group_windows(self) -> Tuple[Set[Window], Set[Window], Set[Window]]:
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
        return windows_list

    def arrange(self):
        """Arrange windows based on the theme

        :param str theme: optional, fallback to theme of the instance
        """
        logger.debug("%s arrange total %d windows", self, len(self.tiling_windows))
        for i, window in enumerate(self.tiling_windows):
            window.attrs[PREFERRED_WINDOW_INDEX] = i
        theme = self.theme
        wr = self.rect
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self.tiling_windows
        i = 0
        gap = theme.gap
        # tile the first n windows
        w = len(windows)
        n = w
        if theme.max_tiling_areas > 0:
            n = min(theme.max_tiling_areas, n)
        r = None
        self.tiling_areas = []
        for left, top, right, bottom in theme.layout_tiler(work_area, n):
            window = windows[i]
            i += 1
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
            r = Rect(left, top, right, bottom)
            self.tiling_areas.append(r)
            if i == n and w > n:  # when
                break
            window.set_restrict_rect(r)
        # stack the rest
        num_rest = w - n
        if num_rest <= 0:
            return
        self._stack_the_rest(i - 1, num_rest, r)

    def _stack_the_rest(self, index: int, num_rest: int, bound: Rect):
        # window size
        w = int(bound.width * self.theme.stacking_window_width)
        h = int(bound.height * self.theme.stacking_window_height)
        # offset between windows
        x_step = (bound.width - w) // num_rest
        y_step = (bound.height - h) // num_rest
        left, top = bound.left, bound.top
        for i in range(index, len(self.tiling_windows)):
            self.tiling_windows[i].set_restrict_rect(Rect(left, top, left + w, top + h))
            left += x_step
            top += y_step

    def restrict(self):
        """Restrict all managed windows to their specified rect"""
        logger.debug("%s restrict total %d windows", self, len(self.tiling_windows))
        if not self.theme.strict:
            return
        for window in self.tiling_windows:
            window.restrict()

    def tiling_index_from_cursor(self) -> int:
        """Get the index of the tiling area under the cursor"""
        pos = get_cursor_pos()
        for i, r in enumerate(self.tiling_areas):
            if r.contains(pos.x, pos.y):
                return i
        return -1
