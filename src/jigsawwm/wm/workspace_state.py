"""WorkspaceState maintins the state of a workspace"""

import logging
import time
from typing import Iterator, List, Optional, Set, Tuple

from jigsawwm.w32.monitor import Monitor, get_cursor_pos
from jigsawwm.w32.window import (InsertAfter, Rect, Window,
                                 get_foreground_window)

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
            window.set_rect(window.relative_rect.into(current_rect))
            window.toggle(show)

        if self.showing:
            if self.dirty:
                self.sync_windows(force_arrange=True)
            if not self.floating_windows:
                self.focus_fallback()
            else:
                # make floating windows on top of tiling windows
                p = self.floating_windows[0]
                p.insert_after(InsertAfter.HWND_TOP)
                for w in self.floating_windows[1:]:
                    w.insert_after(p)
                    p = w

    def focus_fallback(self):
        """Focus a window"""
        w = self.last_active_window
        if (not w or w not in self.windows) and self.tiling_windows:
            w = self.tiling_windows[0]
        if w and w.exists():
            w.activate()

    def show_floating_windows(self):
        """Show floating windows in stacking manner"""
        logger.info("show_floating_windows")
        # work_rect = self.monitor.get_work_rect()
        # w, h = work_rect.width * 0.618, work_rect.height * 0.618
        # left, top = (work_rect.width - w) // 2, (work_rect.height - h) // 2
        # bound_rect = Rect(left, top, left + w, top + h)
        windows = list(w for w in self.floating_windows if w and w.exists())
        # self._stack_windows(work_rect, bound_rect, windows)
        # p = InsertAfter.HWND_BOTTOM
        p = None
        a = None
        if windows:
            for w in windows:
                w.insert_after(p)
                p = w.handle
            a = windows[0]
        if self.tiling_windows:
            for w in self.tiling_windows:
                w.insert_after(p)
                p = w.handle
            a = a or self.tiling_windows[0]
        a.activate()

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
            self.update_floating_windows_rects()

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
            # set z-orders for stacking layout
            # if new_list:
            #     new_list[0].insert_after(InsertAfter.HWND_TOP)
        else:
            windows_list += new_list
        #     if windows_list and new_list:
        #         new_list[0].insert_after(windows_list[-1])
        # if len(new_list) > 1:
        #     p = new_list[0]
        #     for w in new_list[1:]:
        #         w.insert_after(p)
        #         p = w
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
        windows = list(w for w in self.tiling_windows if w and w.exists())
        # tile the first n windows
        n = len(windows)
        m = n
        if theme.max_tiling_areas > 0:
            m = min(theme.max_tiling_areas, m)
        self.tiling_areas = list(self.generate_relative_tiling_areas(m))
        logger.debug("%s tiling_areas: %s", self, self.tiling_areas)
        # arrange all except the last areaself.theme.
        work_rect = self.monitor.get_work_rect()
        # insert_after = InsertAfter.HWND_BOTTOM
        active_handle = get_foreground_window() 
        insert_after = active_handle
        for i in range(m - 1):
            w = windows[i]
            if w is not None:
                ia = insert_after if self.theme.reorder and active_handle != w.handle else None
                w.set_restricted_rect(self.tiling_areas[i], work_rect, ia)
                insert_after = w.handle
                if self.theme.reorder:
                    time.sleep(0.1)
        # arrange the last area
        overflow = n > m
        if overflow:
            bound = self.tiling_areas[-1]
            w = int(bound.width * self.theme.stacking_window_width)
            h = int(bound.height * self.theme.stacking_window_height)
            windows = self.tiling_windows[m - 1 :]
            self._stack_windows(work_rect, bound, windows, w=w, h=h)
        elif n == m and n > 0:
            w = windows[-1]
            ia = insert_after if self.theme.reorder and active_handle != w.handle else None
            w.set_restricted_rect(self.tiling_areas[-1], work_rect,  ia)

    def update_floating_windows_rects(self):
        """Arrange floating windows in the workspace"""
        work_rect = self.monitor.get_work_rect()
        for window in self.floating_windows:
            if not window.relative_rect:
                self.update_relative_rect(window)
            else:
                window.set_relative_rect(window.relative_rect, work_rect)

    def update_relative_rect(self, window: Window):
        """Update floating window relative rect when it was moved / resized"""
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
            relative_rect = Rect(
                window_rect.left - work_rect.left,
                window_rect.top - work_rect.top,
                window_rect.right - work_rect.left,
                window_rect.bottom - work_rect.top,
            )
        window.relative_rect = relative_rect

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

    def _stack_windows(
        self,
        work_rect,
        bound_rect: Rect,
        windows: list[Window],
        w: int = None,
        h: int = None,
    ):
        """Stack all the rest tiling windows starting from index into the specified bound"""
        if not windows:
            return
        # window size
        n = len(windows) - 1
        r = windows[-1].get_rect()
        x_step = int((bound_rect.width - (w or r.width)) // n) if n else 0
        y_step = int((bound_rect.height - (h or r.height)) // n) if n else 0
        left, top = int(bound_rect.left), int(bound_rect.top)
        for window in windows:
            wr = window.get_rect()
            rect = Rect(left, top, left + int(w or wr.width), top + int(h or wr.height))
            if w and h:
                window.set_restricted_rect(rect, work_rect)
            else:
                logger.info(
                    "set window %s rect to %s relative to %s", window, rect, work_rect
                )
                window.set_relative_rect(rect, work_rect)
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
        logger.debug("%s reclaim hidden windows", self)
        for window in self.windows:
            if window.off:
                self.toggle_window(window, True)
