from dataclasses import dataclass
from os import path
from typing import Dict, List, Optional, Set

from jigsawwm.tiler.tilers import *
from jigsawwm.virtdeskstub import find_or_create_virtdeskstub
from jigsawwm.w32.idesktopwallpaper import desktop_wallpaper
from jigsawwm.w32.ivirtualdesktopmanager import GUID, virtual_desktop_manager
from jigsawwm.w32.monitor import (
    Monitor,
    get_monitor_from_cursor,
    get_monitor_from_window,
    get_monitors,
    get_topo_sorted_monitors,
    set_cursor_pos,
)
from jigsawwm.w32.window import (
    HWND,
    RECT,
    Window,
    get_active_window,
    get_first_app_window,
    get_foreground_window,
    get_manageable_windows,
    sprint_window,
)


@dataclass
class Theme:
    """Theme is a set of preference packed together for users to switch easily,
    typically, it consists of a LayoutTiler, Background, Gap between windows and
    other options.
    """

    # name of the theme
    name: str
    # layout tiler
    layout_tiler: LayoutTiler
    # unused
    icon_name: Optional[str] = None
    # unused
    icon_path: Optional[str] = None
    # background, color if the string starts with `#`, otherwise treated as image path
    background: Optional[str] = None
    # new appeared window would be prepended to the list if the option was set to True
    new_window_as_master: Optional[bool] = None
    # gap between windows / monitor edges
    gap: Optional[int] = None
    # forbid
    strict: Optional[bool] = None


class MonitorState:
    """MonitorState holds variables needed by a Monitor


    :param VirtDeskState virtdesk_state: associated virtual desktop
    :param Monitor monitor: associated system monitor
    :param str theme: the active theme for the monitor in the virtual desktop
    """

    virtdesk_state: "VirtDeskState"
    monitor: Monitor
    theme: Optional[str]
    windows: List[Window]
    last_active_window: Optional[Window] = None

    def __init__(
        self,
        virtdesk_state: "VirtDeskState",
        monitor: Monitor,
        theme: Optional[str] = None,
    ):
        self.virtdesk_state = virtdesk_state
        self.monitor = monitor
        self.theme = theme
        self.windows = []
        self.last_active_window = None

    def get_theme(self) -> Theme:
        """Retrieves theme for monitor in current virtual desktop"""
        mgr = self.virtdesk_state.manager
        return mgr.themes[mgr.get_theme_index(self.theme)]

    def get_existing_windows(self) -> List[Window]:
        """Retrieves current managed windows"""
        return self.windows

    def sync(self, windows: Set[Window], restrict=False):
        """Synchronize managed windows with given actual windows currently visible and arrange them accordingly

        :param Set[Window] windows: latest visible windows
        :param bool restrict: optional, restrict windows to their specified rect no matter what
        """
        theme = self.get_theme()
        old_list = self.windows
        new_list = []
        for w in old_list:
            if w not in windows:
                continue
            windows.remove(w)
            if not w.exists():
                continue
            new_list.append(w)
        # and then, prepend or append the new windows
        if theme.new_window_as_master:
            new_list = list(windows) + new_list
        else:
            new_list = new_list + list(windows)
        # skip if there is nothing changed, unless Strict mode is enable
        if new_list == old_list:
            if theme.background is not None:
                self.set_background(theme)
            if restrict:
                self.restrict(theme)
            return
        self.windows = new_list
        self.arrange(theme)

    def arrange(self, theme: Optional[Theme] = None):
        """Arrange windows based on the theme

        :param str theme: optional, fallback to theme of the instance
        """
        theme = theme or self.get_theme()
        if theme.background is not None:
            self.set_background(theme)
        scale_factor = self.monitor.get_scale_factor().value / 100
        wr = self.monitor.get_info().rcWork
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self.get_existing_windows()
        i = 0
        gap = theme.gap
        # print(work_area, theme.name, len(windows))
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
            # compensation
            r = window.get_rect()
            b = window.get_extended_frame_bounds()
            # now, here is the tricky part, thanks to the chaotic Win32 API
            #
            #   1. the `SetWindowPos` api accept Scaled-Pixel (x,y,w,h), however,
            #      most of windows would be rendered smaller than the given value.
            #   2. ideally, we want windows to be rendered in exact size we specified.
            #      the only way I found is to get the actual size by `dwmapi` and
            #      compensate the difference. however `DwmGetWindowAttribute` works in
            #      Physical-Pixel, it must be scaled
            compensated_rect = (
                round(left + r.left - (b.left / scale_factor)),
                round(top + r.top - (b.top / scale_factor)),
                round(right + r.right - (b.right / scale_factor)),
                round(bottom + r.bottom - (b.bottom / scale_factor)),
            )
            window.set_rect(RECT(*compensated_rect))
            i += 1

    def set_background(self, theme: Theme):
        """Set background for the monitor based on given theme"""
        monitors = list(get_monitors())
        idx = monitors.index(self.monitor)
        monitor_id = desktop_wallpaper.GetMonitorDevicePathAt(idx)
        desktop_wallpaper.SetWallpaper(monitor_id, theme.background)

    def restrict(self, theme: Optional[Theme] = None):
        """Restrict all managed windows to their specified rect"""
        theme = theme or self.get_theme()
        if not theme.strict:
            return
        for window in self.windows:
            window.set_rect(window.last_rect)


