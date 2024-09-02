"""Window Manager Operations"""

import logging
import pickle
import os
import time
from typing import Dict, List, Callable, Optional
from ctypes.wintypes import HWND, LONG, DWORD

from jigsawwm.ui import Splash, app
from jigsawwm.w32 import hook
from jigsawwm.w32.winevent import WinEvent
from jigsawwm.w32.reg import get_current_desktop_id
from jigsawwm.w32.window import Window
from jigsawwm.worker import ThreadWorker

from .theme import Theme
from .config import WmConfig, WmRule
from .virtdesk_state import VirtDeskState, MonitorState, WorkspaceState
from .debug_state import inspect_virtdesk_states
from .const import MONITOR_STATE, WORKSPACE_STATE


logger = logging.getLogger(__name__)


class WindowManager(ThreadWorker):
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

    DEFAULT_STATE_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "jigsawwm", "wm.state")
    _hook_ids: List[int] = []
    virtdesk_states: Dict[bytearray, VirtDeskState]
    config: WmConfig
    splash: Splash

    def __init__(
        self,
        themes: List[Theme] = None,
        rules: List[WmRule] = None,
    ):
        config = WmConfig(
            themes=themes,
            rules=rules,
        )
        config.prepare()
        self.config = config
        self.virtdesk_states = {}
        self.splash = Splash()

    def start(self):
        """Start the WindowManagerCore service"""
        # load windows state from the last session
        # self.load_state()
        self.virtdesk_state.sync_monitors()
        self.virtdesk_state.sync_windows()
        self.start_worker()
        self.install_hooks()

    def stop(self):
        """Stop the WindowManagerCore service"""
        self.uninstall_hooks()
        self.stop_worker()
        self.unhide_workspaces()

    def install_hooks(self):
        """Install hooks for window events"""
        self._hook_ids = [
            hook.hook_winevent(
                WinEvent.EVENT_MIN,
                WinEvent.EVENT_MAX,
                self._window_event_proc,
            ),
        ]
        app.screenAdded.connect(self._screen_event_proc)
        app.screenRemoved.connect(self._screen_event_proc)

    def _screen_event_proc(self):
        # wait a little bit for monitors to be ready
        self.enqueue(self.on_screen_event, time.time())

    def _window_event_proc(
        self,
        event: WinEvent,
        hwnd: HWND,
        _id_obj: LONG,
        _id_chd: LONG,
        _id_evt_thread: DWORD,
        _evt_time: DWORD,
    ):
        self.enqueue(self.on_window_event, event, hwnd, time.time())

    def uninstall_hooks(self):
        """Uninstall hooks for window events"""
        app.screenAdded.disconnect(self._screen_event_proc)
        app.screenRemoved.disconnect(self._screen_event_proc)
        for hook_id in self._hook_ids:
            hook.unhook_winevent(hook_id)
        self._hook_ids = []

    def save_state(self):
        """Save the windows state"""
        logger.info("saving state")
        with open(self.DEFAULT_STATE_PATH, "wb") as f:
            pickle.dump(self.virtdesk_states)

    def load_state(self):
        """Load the windows state"""
        logger.info("loading state")
        if os.path.exists(self.DEFAULT_STATE_PATH):
            with open(self.DEFAULT_STATE_PATH, "rb") as f:
                try:
                    self.virtdesk_states = pickle.load(f)
                    logger.info("load windows states from the last session")
                except:  # pylint: disable=bare-except
                    logger.exception("load windows states error", exc_info=True)
                    return
            for virtdesk_state in self.virtdesk_states.values():
                virtdesk_state.update_config(self.config)
        else:
            logger.info("nothing from the last session")

    @property
    def virtdesk_state(self) -> VirtDeskState:
        """Retrieve virtual desktop state"""
        desktop_id = get_current_desktop_id()
        virtdesk_state = self.virtdesk_states.get(desktop_id)
        if virtdesk_state is None:
            # make sure monitor_state for current virtual desktop exists
            virtdesk_state = VirtDeskState(desktop_id, self.config)
            self.virtdesk_states[desktop_id] = virtdesk_state
        return virtdesk_state

    def sleep_till(self, ts: float):
        """Sleep till the timestamp"""
        span = ts - time.time()
        if span > 0:
            time.sleep(span)

    def on_screen_event(self, ts: float):
        """Handle screen event"""
        self.sleep_till(ts + 0.5)
        self.virtdesk_state.sync_monitors()

    def on_window_event(self, event: WinEvent, hwnd: HWND, ts: float):
        """Handle the winevent"""
        self.sleep_till(ts + 0.2)
        self.virtdesk_state.on_window_event(event, hwnd)

    def activate_by_offset(self, delta: int) -> Callable:
        """Activate managed window by offset

        When the active window is managed, activate window in the same monitor by offset
        When the active window is unmanaged, activate the first in the list or do nothing
        """
        window = self.virtdesk_state.window_detector.foreground_window()
        if not window.manageable or not window.tilable:
            return
        monitor_state: MonitorState = window.attrs[MONITOR_STATE]
        workspace_state: WorkspaceState = window.attrs[WORKSPACE_STATE]
        src_index = workspace_state.tiling_windows.index(window)
        dst_index = (src_index + delta) % len(workspace_state.tiling_windows)
        dst_window = workspace_state.tiling_windows[dst_index]
        dst_window.activate()
        self.splash.show_splash.emit(
            monitor_state, monitor_state.active_workspace_index, dst_window
        )
        return self.splash.hide_splash.emit

    def swap_by_offset(self, offset: int):
        """Swap current active managed window with its sibling by offset"""

        def reorderer(windows: List[Window], src_idx: int):
            dst_idx = (src_idx + offset) % len(windows)
            windows[src_idx], windows[dst_idx] = windows[dst_idx], windows[src_idx]

        self.enqueue(self.virtdesk_state.reorder, reorderer)

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

        self.enqueue(self.virtdesk_state.reorder, reorderer)

    def switch_theme_by_offset(self, delta: int) -> Callable:
        """Switch theme by offset"""
        logger.info("switching theme by offset: %s", delta)
        monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        theme_index = self.config.get_theme_index(monitor_state.theme.name)
        theme = self.config.themes[(theme_index + delta) % len(self.config.themes)]
        self.enqueue(monitor_state.workspace.set_theme, theme)
        self.splash.show_splash.emit(
            monitor_state, monitor_state.active_workspace_index, None
        )
        return self.splash.hide_splash.emit

    def get_monitor_state_by_offset(
        self, delta: int, src_monitor_state: Optional[MonitorState] = None
    ) -> MonitorState:
        """Retrieves a pair of monitor_states, the current active one and its offset in the list"""
        if not src_monitor_state:
            src_monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        monitors = self.virtdesk_state.monitor_detector.monitors
        src_idx = monitors.index(src_monitor_state.monitor)
        dst_idx = (src_idx + delta) % len(monitors)
        dst_monitor = monitors[dst_idx]
        dst_monitor_state = self.virtdesk_state.monitor_state(dst_monitor)
        return dst_monitor_state

    def switch_monitor_by_offset(self, delta: int):
        """Switch to another monitor by given offset"""
        logger.debug("switch_monitor_by_offset: %s", delta)
        src_monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        dst_monitor_state = self.get_monitor_state_by_offset(
            delta, src_monitor_state=src_monitor_state
        )
        self.splash.show_splash.emit(
            dst_monitor_state, dst_monitor_state.active_workspace_index, None
        )
        return self.splash.hide_splash.emit

    def move_to_monitor_by_offset(self, delta: int):
        """Move active window to another monitor by offset"""
        logger.debug("move_to_monitor_by_offset(%s)", delta)
        self.enqueue(self.virtdesk_state.move_to_monitor, delta)

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
        self.enqueue(self.virtdesk_state.toggle_tilable)

    def move_to_workspace(self, workspace_index: int):
        """Move active window to a specific workspace"""
        pass

    def switch_workspace(
        self,
        workspace_index: int,
        monitor_name: str = None,
        hide_splash_in: Optional[float] = None,
    ) -> Callable:
        """Switch to a specific workspace"""
        # monitor_state = (
        #     self.virtdesk_state.monitor_state_by_name(monitor_name)
        #     if monitor_name
        #     else self.virtdesk_state.monitor_state_from_cursor()
        # )
        # window = monitor_state.workspaces[workspace_index].last_active_window
        # ui.show_windows_splash(monitor_state, workspace_index, window)
        # self.enqueue(
        #     WinEvent.CMD_CALL,
        #     self._switch_workspace,
        #     monitor_state,
        #     workspace_index,
        #     hide_splash_in,
        # )
        # if not hide_splash_in:
        #     return ui.hide_windows_splash

    def unhide_workspaces(self):
        """Unhide all workspaces"""
        for virtdesk_state in self.virtdesk_states.values():
            for ms in virtdesk_state.monitor_states.values():
                for ws in ms.workspaces:
                    for w in ws.windows:
                        w.toggle(True)

    def inspect_state(self):
        """Inspect the state of the virtual desktops"""
        inspect_virtdesk_states(self.virtdesk_states)

    def inspect_active_window(self):
        """Inspect active window"""
        self.virtdesk_state.window_detector.foreground_window().inspect()
