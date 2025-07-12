"""WorkspaceState maintins the state of a workspace"""

import logging
from typing import Iterator, List, Optional, Set, Tuple

from jigsawwm.w32.monitor import Monitor, get_cursor_pos
from jigsawwm.w32.window import Rect, Window

from .const import PREFERRED_WINDOW_INDEX, STATIC_WINDOW_INDEX, WORKSPACE_STATE
from .theme import Theme, mono

logger = logging.getLogger(__name__)


class WorkspaceState:
    """WorkspaceState maintins the state of a workspace"""

    monitor_index: int
    index: int
    name: str
    rect: Rect
    theme: Theme
    prev_theme: Theme
    windows: Set[Window]
    tiling_windows: List[Optional[Window]]
    floating_windows: List[Window]
    minimized_windows: List[Window]
    showing: bool = False
    last_active_window: Optional[Window] = None
    tiling_areas: List[Rect] = []
    dirty: bool = False

    def __init__(
        self,
        monitor_index: int,
        index: int,
        name: str,
        monitor: Monitor,
        alter_rect: Rect,
        theme: Theme,
    ):
        self.monitor_index = monitor_index
        self.index = index
        self.name = name
        self.monitor = monitor
        self.alter_rect = alter_rect
        self.theme = theme
        self.prev_theme = None
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

        current_rect = self.monitor.get_work_rect() if self.showing else self.alter_rect

        for window in self.windows:
            if not window.relative_rect:
                logger.warning("%s has no relative rect, skipping toggle", window)
                continue
            window.set_rect(window.relative_rect.relative_to(current_rect))
            window.toggle(show)
        if self.showing:
            if self.dirty:
                self.sync_windows(force_arrange=True)
            if not self.floating_windows:
                w = self.last_active_window
                if not w and self.tiling_windows:
                    w = self.tiling_windows[0]
                if w and w.exists():
                    w.activate()
                # make floating windows on top of tiling windows
            else:
                for w in self.floating_windows:
                    w.activate()

    def set_theme(self, theme: Theme):
        """Set theme for the workspace"""
        logger.debug("%s set theme %s", self, theme.name)
        self.theme = theme
        self.sync_windows(force_arrange=True)

    def toggle_mono_theme(self):
        """Toggle mono theme"""
        if self.theme == mono:
            if self.prev_theme:
                self.set_theme(self.prev_theme)
        else:
            self.prev_theme = self.theme
            self.set_theme(mono)

    # def set_rect(self, rect: Rect):
    #     """Set the rect of the workspace"""
    #     self.rect = rect
    #     self.arrange()

    def sync_windows(self, force_arrange=False) -> bool:
        """Sync the internal windows list to the incoming windows list"""
        logger.debug("%s sync windows", self)
        for window in self.windows:
            window.attrs[WORKSPACE_STATE] = self
        tiling_windows, floating_windows, self.minimized_windows = self._group_windows()
        if self.theme.static_layout:
            tiling_windows = self.sort_by_static_index(tiling_windows)
        if force_arrange or tiling_windows != self.tiling_windows:
            self.tiling_windows = tiling_windows
            self.arrange()
        if floating_windows != self.floating_windows:
            self.floating_windows = floating_windows
            self.arrange_floating_windows()

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
        self.tiling_areas = list(self.generate_relative_tiling_areas(m))
        logger.debug("%s tiling_areas: %s", self, self.tiling_areas)
        # arrange all except the last areaself.theme.
        work_rect = self.monitor.get_work_rect()
        for i in range(m - 1):
            if windows[i] is not None:
                logger.debug(
                    "set_restricted_rect relative: %s container: %s",
                    self.tiling_areas[i],
                    work_rect,
                )
                windows[i].set_restricted_rect(self.tiling_areas[i], work_rect)
        # arrange the last area
        overflow = n > m
        if overflow:
            self._stack_the_rest(self.tiling_areas[-1], work_rect)
        elif n == m and n > 0:
            windows[-1].set_restricted_rect(self.tiling_areas[-1], work_rect)

    def arrange_floating_windows(self):
        """Arrange floating windows in the workspace"""
        work_rect = self.monitor.get_work_rect()
        for window in self.floating_windows:
            if not window.relative_rect:
                # calcuate relative rect if not set
                work_rect = self.monitor.get_work_rect()
                window_rect = window.get_rect()
                if not work_rect.intersected(window_rect):
                    # if the window is not in the work rect, set its relative rect to the center of the work rect
                    logger.debug(
                        "%s is not in work rect %s, setting relative rect to center",
                        window,
                        work_rect,
                    )
                    relative_rect = window_rect.center_of(
                        Rect(0, 0, work_rect.width, work_rect.height)
                    )
                else:
                    # or calculate the relative rect based on the work rect
                    logger.debug(
                        "%s is in work rect %s, setting relative rect to relative",
                        window,
                        work_rect,
                    )
                    relative_rect = window_rect.relative_to(work_rect)
                logger.debug("%s set relative rect %s", window, relative_rect)
                window.relative_rect = relative_rect
            window.set_relative_rect(window.relative_rect, work_rect)

    def generate_relative_tiling_areas(self, num: int) -> Iterator[Rect]:
        """Generate tiling areas for current monitor with respect to given number"""
        wr = self.monitor.get_work_rect()
        work_area = (0, 0, wr.width, wr.height)
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

    def _stack_the_rest(self, bound: Rect, container_rect: Rect):
        """Stack all the rest tiling windows starting from index into the specified bound"""
        # window size
        windows = self.tiling_windows
        index = len(self.tiling_areas) - 1
        n = len(windows)
        w = int(bound.width * self.theme.stacking_window_width)
        h = int(bound.height * self.theme.stacking_window_height)
        # offset between windows
        n = len(windows)
        num_rest = n - index - 1
        x_step = (bound.width - w) // num_rest
        y_step = (bound.height - h) // num_rest
        left, top = bound.left, bound.top
        for i in range(index, n):
            if not self.tiling_windows[i]:
                continue
            windows[i].set_restricted_rect(
                Rect(left, top, left + w, top + h), container_rect
            )
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
        if self.tiling_windows:
            if self.last_active_window is None:
                self.last_active_window = self.tiling_windows[0]
            if self.last_active_window not in self.tiling_windows:
                self.last_active_window = self.tiling_windows[0]
        if not self.last_active_window:
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
        logger.debug("%s toggle %s showing to %s", self, window, show)

    def add_window(self, window: Window, workspace_index: Optional[int] = None):
        """Add a window to the workspace"""
        logger.debug("%s add window %s", self, window)
        if workspace_index is None:
            workspace_index = self.index
        if window in self.windows:
            logger.warning("%s already in %s", window, self)
            return
        self.windows.add(window)
        window.attrs[WORKSPACE_STATE] = self
        if not self.showing:
            # if workspace is not showing, set relative rect to alter_rect
            window.set_relative_rect(
                window.relative_rect or window.get_rect(), self.alter_rect
            )
            window.hide()
        self.dirty = True

    def remove_window(self, window: Window):
        """Remove a window from the workspace"""
        logger.debug("%s remove window %s", self, window)
        if window not in self.windows:
            logger.warning("%s not in %s", window, self)
            return
        self.windows.remove(window)
        window.attrs.pop(WORKSPACE_STATE, None)
        self.dirty = True

    def reclaim_hidden_windows(self):
        """Reclaim windows got hidden by the previous process"""
        logger.debug("%s reclaim hidden windows", self)
        for window in self.windows:
            if window.off:
                self.toggle_window(window, True)
        """Reclaim windows got hidden by the previous process"""
        logger.debug("%s reclaim hidden windows", self)
        for window in self.windows:
            if window.off:
                self.toggle_window(window, True)