class VirtDeskState:
    """VirtDeskState holds variables needed by a Virtual Desktop

    :param WindowManager manager: associated WindowManager
    :param GUID desktop_id: virtual desktop id
    """

    desktop_id: GUID
    manager: "WindowManager"
    managed_windows: Set[Window]
    monitors: Dict[Monitor, MonitorState]
    last_active_window: Optional[Window] = None

    def __init__(self, manager: "WindowManager", desktop_id: GUID):
        self.desktop_id = desktop_id
        self.manager = manager
        self.managed_windows = set()
        self.monitors = {}
        self.last_active_window = None

    def get_monitor(self, monitor: Monitor) -> MonitorState:
        """Retrieves the monitor state for the specified monitor in the virtual desktop

        :param Monitor monitor: monitor
        :returns: monitor state
        :rtype: MonitorState
        """
        monitor_state = self.monitors.get(monitor)
        if monitor_state is None:
            monitor_state = MonitorState(self, monitor)
            self.monitors[monitor] = monitor_state
        return monitor_state

    def get_managed_active_window(self) -> Optional[Window]:
        """Retrieves the managed forground window if any"""
        window = get_active_window()
        if window is None:
            return None
        if window not in self.managed_windows:
            return None
        return window

    def get_last_managed_active_window(self) -> Optional[Window]:
        """Retrieves the latest managed forground window if any"""
        if self.last_active_window and (
            self.last_active_window not in self.managed_windows
            or not self.last_active_window.exists()
        ):
            return None
        return self.last_active_window

    def find_owner(self, window: Window) -> Optional[MonitorState]:
        """Retrieves the windows list containing specified window and its index in the list"""
        monitor = get_monitor_from_window(window.handle)
        monitor_state = self.get_monitor(monitor)
        if window in monitor_state.windows:
            return monitor_state
        return None


