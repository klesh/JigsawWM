"""WorkspaceState maintins the state of a workspace"""

import logging
from typing import List, Optional, Set, Tuple, Iterator

from jigsawwm.w32.window import Window, Rect
from jigsawwm.w32.monitor import get_cursor_pos

from .theme import Theme
from .const import PREFERRED_WINDOW_INDEX, STATIC_WINDOW_INDEX

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
        self,
        monitor_index: int,
        index: int,
        name: str,
        rect: Rect,
        alter_rect: Rect,
        theme: Theme,
    ):
        self.monitor_index = monitor_index
        self.index = index
        self.name = name
        self.rect = rect
        self.alter_rect = alter_rect
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
            self.toggle_window(window, show)
        if show:
            w = self.last_active_window
            if not w and self.tiling_windows:
                w = self.tiling_windows[0]
            if w and w.exists():
                w.activate()

    def set_theme(self, theme: Theme):
        """Set theme for the workspace"""
        logger.debug("%s set theme %s", self, theme.name)
        self.theme = theme
        self.sync_windows(force_arrange=True)

    def set_rect(self, rect: Rect):
        """Set the rect of the workspace"""
        self.rect = rect
        self.arrange()

    def sync_windows(self, force_arrange=False) -> bool:
        """Sync the internal windows list to the incoming windows list"""
        logger.debug("%s sync windows", self)
        tiling_windows, self.floating_windows, self.minimized_windows = (
            self._group_windows()
        )
        if self.theme.static_layout:
            tiling_windows = self.sort_by_static_index(tiling_windows)
        if force_arrange or tiling_windows != self.tiling_windows:
            self.tiling_windows = tiling_windows
            self.arrange()

    def sort_by_static_index(
        self, tiling_windows: List[Optional[Window]]
    ) -> List[Optional[Window]]:
        """ "Sort windows by static_index"""
        assert self.theme.max_tiling_areas > 1
        new_tiling_windows = [None] * self.theme.max_tiling_areas

        for w in tiling_windows:
            if w is None:
                continue
            if STATIC_WINDOW_INDEX in w.attrs:
                static_index = w.attrs[STATIC_WINDOW_INDEX]
                assert static_index < self.theme.max_tiling_areas
                assert (
                    new_tiling_windows[static_index] is None
                ), "static index duplicated"
                new_tiling_windows[static_index] = w
            else:
                new_tiling_windows.append(w)
        logger.info("new_tiling_windows: %s", new_tiling_windows)
        return new_tiling_windows

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
        new_list = sorted(
            new_set, key=lambda w: w.attrs.get(PREFERRED_WINDOW_INDEX, 0) if w else 0
        )
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
            if window:
                window.attrs[PREFERRED_WINDOW_INDEX] = i
        theme = self.theme
        windows = self.tiling_windows
        # tile the first n windows
        n = len(windows)
        m = n
        if theme.max_tiling_areas > 0:
            m = min(theme.max_tiling_areas, m)
        self.tiling_areas = list(self.generate_tiling_areas(m))
        # arrange all except the last areaself.theme.
        for i in range(m - 1):
            if windows[i] is not None:
                windows[i].set_restrict_rect(self.tiling_areas[i])
        # arrange the last area
        overflow = n > m
        if overflow:
            self._stack_the_rest(self.tiling_areas[-1])
        elif n == m and n > 0:
            windows[-1].set_restrict_rect(self.tiling_areas[-1])

    def generate_tiling_areas(self, num: int) -> Iterator[Rect]:
        """Generate tiling areas for current monitor with respect to given number"""
        wr = self.rect
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        gap = self.theme.gap or 0
        for left, top, right, bottom in self.theme.layout_tiler(work_area, num):
            if gap:
                if left == wr.left:
                    left += gap
                if top == wr.top:
                    top += gap
                if right == wr.right:
                    right -= gap
                if bottom == wr.bottom:
                    bottom -= gap
            yield Rect(left + gap, top + gap, right - gap, bottom - gap)

    def _stack_the_rest(self, bound: Rect):
        """Stack all the rest tiling windows starting from index into the specified bound"""
        # window size
        index = len(self.tiling_areas) - 1
        n = len(self.tiling_windows)
        w = int(bound.width * self.theme.stacking_window_width)
        h = int(bound.height * self.theme.stacking_window_height)
        # offset between windows
        n = len(self.tiling_windows)
        num_rest = n - index - 1
        x_step = (bound.width - w) // num_rest
        y_step = (bound.height - h) // num_rest
        left, top = bound.left, bound.top
        for i in range(index, n):
            if not self.tiling_windows[i]:
                continue
            self.tiling_windows[i].set_restrict_rect(Rect(left, top, left + w, top + h))
            left += x_step
            top += y_step

    def restrict(self):
        """Restrict all managed windows to their specified rect"""
        logger.debug("%s restrict total %d windows", self, len(self.tiling_windows))
        if not self.theme.strict:
            return
        for window in self.tiling_windows:
            if window:
                window.restrict()

    def tiling_index_from_cursor(self) -> int:
        """Get the index of the tiling area under the cursor"""
        pos = get_cursor_pos()
        for i, r in enumerate(self.tiling_areas):
            if r.contains(pos.x, pos.y):
                return i
        return -1

    def switch_window(self, delta: int):
        """Switch the active window in the tiling area"""
        if not self.tiling_windows:
            return
        if self.last_active_window is None:
            self.last_active_window = self.tiling_windows[0]
        elif self.last_active_window not in self.tiling_windows:
            self.last_active_window.activate()
            return
        i = self.tiling_windows.index(self.last_active_window)
        i = (i + delta) % len(self.tiling_windows)
        self.last_active_window = self.tiling_windows[i]
        self.last_active_window.activate()

    def toggle_window(self, window: Window, show: bool):
        """Toggle window visibility"""
        if show != window.off:
            logger.debug("%s already %s", self, "showing" if show else "hiding")
            return
        logger.debug("%s toggle showing to %s", self, show)
        r = window.get_rect()
        logger.debug(
            "%s window rect %s,  mr: %s, alter_rect: %s",
            window,
            r,
            self.rect,
            self.alter_rect,
        )
        if show:
            r = Rect(
                self.rect.left + (r.left - self.alter_rect.left),
                self.rect.top + (r.top - self.alter_rect.top),
                self.rect.right + (r.right - self.alter_rect.right),
                self.rect.bottom + (r.bottom - self.alter_rect.bottom),
            )
            window.show()
        else:
            r = Rect(
                self.alter_rect.left + (r.left - self.rect.left),
                self.alter_rect.top + (r.top - self.rect.top),
                self.alter_rect.right + (r.right - self.rect.right),
                self.alter_rect.bottom + (r.bottom - self.rect.bottom),
            )
            window.hide()
        window.set_rect(r)
        logger.debug("%s toggle by setting rect to %s", self, r)

    def reclaim_hidden_windows(self):
        """Reclaim windows got hidden by the previous process"""
        logger.debug("%s reclaim hidden windows", self)
        for window in self.windows:
            if window.off:
                self.toggle_window(window, True)
