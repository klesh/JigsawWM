"""Window Manager Operations"""
import logging
import time
from typing import List, Callable, Optional, Iterable
from jigsawwm import ui, workers
from jigsawwm.w32 import virtdesk
from jigsawwm.w32.window import Window, top_most_window
from jigsawwm.w32.winevent import WinEvent
from jigsawwm.w32.monitor import get_topo_sorted_monitors
from .manager_core import WindowManagerCore, MonitorState
from .theme import Theme
from .config import WmConfig, WmRule

logger = logging.getLogger(__name__)

class WindowManager(WindowManagerCore):
    """Window Manager Operations"""

    def __init__(
        self,
        themes: List[Theme] = None,
        init_exe_sequence: List[List[str]] = None,
        rules: List[WmRule] = None,
    ):
        config = WmConfig(
            themes=themes,
            init_exe_sequence = init_exe_sequence or [],
            rules=rules,
        )
        self._hide_ui_thread = None
        self._ignore_events = False
        super().__init__(config)

    def activate(self, window: Window):
        """Activate specified window"""
        if not window or not window.exists():
            return
        logger.debug("activate(%s)", window)
        window.activate()

    def activate_by_offset(self, offset: int) -> Callable:
        """Activate managed window by offset

        When the active window is managed, activate window in the same monitor by offset
        When the active window is unmanaged, activate the first in the list or do nothing
        """
        active_window, monitor_state = self.get_active_tilable_window()
        if not active_window:
            monitor_state = self.get_active_monitor_state()
            if monitor_state.workspace.tilable_windows:
                self.activate(monitor_state.workspace.tilable_windows[0])
            ui.show_windows_splash(monitor_state, None)
            return self.put_hide_splash_event
        try:
            src_index = monitor_state.tilable_windows.index(active_window)
        except ValueError:
            src_index = 0
        dst_index = (src_index + offset) % len(monitor_state.tilable_windows)
        dst_window = monitor_state.tilable_windows[dst_index]
        self.activate(dst_window)
        ui.show_windows_splash(monitor_state, dst_window)
        return self.put_hide_splash_event

    def _reorder(self, reorderer: Callable[[List[Window], int], None]):
        active_window, monitor_state = self.get_active_tilable_window()
        if not active_window:
            return
        if len(monitor_state.tilable_windows) < 2:
            return
        next_active_window = reorderer(monitor_state.tilable_windows, monitor_state.tilable_windows.index(active_window))
        # monitor_state.workspace.save_state()
        monitor_state.arrange()
        self.activate(next_active_window or active_window)
        self.save_state()

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
            return windows[0]

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
            return src_window

        self._reorder(reorderer)

    def put_hide_splash_event(self):
        """Put hide splash event into the queue"""
        # hiding splash must be put into the queue due to each interested events are proccessed with delay
        logger.info("put hide splash event")
        # delay it a little bit because keys release event might happen before the splash is shown
        def wrapped():
            self._queue.put_nowait((WinEvent.EVENT_HIDE_SPLASH, None, time.time()))
        workers.submit_with_delay(wrapped, 0.2)

    def switch_theme_by_offset(self, delta: int) -> Callable:
        """Switch theme by offset"""
        logger.info("switching theme by offset: %s", delta)
        monitor_state = self.get_active_monitor_state()
        theme_index = self.config.get_theme_index(monitor_state.theme.name)
        theme = self.config.themes[(theme_index + delta) % len(self.config.themes)]
        monitor_state.set_theme(theme)
        self.save_state()
        ui.show_windows_splash(monitor_state, None)
        return self.put_hide_splash_event

    def get_monitor_state_by_offset(self, delta: int, src_monitor_state: Optional[MonitorState]=None) -> MonitorState:
        """Retrieves a pair of monitor_states, the current active one and its offset in the list"""
        if not src_monitor_state:
            src_monitor_state = self.get_active_monitor_state()
        monitors = get_topo_sorted_monitors()
        src_idx = monitors.index(src_monitor_state.monitor)
        dst_idx = (src_idx + delta) % len(monitors)
        dst_monitor = monitors[dst_idx]
        dst_monitor_state = self.virtdesk_state.get_monitor_state(dst_monitor)
        return dst_monitor_state

    def activate_top_most_window(self, windows: Iterable[Window]) -> bool:
        """Activate the top most window in the list"""
        window = top_most_window(windows)
        if window:
            self.activate(window)
            return True
        return False

    def switch_monitor_by_offset(self, delta: int):
        """Switch to another monitor by given offset"""
        logger.debug("switch_monitor_by_offset: %s", delta)
        src_monitor_state = self.get_active_monitor_state()
        dst_monitor_state = self.get_monitor_state_by_offset(delta, src_monitor_state=src_monitor_state)
        self._ignore_events = True
        src_monitor_state.workspace.on_unfocus()
        dst_monitor_state.workspace.on_focus()
        self._ignore_events = False

    def move_to_monitor_by_offset(self, delta: int):
        """Move active window to another monitor by offset"""
        logger.debug("move_to_monitor_by_offset(%s)", delta)
        active_window, src_monitor_state = self.get_active_window()
        if not active_window:
            return
        dst_monitor_state = self.get_monitor_state_by_offset(delta, src_monitor_state)
        src_monitor_state.remove_window(active_window)
        dst_monitor_state.add_window(active_window)
        self.activate_top_most_window(src_monitor_state.windows)
        self.save_state()

    def switch_workspace(self, workspace_index: int, monitor_name: str = None, hide_splash_in: Optional[float] = None) -> Callable:
        """Switch to a specific workspace"""
        logger.debug("switch workspace to %d", workspace_index)
        if monitor_name:
            monitor_state = self.virtdesk_state.get_monitor_state_by_name(monitor_name)
        else:
            monitor_state = self.get_active_monitor_state()
        if monitor_state.active_workspace_index == workspace_index:
            return
        self._ignore_events = True
        monitor_state.switch_workspace(workspace_index)
        self._ignore_events = False
        logger.debug("show_windows_splash")
        self.save_state()
        ui.show_windows_splash(monitor_state, None)
        if hide_splash_in:
            logger.debug("hide splash in %s", hide_splash_in)
            workers.submit_with_delay(self.put_hide_splash_event, hide_splash_in)
            return None
        return self.put_hide_splash_event

    def move_to_workspace(self, workspace_index: int):
        """Move active window to a specific workspace"""
        active_window, src_monitor_state = self.get_active_window()
        if not active_window:
            return
        self._ignore_events = True
        src_monitor_state.move_to_workspace(active_window, workspace_index)
        self._ignore_events = False
        self.save_state()

    def prev_theme(self):
        """Switch to previous theme in the themes list"""
        self.switch_theme_by_offset(-1)

    def next_theme(self) -> Callable:
        """Switch to next theme in the themes list"""
        return self.switch_theme_by_offset(+1)

    def activate_next(self) -> Callable:
        """Activate the managed window next to the last activated managed window"""
        return self.activate_by_offset(+1)

    def activate_prev(self) -> Callable:
        """Activate the managed window prior to the last activated managed window"""
        return self.activate_by_offset(-1)

    def swap_next(self):
        """Swap the current active managed window with its next in list"""
        self.swap_by_offset(+1)

    def swap_prev(self):
        """Swap the current active managed window with its previous in list"""
        self.swap_by_offset(-1)

    def prev_monitor(self):
        """Switch to previous monitor"""
        self.switch_monitor_by_offset(-1)

    def next_monitor(self):
        """Switch to next monitor"""
        self.switch_monitor_by_offset(+1)

    def move_to_prev_monitor(self):
        """Move active window to previous monitor"""
        self.move_to_monitor_by_offset(-1)

    def move_to_next_monitor(self):
        """Move active window to next monitor"""
        self.move_to_monitor_by_offset(+1)

    def move_to_desktop(self, desktop_number: int, window: Optional[Window] = None):
        """Move active window to another virtual desktop"""
        virtdesk.move_to_desktop(desktop_number, window)
        self.sync_windows()
        self.save_state()

    def switch_desktop(self, desktop_number: int):
        """Switch to another virtual desktop"""
        virtdesk.switch_desktop(desktop_number)
        self.sync_windows()

    def toggle_tilable(self):
        """Toggle the active window between tilable and floating state"""
        active_window, _ = self.get_active_window()
        if not active_window:
            return
        active_window.is_tilable = not active_window.is_tilable
        logger.info("toggle window %s tilable state to %s", active_window, active_window.is_tilable)
        # shrink the window a little bit to avoid covering tialbe windows
        if not active_window.is_tilable:
            active_window.unrestrict()
            active_window.shrink()
        self.sync_windows()
        self.save_state()