from typing import Set, Dict, List, Optional
from jigsawwm.w32.monitor import (
    Monitor,
    get_monitor_from_window,
    get_monitor_from_cursor,
    set_cursor_pos,
)
from jigsawwm.w32.window import Window, get_normal_windows, get_active_window, RECT
from jigsawwm.w32.ivirtualdesktopmanager import GUID
from jigsawwm.tiler.tilers import *
from os import path
from threading import Thread
import time


class WindowManager:
    """WindowManager detect the monitors/windows state and arrange them dynamically
    keep in mind that not all windows are managed by the WindowManager, only those
    returned by `jigsawwm.w32.get_normal_windows()` and not ignored would be managed.

    The WindowManager works just like other Dynamic Window Managers, it store all
    managed windows in a list, the first one in the list is called Master, it would
    normally take up most area of the screen while others occuppy the rest.

    :param new_window_as_master: set the latest appeared window as the master
    :param layout_tilers: specify available layout tilers
    :param ignore_exe_names: list of executable filenames that you don't want them
                             to be managed/arranged
    :param gap: specify tha gap between windows and screen border, keep in mind it
                is half of what you want, say you want 6 pixel between windows, set
                it to 3.
    """

    _state: Dict[Monitor, List[Window]]
    new_window_as_master: bool
    layout_tilers: List[LayoutTiler]
    ignore_exe_names: Set[str]
    gap: int
    managed_windows: Optional[Set[Window]]
    _last_active_window: Optional[Window]

    def __init__(
        self,
        new_window_as_master: bool = True,
        layout_tilers: List[LayoutTiler] = None,
        ignore_exe_names: Set[str] = None,
        gap: int = 2,
    ):
        self._state = {}
        self.new_window_as_master = new_window_as_master
        self.layout_tilers = layout_tilers or [
            widescreen_dwindle_layout_tiler,
            obs_dwindle_layout_tiler,
            dwindle_layout_tiler,
        ]
        self.current_layout_tiler_index = 0
        self.ignore_exe_names = set(ignore_exe_names or [])
        self.gap = gap
        self.managed_windows = None
        self._last_active_window = None

    def sync(self) -> bool:
        """Update manager state(monitors, windows) to match OS's and arrange windows if it is changed"""
        state: Dict[Monitor, Set[Window]] = {}
        # get all normal windows and form managed windows list
        managed_windows = set()
        for window in get_normal_windows():
            # skip certain exe file name
            if path.basename(window.exe) in self.ignore_exe_names:
                continue
            # group them by monitor
            monitor = get_monitor_from_window(window.handle)
            windows = state.get(monitor)
            if not windows:
                windows = set()
                state[monitor] = windows
            windows.add(window)
            managed_windows.add(window)
        self.managed_windows = managed_windows
        # compare and update _state
        for monitor, windows in state.items():
            # found new monitor
            if monitor not in self._state:
                self._state[monitor] = list(windows)
                self.arrange_monitor(monitor)
                continue
            # monitor exists, respect the existing windows order
            # first, remove disappeared windows
            old_list = self._state[monitor]
            new_list = []
            for w in old_list:
                if w not in windows:
                    continue
                windows.remove(w)
                if not w.exists():
                    continue
                new_list.append(w)
            # and then, prepend or append the new windows
            if self.new_window_as_master:
                new_list = list(windows) + new_list
            else:
                new_list = new_list + list(windows)
            # skip if there is nothing changed
            if new_list == old_list:
                continue
            self._state[monitor] = new_list
            self.arrange_monitor(monitor)

    def arrange_monitor(self, monitor: Monitor):
        """Arranges windows from the specified monitor"""
        # now, here is the tricky part, thanks to the chaotic Win32 API
        #
        #   1. the `SetWindowPos` api accept Scaled-Pixel (x,y,w,h), however,
        #      most of windows would be rendered smaller than the given value.
        #   2. ideally, we want windows to be rendered in exact size we specified.
        #      the only way I found is to get the actual size by `dwmapi` and
        #      compensate the difference. however `DwmGetWindowAttribute` works in
        #      Physical-Pixel, it must be scaled

        scale_factor = monitor.get_scale_factor().value / 100
        wr = monitor.get_info().rcWork
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self._state[monitor]
        i = 0
        for (left, top, right, bottom) in self.current_layout_tiler(
            work_area, len(windows)
        ):
            window = windows[i]
            # add gap
            if self.gap:
                if left == wr.left:
                    left += self.gap
                if top == wr.top:
                    top += self.gap
                if right == wr.right:
                    right -= self.gap
                if bottom == wr.bottom:
                    bottom -= self.gap
            left += self.gap
            top += self.gap
            right -= self.gap
            bottom -= self.gap
            # compensation
            r = window.get_rect()
            b = window.get_extended_frame_bounds()
            compensated_rect = (
                round(left + r.left - (b.left / scale_factor)),
                round(top + r.top - (b.top / scale_factor)),
                round(right + r.right - (b.right / scale_factor)),
                round(bottom + r.bottom - (b.bottom / scale_factor)),
            )

            window.set_rect(RECT(*compensated_rect))
            i += 1

    def arrange_monitor_by_window(self, window: Window):
        """Arrange the monitor that owns specified window"""
        m = get_monitor_from_window(window.handle)
        self.arrange_monitor(m)

    def arrange_all_monitors(self):
        for monitor in self._state:
            self.arrange_monitor(monitor)

    @property
    def current_layout_tiler(self) -> LayoutTiler:
        """Retrieves current layout tiler function"""
        return self.layout_tilers[self.current_layout_tiler_index]

    @property
    def current_active_window(self) -> Optional[Window]:
        """Retrivevs current active managed window"""
        window = get_active_window()
        if window is None:
            return None
        if window not in self.managed_windows:
            return None
        return window

    @property
    def last_active_window(self) -> Optional[Window]:
        """Retrieves last activated window"""
        if self._last_active_window and (
            self._last_active_window not in self.managed_windows
            or not self._last_active_window.exists
        ):
            return None
        return self._last_active_window

    def find_owner_and_index(self, window: Window) -> Tuple[List[Window], int]:
        """Retrieves the windows list containing specified window and its index in the list"""
        monitor = get_monitor_from_window(window.handle)
        windows_list = self._state[monitor]
        index = windows_list.index(window)
        return windows_list, index

    def activate(self, window: Window):
        window.activate()
        # move cursor to the center of the window
        rect = window.get_rect()
        set_cursor_pos(
            rect.left + (rect.right - rect.left) / 2,
            rect.top + (rect.bottom - rect.top) / 2,
        )
        self._last_active_window = window

    def activate_by_offset(self, offset: int):
        """Activate managed window by offset

        When the active window is managed, activate window in the same monitor by offset
        When the active window is unmanaged, activate the last active window
        When none of above viable, activate the Master window in the montior under cursor
        Or, do nothing!
        """
        src_window = self.current_active_window
        dst_window = None
        if src_window:
            windows_list, src_index = self.find_owner_and_index(src_window)
            if len(windows_list) > 0:
                dst_index = (src_index + offset) % len(windows_list)
                dst_window = windows_list[dst_index]
        else:
            dst_window = self.last_active_window
        if not dst_window:
            monitor = get_monitor_from_cursor()
            windows_list = self._state[monitor]
            if len(windows_list) > 0:
                dst_window = windows_list[0]
        if not dst_window:
            return
        self.activate(dst_window)

    def activate_next(self):
        """Activate the managed window next to the last activated managed window"""
        self.activate_by_offset(+1)

    def activate_prev(self):
        """Activate the managed window prior to the last activated managed window"""
        self.activate_by_offset(-1)

    def swap_by_offset(self, offset: int):
        """Swap current active managed window with its sibling by offset"""
        src_window = self.current_active_window
        if not src_window:
            return
        l, src_idx = self.find_owner_and_index(src_window)
        if len(l) < 2:
            return
        dst_idx = (src_idx + offset) % len(l)
        l[src_idx], l[dst_idx] = l[dst_idx], l[src_idx]
        self.arrange_monitor_by_window(src_window)
        self.activate(src_window)

    def swap_next(self):
        """Swap the current active managed window with its next in list"""
        self.swap_by_offset(+1)

    def swap_prev(self):
        """Swap the current active managed window with its previous in list"""
        self.swap_by_offset(-1)

    def swap_master(self):
        """Swap the current active managed window with the Master or the second window
        in the list if it is Master already
        """
        src_window = self.current_active_window
        if not src_window:
            return
        l, src_idx = self.find_owner_and_index(src_window)
        if len(l) < 2:
            return
        if src_idx == 0:
            dst_idx = 1
        else:
            dst_idx = 0
        l[src_idx], l[dst_idx] = l[dst_idx], l[src_idx]
        self.arrange_monitor_by_window(src_window)
        self.activate(l[0])

    def prev_layout_tiler(self):
        self.current_layout_tiler_index = (self.current_layout_tiler_index - 1) % len(
            self.layout_tilers
        )
        self.arrange_all_monitors()

    def next_layout_tiler(self):
        self.current_layout_tiler_index = (self.current_layout_tiler_index + 1) % len(
            self.layout_tilers
        )
        self.arrange_all_monitors()


if __name__ == "__main__":
    wm = WindowManager()
    wm.sync()
    print()
    wm.sync()
