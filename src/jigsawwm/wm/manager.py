import logging
from functools import partial
from os import path
from typing import Dict, List, Optional, Set

from jigsawwm import ui
from jigsawwm.tiler.tilers import *
from jigsawwm.w32 import hook
from jigsawwm.w32.monitor import (
    Monitor,
    get_monitor_from_cursor,
    get_monitor_from_window,
    get_topo_sorted_monitors,
    set_cursor_pos,
)
from jigsawwm.w32.reg import get_current_desktop_id
from jigsawwm.w32.window import (
    DWORD,
    HWND,
    LONG,
    Window,
    get_foreground_window,
    get_manageable_windows,
    get_window_from_pos,
    get_window_title,
    is_app_window,
    is_window,
)
from jigsawwm.w32.winevent import WinEvent

from .op_mixin import OpMixin
from .state import MonitorState, VirtDeskState
from .theme import Theme

logger = logging.getLogger(__name__)


class WindowManager(OpMixin):
    """WindowManager detect the monitors/windows state and arrange them dynamically
    keep in mind that not all windows are managed by the WindowManager, only those
    returned by `jigsawwm.w32.get_normal_windows()` and not ignored would be managed.

    The WindowManager works just like other Dynamic Window Managers, it store all
    managed windows in a list, the first one in the list is called Master, it would
    normally take up most area of the screen while others occuppy the rest.

    :param List[Theme] themes: all avaiable themes for user to switch
    :param ignore_exe_names: list of executable filenames that you don't want them
                             to be managed/arranged
    :param init_exe_sequence: list of executable filenames and title search criteria
                              that are to be kept in exactly this order when
                              distributing into windows
    """

    _state: Dict[bytearray, VirtDeskState]
    themes: List[Theme]
    ignore_exe_names: Set[str]
    force_managed_exe_names: Set[str]
    init_exe_sequence: List[List[str]]

    def __init__(
        self,
        themes: List[Theme] = None,
        ignore_exe_names: Set[str] = None,
        force_managed_exe_names: Set[str] = None,
        init_exe_sequence: List[List[str]] = None,
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
        self.force_managed_exe_names = set(force_managed_exe_names or [])
        self.init_exe_sequence = init_exe_sequence or []
        self.theme = self.themes[0].name
        self.sync(init=True)

    @property
    def virtdesk_state(self) -> Optional[VirtDeskState]:
        """Retrieve virtual desktop state"""
        desktop_id = get_current_desktop_id()
        virtdesk_state = self._state.get(desktop_id)
        if virtdesk_state is None:
            # make sure monitor_state for current virtual desktop exists
            virtdesk_state = VirtDeskState(
                lambda theme: self.themes[self.get_theme_index(theme)], desktop_id
            )
            self._state[desktop_id] = virtdesk_state
        return virtdesk_state

    def check_window_ignored(self, window: Window) -> bool:
        exepath = window.exe
        return not exepath or path.basename(exepath) in self.ignore_exe_names

    def check_force_managed(self, hwnd: HWND) -> bool:
        try:
            exepath = Window(hwnd).exe
            return exepath and path.basename(exepath) in self.force_managed_exe_names
        except:
            return False

    def sync(self, init=False, restrict=False) -> bool:
        """Update manager state(monitors, windows) to match OS's and arrange windows if it is changed"""

        virtdesk_state = self.virtdesk_state


        #
        # gather all manageable windows
        #

        manageable_windows = list(get_manageable_windows(self.check_force_managed))
        if not manageable_windows:
            return


        #
        # group manageable windows by their current monitor
        #

        group_wins_by_mons: Dict[Monitor, Set[Window]] = {}
        managed_windows = set()
        for window in manageable_windows:


            #
            # skip this window if to be ignored
            #

            if self.check_window_ignored(window):
                continue


            #
            # determine relevant monitor
            #

            if init or window in virtdesk_state.managed_windows:

                # use previous monitor
                monitor = get_monitor_from_window(window.handle)

            else:
                # use the monitor currently showing the cursor
                monitor = get_monitor_from_cursor()


            #
            # build list of windows for each monitor
            #

            # get current list of windows for relevant monitor
            windows = group_wins_by_mons.get(monitor)

            # init list if not yet existing
            if windows is None:
                windows = set()
                group_wins_by_mons[monitor] = windows

            # add window to lists
            windows.add(window)
            managed_windows.add(window)
            logger.debug("%s is managed by monitor %s", window, monitor)


        #
        # synchronize windows on each monitor
        #

        virtdesk_state.managed_windows = managed_windows

        # pass down to monitor_state for further synchronization
        for monitor, windows in group_wins_by_mons.items():
            monitor_state = virtdesk_state.get_monitor(monitor)
            monitor_state.sync(
                    windows,
                    restrict=restrict,
                    #window_sort_order=self.init_exe_sequence if init else [],
                    window_sort_order=self.init_exe_sequence,
                    )

    def arrange_all_monitors(self):
        """Arrange all windows in all monitors to where their suppose to be"""
        virtdesk_state = self.virtdesk_state
        for monitor in virtdesk_state.monitors.values():
            monitor.arrange()

    def activate(self, window: Window):
        """Activate specified window"""
        virtdesk_state = self.virtdesk_state
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
        virtdesk_state = self.virtdesk_state
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
        ui.show_windows_splash(monitor_state, dst_window)

    def _reorder(self, reorderer: Callable[[List[Window], int], None]):
        virtdesk_state = self.virtdesk_state
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
        try:
            virtdesk_state = self.virtdesk_state
            monitor = (
                get_monitor_from_window(get_foreground_window())
                or get_monitor_from_cursor()
            )
            monitor_state = virtdesk_state.get_monitor(monitor)
            theme_index = self.get_theme_index(monitor_state.theme)
            theme = self.themes[(theme_index + delta) % len(self.themes)]
            # new_theme_name = self.themes[(theme_index + delta) % len(self.themes)].name
            monitor_state.theme = theme.name
            monitor_state.arrange(theme)
        except:
            import traceback

            traceback.print_exc()

    def get_monitor_state_pair(
        self, delta: int, virtdesk_state: Optional[VirtDeskState] = None, window: Optional[Window]=None
    ) -> Tuple[MonitorState, MonitorState]:
        """Retrieves a pair of monitor_states, from cursor and its offset in the list"""
        virtdesk_state = virtdesk_state or self.virtdesk_state
        if not virtdesk_state:
            return
        monitors = get_topo_sorted_monitors()
        src_monitor = get_monitor_from_window(window.handle) if window else get_monitor_from_cursor()
        src_idx = monitors.index(src_monitor)
        dst_idx = (src_idx + delta) % len(monitors)
        dst_monitor = monitors[dst_idx]
        dst_monitor_state = virtdesk_state.get_monitor(dst_monitor)
        src_monitor_state = virtdesk_state.get_monitor(src_monitor)
        return src_monitor_state, dst_monitor_state

    def switch_monitor_by_offset(self, delta: int):
        """Switch to another monitor by given offset"""
        logger.debug("switch_monitor_by_offset: %s", delta)
        _, dst_monitor_state = self.get_monitor_state_pair(delta)
        rect = dst_monitor_state.monitor.get_info().rcWork
        x, y = (
            rect.left + (rect.right - rect.left) / 2,
            rect.top + (rect.bottom - rect.top) / 2,
        )
        set_cursor_pos(x, y)
        window = get_window_from_pos(x, y)
        if not window:
            window = dst_monitor_state.last_active_window
        if window is None or not window.exists():
            windows = dst_monitor_state.get_existing_windows()
            if windows:
                window = windows[0]
        if window:
            self.activate(window)

    def move_to_monitor_by_offset(self, delta: int):
        """Move active window to another monitor by offset"""
        logger.debug("move_to_monitor_by_offset(%s)", delta)
        virtdesk_state = self.virtdesk_state
        window = virtdesk_state.get_managed_active_window()
        if not window:
            return
        src_monitor_state, dst_monitor_state = self.get_monitor_state_pair(
            delta, virtdesk_state, window,
        )
        src_monitor_state.windows.remove(window)
        src_monitor_state.arrange()
        dst_monitor_state.windows.append(window)
        dst_monitor_state.arrange()
        # idx = src_monitor_state.windows.index(window)
        # src_win_len = len(src_monitor_state.windows)
        # if src_win_len:
        #     next_window = src_monitor_state.windows[idx % src_win_len]
        #     self.activate(next_window)
        self.activate(window)

    def _winevent_callback(
        self,
        event: WinEvent,
        hwnd: HWND,
        id_obj: LONG,
        id_chd: LONG,
        id_evt_thread: DWORD,
        evt_time: DWORD,
        restrict: bool = False,
    ):
        if (
            id_obj
            or id_chd
            or not is_window(hwnd)
            or not is_app_window(hwnd)
            or self.check_window_ignored(Window(hwnd))
        ):
            return
        logger.debug(
            "_winevent_callback: event %s restrict %s %s",
            event.name,
            restrict,
            get_window_title(hwnd),
        )
        self.sync(restrict=restrict)

    def install_hooks(self):
        """Install hooks for window events"""
        self.hook_ids = [
            hook.hook_winevent(
                WinEvent.EVENT_OBJECT_SHOW,
                WinEvent.EVENT_OBJECT_HIDE,
                self._winevent_callback,
            ),
            hook.hook_winevent(
                WinEvent.EVENT_OBJECT_CLOAKED,
                WinEvent.EVENT_OBJECT_UNCLOAKED,
                self._winevent_callback,
            ),
            hook.hook_winevent(
                WinEvent.EVENT_SYSTEM_MINIMIZESTART,
                WinEvent.EVENT_SYSTEM_MINIMIZEEND,
                self._winevent_callback,
            ),
            hook.hook_winevent(
                WinEvent.EVENT_SYSTEM_MOVESIZEEND,
                WinEvent.EVENT_SYSTEM_MOVESIZEEND,
                partial(self._winevent_callback, restrict=True),
            ),
            # hook.hook_winevent(
            #     WinEvent.EVENT_SYSTEM_FOREGROUND,
            #     WinEvent.EVENT_SYSTEM_FOREGROUND,
            #     partial(self._winevent_callback, restrict=True),
            # ),
        ]

    def uninstall_hooks(self):
        for hook_id in self.hook_ids:
            hook.unhook_winevent(hook_id)
        self.hook_ids = []


if __name__ == "__main__":
    wm = WindowManager()
    wm.sync()
    print()
    wm.sync()