class WindowManager:
    """WindowManager detect the monitors/windows state and arrange them dynamically
    keep in mind that not all windows are managed by the WindowManager, only those
    returned by `jigsawwm.w32.get_normal_windows()` and not ignored would be managed.

    The WindowManager works just like other Dynamic Window Managers, it store all
    managed windows in a list, the first one in the list is called Master, it would
    normally take up most area of the screen while others occuppy the rest.

    :param List[Theme] themes: all avaiable themes for user to switch
    :param ignore_exe_names: list of executable filenames that you don't want them
                             to be managed/arranged
    """

    _state: Dict[GUID, VirtDeskState]
    themes: List[Theme]
    ignore_exe_names: Set[str]

    def __init__(
        self,
        themes: List[Theme] = None,
        ignore_exe_names: Set[str] = None,
    ):
        self._state = {}
        self.themes = themes or [
            Theme(
                name="WideScreen Dwindle",
                layout_tiler=widescreen_dwindle_layout_tiler,
                icon_name="wide-dwindle.png",
            ),
            Theme(
                name="OBS Dwindle",
                layout_tiler=obs_dwindle_layout_tiler,
                icon_name="obs.png",
            ),
            Theme(
                name="Dwindle",
                layout_tiler=dwindle_layout_tiler,
                icon_name="dwindle.png",
            ),
        ]
        self.ignore_exe_names = set(ignore_exe_names or [])
        self.theme = self.themes[0].name
        self.sync(init=True)

    def try_get_virtdesk_state(
        self, hwnd: Optional[HWND] = None
    ) -> Optional[VirtDeskState]:
        """Retrieve virtual desktop state without exception.
        It is likely to fail due to API limitation, i.e. pressing hotkey while
        Start Menu is activating, better to do nothing than raising exception"""
        try:
            return self.get_virtdesk_state(hwnd)
        except:
            pass

    def get_virtdesk_state(self, hwnd: Optional[HWND] = None) -> VirtDeskState:
        """Retrieve virtual desktop state"""
        # Hey, M$, why not just offer an API so we can know which virtual desktop is current active? WHY?
        proc = None
        # try to use the first app window
        if hwnd is None:
            hwnd = get_first_app_window()
        # last resort: create a temporary window ... :tears:
        if hwnd is None:
            hwnd, proc = find_or_create_virtdeskstub()

        desktop_id = None
        try:
            desktop_id = virtual_desktop_manager.GetWindowDesktopId(hwnd)
        except Exception as e:
            pass
        if desktop_id is None or desktop_id == GUID():
            wininfo = sprint_window(hwnd)
            raise Exception("invalid desktop_id\n" + wininfo)
        # print("desktop id", desktop_id)
        virtdesk_state = self._state.get(desktop_id)
        if virtdesk_state is None:
            # make sure monitor_state for current virtual desktop exists
            virtdesk_state = VirtDeskState(self, desktop_id)
            self._state[desktop_id] = virtdesk_state
        if proc:
            proc.kill()
        return virtdesk_state

    def is_ignored(self, window: Window) -> bool:
        exepath = window.exe
        return not exepath or path.basename(exepath) in self.ignore_exe_names

    def sync(self, init=False, restrict=False) -> bool:
        """Update manager state(monitors, windows) to match OS's and arrange windows if it is changed"""
        manageable_windows = list(get_manageable_windows())
        if not manageable_windows:
            return
        virtdesk_state = self.try_get_virtdesk_state(manageable_windows[0].handle)
        if not virtdesk_state:
            return
        # gather all manageable windows and group them by monitor
        group_wins_by_mons: Dict[Monitor, Set[Window]] = {}
        managed_windows = set()
        for window in manageable_windows:
            # skip certain exe file name
            if self.is_ignored(window):
                continue
            # if window was already managed, use previous monitor, or use the one under the cursor
            if init or window in virtdesk_state.managed_windows:
                monitor = get_monitor_from_window(window.handle)
            else:
                monitor = get_monitor_from_cursor()
            windows = group_wins_by_mons.get(monitor)
            if windows is None:
                windows = set()
                group_wins_by_mons[monitor] = windows
            windows.add(window)
            managed_windows.add(window)
        virtdesk_state.managed_windows = managed_windows

        # pass down to monitor_state for further synchronization
        for monitor, windows in group_wins_by_mons.items():
            monitor_state = virtdesk_state.get_monitor(monitor)
            monitor_state.sync(windows, restrict=restrict)

    def arrange_all_monitors(self):
        """Arrange all windows in all monitors to where their suppose to be"""
        virtdesk_state = self.try_get_virtdesk_state()
        if not virtdesk_state:
            return
        for monitor in virtdesk_state.monitors.values():
            monitor.arrange()

    def activate(self, window: Window):
        """Activate specified window"""
        virtdesk_state = self.try_get_virtdesk_state(window.handle)
        if not virtdesk_state:
            return
        window.activate()
        # move cursor to the center of the window
        rect = window.get_rect()
        set_cursor_pos(
            rect.left + (rect.right - rect.left) / 2,
            rect.top + (rect.bottom - rect.top) / 2,
        )
        virtdesk_state.last_active_window = window
        monitor = get_monitor_from_window(window.handle)
        virtdesk_state.get_monitor(monitor).last_active_window = window

    def activate_by_offset(self, offset: int):
        """Activate managed window by offset

        When the active window is managed, activate window in the same monitor by offset
        When the active window is unmanaged, activate the last active window
        When none of above viable, activate the Master window in the montior under cursor
        Or, do nothing!
        """
        virtdesk_state = self.try_get_virtdesk_state()
        if not virtdesk_state:
            return
        src_window = virtdesk_state.get_managed_active_window()
        dst_window = None
        if src_window:
            monitor_state = virtdesk_state.find_owner(src_window)
            if len(monitor_state.windows) > 0:
                src_index = monitor_state.windows.index(src_window)
                dst_index = (src_index + offset) % len(monitor_state.windows)
                dst_window = monitor_state.windows[dst_index]
        else:
            dst_window = virtdesk_state.last_active_window
        if not dst_window:
            monitor_state = virtdesk_state.get_monitor(get_monitor_from_cursor())
            if len(monitor_state.windows) > 0:
                dst_window = monitor_state.windows[0]
        if not dst_window:
            return
        self.activate(dst_window)

    def activate_next(self):
        """Activate the managed window next to the last activated managed window"""
        self.activate_by_offset(+1)

    def activate_prev(self):
        """Activate the managed window prior to the last activated managed window"""
        self.activate_by_offset(-1)

    def _reorder(self, reorderer: Callable[[List[Window], int], None]):
        virtdesk_state = self.try_get_virtdesk_state()
        if not virtdesk_state:
            return
        src_window = virtdesk_state.get_managed_active_window()
        if not src_window:
            return
        monitor_state = virtdesk_state.find_owner(src_window)
        if monitor_state is None:
            return
        if len(monitor_state.windows) < 2:
            return
        reorderer(monitor_state.windows, monitor_state.windows.index(src_window))
        monitor_state.arrange()
        self.activate(src_window)

    def swap_by_offset(self, offset: int):
        """Swap current active managed window with its sibling by offset"""

        def reorderer(windows: List[Window], src_idx: int):
            dst_idx = (src_idx + offset) % len(windows)
            windows[src_idx], windows[dst_idx] = windows[dst_idx], windows[src_idx]

        self._reorder(reorderer)

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

        def reorderer(windows: List[Window], src_idx: int):
            if src_idx == 0:
                dst_idx = 1
            else:
                dst_idx = 0
            windows[src_idx], windows[dst_idx] = windows[dst_idx], windows[src_idx]

        self._reorder(reorderer)

    def set_master(self):
        """Set the active active managed window as the Master or the second window
        in the list if it is Master already
        """

        def reorderer(windows: List[Window], src_idx: int):
            src_window = windows[src_idx]
            if src_idx == 0:
                src_idx = 1
                src_window = windows[1]
            # shift elements from the beginning to the src_window
            for i in reversed(range(1, src_idx + 1)):
                windows[i] = windows[i - 1]
            # assign new master
            windows[0] = src_window

        self._reorder(reorderer)

    def get_theme_index(self, theme_name: str) -> int:
        """Retrieves the index of given theme name, useful to switching theme"""
        i = len(self.themes) - 1
        while i > 0:
            if self.themes[i].name == theme_name:
                return i
            i -= 1
        return i

    def switch_theme_by_offset(self, delta: int):
        """Switch theme by offset"""
        virtdesk_state = self.try_get_virtdesk_state()
        if not virtdesk_state:
            return
        monitor = (
            get_monitor_from_window(get_foreground_window())
            or get_monitor_from_cursor()
        )
        monitor_state = virtdesk_state.get_monitor(monitor)
        theme_index = self.get_theme_index(monitor_state.theme)
        new_theme_name = self.themes[(theme_index + delta) % len(self.themes)].name
        monitor_state.theme = new_theme_name
        monitor_state.arrange()

    def prev_theme(self):
        """Switch to previous theme in the themes list"""
        self.switch_theme_by_offset(-1)

    def next_theme(self):
        """Switch to next theme in the themes list"""
        self.switch_theme_by_offset(+1)

    def get_monitor_state_pair(
        self, delta: int, virtdesk_state: Optional[VirtDeskState] = None
    ) -> Tuple[MonitorState, MonitorState]:
        """Retrieves a pair of monitor_states, from cursor and its offset in the list"""
        virtdesk_state = virtdesk_state or self.try_get_virtdesk_state()
        if not virtdesk_state:
            return
        monitors = get_topo_sorted_monitors()
        src_monitor = get_monitor_from_cursor()
        src_idx = monitors.index(src_monitor)
        dst_idx = (src_idx + delta) % len(monitors)
        dst_monitor = monitors[dst_idx]
        dst_monitor_state = virtdesk_state.get_monitor(dst_monitor)
        src_monitor_state = virtdesk_state.get_monitor(src_monitor)
        return src_monitor_state, dst_monitor_state

    def switch_monitor_by_offset(self, delta: int):
        """Switch to another monitor by given offset"""
        _, dst_monitor_state = self.get_monitor_state_pair(delta)
        window = dst_monitor_state.last_active_window
        if window is None or not window.exists():
            windows = dst_monitor_state.get_existing_windows()
            if windows:
                window = windows[0]
        if window:
            self.activate(window)
        else:
            rect = dst_monitor_state.monitor.get_info().rcWork
            set_cursor_pos(
                rect.left + (rect.right - rect.left) / 2,
                rect.top + (rect.bottom - rect.top) / 2,
            )

    def prev_monitor(self):
        """Switch to previous monitor"""
        self.switch_monitor_by_offset(-1)

    def next_monitor(self):
        """Switch to next monitor"""
        self.switch_monitor_by_offset(+1)

    def move_to_monitor_by_offset(self, delta: int):
        """Move active window to another monitor by offset"""
        virtdesk_state = self.try_get_virtdesk_state()
        if not virtdesk_state:
            return
        window = virtdesk_state.get_managed_active_window()
        if not window:
            return
        src_monitor_state, dst_monitor_state = self.get_monitor_state_pair(
            delta, virtdesk_state
        )
        idx = src_monitor_state.windows.index(window)
        src_monitor_state.windows.remove(window)
        src_monitor_state.arrange()
        dst_monitor_state.windows.append(window)
        dst_monitor_state.arrange()
        src_win_len = len(src_monitor_state.windows)
        if src_win_len:
            next_window = src_monitor_state.windows[idx % src_win_len]
            self.activate(next_window)

    def move_to_prev_monitor(self):
        """Move active window to previous monitor"""
        self.move_to_monitor_by_offset(-1)

    def move_to_next_monitor(self):
        """Move active window to next monitor"""
        self.move_to_monitor_by_offset(+1)


if __name__ == "__main__":
    wm = WindowManager()
    wm.sync()
    print()
    wm.sync()
