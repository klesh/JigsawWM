"""Window Manager Operations"""
import logging
import time
import pickle
import os
from typing import List, Callable, Optional
from threading import Thread

from jigsawwm import ui
from jigsawwm.w32 import hook
from jigsawwm.w32.window import Window, HWND, LONG, DWORD, get_active_window, replace_seen_windows
from jigsawwm.w32.monitor import get_topo_sorted_monitors
from jigsawwm.w32.winevent import WinEvent

from .manager_core import WindowManagerCore, MonitorState, MONITOR_STATE
from .theme import Theme
from .config import WmConfig, WmRule

logger = logging.getLogger(__name__)

class WindowManager(WindowManagerCore):
    """WindowManager detect the monitors/windows state and arrange them dynamically

    The WindowManager works just like other Dynamic Window Managers, it store all
    managed windows in a list, the first one in the list is the Master, it would
    normally take up most area of the screen while others occuppy the rest.

    :param List[Theme] themes: all avaiable themes for user to switch
    :param ignore_exe_names: list of executable filenames that you don't want them
                             to be managed/arranged
    :param init_exe_sequence: list of executable filenames and title search criteria
                              that are to be kept in exactly this order when
                              distributing into windows
    """
    _hook_ids: List[int] = []

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
        config.prepare()
        super().__init__(config)

    def start(self):
        """Start the WindowManagerCore service"""
        # load windows state from the last session
        self.load_state()
        self.sync_windows()
        self._consumer = Thread(target=self._consume_events)
        self._consumer.start()
        self.install_hooks()

    def load_state(self):
        """Load the windows state"""
        logger.info("loading state")
        if os.path.exists(self.DEFAULT_STATE_PATH):
            with open(self.DEFAULT_STATE_PATH, "rb") as f:
                try:
                    virtdesk_states, seen_windows, managed_windows, monitors = pickle.load(f)
                    replace_seen_windows({hwnd: window for hwnd, window in seen_windows.items() if window.exists()})
                    self._managed_windows = {w for w in managed_windows if w.exists()}
                    self.virtdesk_states = virtdesk_states
                    self._monitors = monitors
                    logger.info("load windows states from the last session")
                except: # pylint: disable=bare-except
                    logger.exception("load windows states error", exc_info=True)
                    return
            for virtdesk_state in self.virtdesk_states.values():
                virtdesk_state.update_config(self.config)
        else:
            logger.info("nothing from the last session")
        self.sync_windows()

    def stop(self):
        """Stop the WindowManagerCore service"""
        ui.on_screen_changed(None)
        self.uninstall_hooks()
        self.enqueue(WinEvent.CMD_EXIT)
        self._consumer.join()

    def install_hooks(self):
        """Install hooks for window events"""
        self._hook_ids = [
            hook.hook_winevent(
                WinEvent.EVENT_MIN,
                WinEvent.EVENT_MAX,
                self._winevent_callback,
            ),
        ]
        ui.on_screen_changed(self._screen_changed_callback)

    def uninstall_hooks(self):
        """Uninstall hooks for window events"""
        ui.on_shell_window_changed(None)
        for hook_id in self._hook_ids:
            hook.unhook_winevent(hook_id)
        self._hook_ids = []
        self.unhide_workspaces()

    def enqueue(self, evt: WinEvent, *args):
        """Enqueue event without blocking"""
        self._queue.put_nowait((evt, args, time.time()))

    def _screen_changed_callback(self):
        # wait a little bit for monitors to be ready
        self.enqueue(WinEvent.EVENT_SCREEN_CHANGED)

    def _winevent_callback(
        self,
        event: WinEvent,
        hwnd: HWND,
        _id_obj: LONG,
        _id_chd: LONG,
        _id_evt_thread: DWORD,
        _evt_time: DWORD,
    ):
        self.enqueue(event, hwnd)

    def activate_by_offset(self, offset: int) -> Callable:
        """Activate managed window by offset

        When the active window is managed, activate window in the same monitor by offset
        When the active window is unmanaged, activate the first in the list or do nothing
        """
        window = get_active_window()
        if not window or not window.exists() or not window.manageable or not window.tilable:
            monitor_state = self.virtdesk_state.monitor_state_from_cursor()
            if monitor_state.tilable_windows:
                window = monitor_state.tilable_windows[0]
            else:
                return
        monitor_state: MonitorState = window.attrs["monitor_state"]
        monitor_state: MonitorState = window.attrs["monitor_state"]
        src_index = monitor_state.tilable_windows.index(window)
        dst_index = (src_index + offset) % len(monitor_state.tilable_windows)
        dst_window = monitor_state.tilable_windows[dst_index]
        dst_window.activate()
        ui.show_windows_splash(monitor_state, monitor_state.active_workspace_index, dst_window)
        return ui.hide_windows_splash

    def swap_by_offset(self, offset: int):
        """Swap current active managed window with its sibling by offset"""

        def reorderer(windows: List[Window], src_idx: int):
            dst_idx = (src_idx + offset) % len(windows)
            windows[src_idx], windows[dst_idx] = windows[dst_idx], windows[src_idx]

        self.enqueue(WinEvent.CMD_CALL, self._reorder, reorderer)

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

        self.enqueue(WinEvent.CMD_CALL, self._reorder, reorderer)

    def switch_theme_by_offset(self, delta: int) -> Callable:
        """Switch theme by offset"""
        logger.info("switching theme by offset: %s", delta)
        monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        theme_index = self.config.get_theme_index(monitor_state.theme.name)
        theme = self.config.themes[(theme_index + delta) % len(self.config.themes)]
        self.enqueue(WinEvent.CMD_CALL, self._set_theme, monitor_state, theme)
        ui.show_windows_splash(self.virtdesk_state.monitor_state_from_cursor(), None)
        return ui.hide_windows_splash

    def get_monitor_state_by_offset(self, delta: int, src_monitor_state: Optional[MonitorState]=None) -> MonitorState:
        """Retrieves a pair of monitor_states, the current active one and its offset in the list"""
        if not src_monitor_state:
            src_monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        monitors = get_topo_sorted_monitors()
        src_idx = monitors.index(src_monitor_state.monitor)
        dst_idx = (src_idx + delta) % len(monitors)
        dst_monitor = monitors[dst_idx]
        dst_monitor_state = self.virtdesk_state.monitor_state(dst_monitor)
        return dst_monitor_state

    def switch_monitor_by_offset(self, delta: int):
        """Switch to another monitor by given offset"""
        logger.debug("switch_monitor_by_offset: %s", delta)
        src_monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        dst_monitor_state = self.get_monitor_state_by_offset(delta, src_monitor_state=src_monitor_state)
        src_monitor_state.workspace.before_hide()
        dst_monitor_state.workspace.after_show()
        ui.show_windows_splash(dst_monitor_state, dst_monitor_state.active_workspace_index, dst_monitor_state.workspace.last_active_window)
        return ui.hide_windows_splash

    def move_to_monitor_by_offset(self, delta: int):
        """Move active window to another monitor by offset"""
        logger.debug("move_to_monitor_by_offset(%s)", delta)
        window = get_active_window()
        if not window or not window.manageable:
            return
        monitor_state: MonitorState = window.attrs[MONITOR_STATE]
        dst_monitor_state = self.get_monitor_state_by_offset(delta, monitor_state)
        if monitor_state == dst_monitor_state:
            return
        self.enqueue(WinEvent.CMD_CALL, self._move_to_monitor, monitor_state, window, dst_monitor_state)

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
        return self.switch_monitor_by_offset(-1)

    def next_monitor(self):
        """Switch to next monitor"""
        return self.switch_monitor_by_offset(+1)

    def move_to_prev_monitor(self):
        """Move active window to previous monitor"""
        self.move_to_monitor_by_offset(-1)

    def move_to_next_monitor(self):
        """Move active window to next monitor"""
        self.move_to_monitor_by_offset(+1)

    # def move_to_desktop(self, desktop_number: int, window: Optional[Window] = None):
    #     """Move active window to another virtual desktop"""
    #     virtdesk.move_to_desktop(desktop_number, window)
    #     self.sync_windows()
    #     self.save_state()

    # def switch_desktop(self, desktop_number: int):
    #     """Switch to another virtual desktop"""
    #     virtdesk.switch_desktop(desktop_number)
    #     self.sync_windows()

    def toggle_tilable(self):
        """Toggle the active window between tilable and floating state"""
        window = get_active_window()
        if not window or not window.manageable:
            return
        self.enqueue(WinEvent.CMD_CALL, self._toggle_tilable, window)

    def move_to_workspace(self, workspace_index: int):
        """Move active window to a specific workspace"""
        window  = get_active_window()
        if not window or not window.manageable:
            return
        self.enqueue(WinEvent.CMD_CALL, self._move_to_workspace, window, workspace_index)

    def switch_workspace(self, workspace_index: int, monitor_name: str = None, hide_splash_in: Optional[float] = None) -> Callable:
        """Switch to a specific workspace"""
        monitor_state = (
            self.virtdesk_state.monitor_state_by_name(monitor_name)
            if monitor_name
            else self.virtdesk_state.monitor_state_from_cursor()
        )
        ui.show_windows_splash(monitor_state, workspace_index, None)
        self.enqueue(WinEvent.CMD_CALL, self._switch_workspace, monitor_state, workspace_index, hide_splash_in)
        if not hide_splash_in:
            return ui.hide_windows_splash

    def unhide_workspaces(self):
        """Unhide all workspaces"""
        for virtdesk_state in self.virtdesk_states.values():
            for monitor_state in virtdesk_state.monitor_states.values():
                logger.info("unhiding monitor %s", monitor_state.monitor)
                monitor_state.unhide_workspaces()