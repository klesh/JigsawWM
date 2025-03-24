"""Window Manager Operations"""

import logging
import os
import time
from ctypes.wintypes import DWORD, HWND, LONG
from typing import Callable, Dict, List, Optional

from jigsawwm.jmk.jmk_service import JmkService, Vk
from jigsawwm.ui import Splash, app
from jigsawwm.w32 import hook
from jigsawwm.w32.reg import get_current_desktop_id
from jigsawwm.w32.window import Rect, Window
from jigsawwm.w32.winevent import WinEvent
from jigsawwm.worker import ThreadWorker

from .config import WmConfig
from .debug_state import inspect_virtdesk_states
from .virtdesk_state import (
    MONITOR_STATE,
    PREFERRED_WINDOW_INDEX,
    WORKSPACE_STATE,
    MonitorState,
    VirtDeskState,
    WorkspaceState,
)

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
    _wait_mouse_released: bool = False
    _movesizing_window: Optional[Window] = None
    _movesizing_window_rect: Optional[Rect] = None
    jmk: JmkService

    def __init__(self, jmk_service: JmkService):
        self.jmk = jmk_service
        self.virtdesk_states = {}
        self.splash = Splash(jmk_service)
        self.splash.on_move_to_workspace.connect(self.on_splash_workspace_mouse_up)

    def start(self):
        """Start the WindowManagerCore service"""
        self.start_worker()
        self.enqueue(self.virtdesk_state.on_monitors_changed)
        self.enqueue(self.virtdesk_state.on_windows_changed, starting_up=True)
        self.install_hooks()

    def stop(self):
        """Stop the WindowManagerCore service"""
        self.uninstall_hooks()
        self.stop_worker()
        self.release_hidden_workspaces()

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

    @property
    def virtdesk_state(self) -> VirtDeskState:
        """Retrieve virtual desktop state"""
        desktop_id = get_current_desktop_id()
        virtdesk_state = self.virtdesk_states.get(desktop_id)
        if virtdesk_state is None:
            # make sure monitor_state for current virtual desktop exists
            virtdesk_state = VirtDeskState(desktop_id, self.config, self.splash)
            self.virtdesk_states[desktop_id] = virtdesk_state
        return virtdesk_state

    def sleep_till(self, ts: float):
        """Sleep till the timestamp"""
        span = ts - time.time()
        if span > 0:
            time.sleep(span)

    def on_screen_event(self, ts: float):
        """Handle screen event"""
        self.sleep_till(ts + 2)
        self.virtdesk_state.on_monitors_changed()

    def on_window_event(self, event: WinEvent, hwnd: HWND, ts: float):
        """Handle the winevent"""
        self.sleep_till(ts + 0.2)
        self.handle_window_event(event, hwnd)

    def handle_window_event(self, event: WinEvent, hwnd: Optional[HWND] = None):
        """Check if we need to sync windows for given window event"""
        # ignore if left mouse button is pressed in case of dragging
        if (
            not self._wait_mouse_released
            and event == WinEvent.EVENT_OBJECT_PARENTCHANGE
            and self.jmk.sysout.state.get(Vk.LBUTTON)  # assuming JMK is enabled...
        ):
            # delay the sync until button released to avoid flickering
            self._wait_mouse_released = True
            return
        elif self._wait_mouse_released:
            if not self.jmk.sysout.state.get(Vk.LBUTTON):
                self._wait_mouse_released = False
                self.virtdesk_state.on_windows_changed()
            else:
                return
        if not hwnd:
            return
        window = self.virtdesk_state.window_detector.get_window(hwnd)
        if not window.manageable:
            return
        # # filter by event
        if event == WinEvent.EVENT_SYSTEM_FOREGROUND:
            self.virtdesk_state.on_foreground_window_changed(window)
        if (
            event == WinEvent.EVENT_OBJECT_HIDE
            or event == WinEvent.EVENT_OBJECT_SHOW
            or event == WinEvent.EVENT_OBJECT_UNCLOAKED
        ):
            logger.info("event: %s, window: %s", event.name, window)
            self.virtdesk_state.on_windows_changed()
        elif event == WinEvent.EVENT_SYSTEM_MOVESIZESTART:
            self.on_move_size_start(window)
        elif event == WinEvent.EVENT_SYSTEM_MOVESIZEEND:
            self.on_movesize_end(window)
        elif (
            event == WinEvent.EVENT_SYSTEM_MINIMIZESTART
            or event == WinEvent.EVENT_SYSTEM_MINIMIZEEND
        ):
            self.virtdesk_state.on_minimize_changed(window)

    def on_move_size_start(self, window: Window):
        """React to EVENT_SYSTEM_MOVESIZESTART event"""
        if not window.manageable or not window.is_root_window:
            return
        self._movesizing_window = window
        self._movesizing_window_rect = window.get_rect()
        self.delay_call(0.5, self.check_moving_window)

    def check_moving_window(self):
        """React to EVENT_OBJECT_LOCATIONCHANGE event"""
        logger.debug("check_moving_window %s", self._movesizing_window)
        if not self._movesizing_window:
            return
        r1, r2 = self._movesizing_window.get_rect(), self._movesizing_window_rect
        if r1.width != r2.width or r1.height != r2.height:
            return
        self.splash.show_splash.emit(self.virtdesk_state.monitor_state_from_cursor())

    def on_splash_workspace_mouse_up(self, workspace_index: int):
        """React to mouse up event on splash's workspace widget"""
        self.enqueue(self.on_move_to_workspace, workspace_index)

    def on_move_to_workspace(self, workspace_index: int):
        """React to on move window to workspace using mouse"""
        if self._movesizing_window:
            logger.info(
                "send %s to workspace %s using mouse",
                self._movesizing_window,
                workspace_index,
            )
            self.enqueue(
                self.virtdesk_state.move_to_workspace,
                workspace_index,
                window=self._movesizing_window,
            )
            self._movesizing_window = None
        else:
            logger.info("switch to workspace %s using mouse", workspace_index)
            ms = self.virtdesk_state.monitor_state_from_cursor()
            self.enqueue(ms.switch_workspace, workspace_index)
            self.splash.hide_splash.emit()
            self.virtdesk_state.no_ws_switching_untill = time.time() + 1

    def on_movesize_end(self, window: Window):
        """React to EVENT_SYSTEM_MOVESIZEEND event"""
        self.splash.hide_splash.emit()
        if not self._movesizing_window:
            return
        self._movesizing_window = None
        if MONITOR_STATE not in window.attrs:
            logger.warning("window %s doesn't have MONITOR_STATE", window)
            return
        # when dragging chrome tab into a new window, the window will not have MONITOR_STATE
        ms: MonitorState = window.attrs[MONITOR_STATE]
        dst_ms = self.virtdesk_state.monitor_state_from_cursor()
        # window being dragged to another monitor
        if dst_ms != ms:
            logger.info("move %s to another monitor %s", window, dst_ms)
            self.virtdesk_state.move_to_monitor(window=window, dst_ms=dst_ms)
            return
        ws: WorkspaceState = window.attrs[WORKSPACE_STATE]
        if not ws.theme.static_layout and window.tilable and len(ws.tiling_windows) > 1:
            # window being reordered
            src_idx = window.attrs[PREFERRED_WINDOW_INDEX]
            dst_idx = ms.workspace.tiling_index_from_cursor()
            if dst_idx >= 0:
                self.virtdesk_state.swap_window(
                    idx=src_idx,
                    delta=dst_idx - src_idx,
                    workspace=ms.workspace,
                    activate=False,
                )
            return
        ws.restrict()

    def switch_window_splash(self, delta: int):
        """Switch to next or previous window"""
        return self.enqueue_splash(
            self.virtdesk_state.monitor_state_from_cursor().workspace.switch_window,
            delta,
        )

    def switch_monitor_splash(self, delta: int):
        """Switch to another monitor by given offset"""
        return self.enqueue_splash(self.virtdesk_state.switch_monitor, delta)

    def switch_theme_splash(self, delta: int) -> Callable:
        """Switch theme by offset"""
        monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        theme_index = self.config.get_theme_index(monitor_state.workspace.theme.name)
        theme = self.config.themes[(theme_index + delta) % len(self.config.themes)]
        return self.enqueue_splash(monitor_state.workspace.set_theme, theme)

    def switch_workspace_splash(self, workspace_index: int):
        """Switch to a specific workspace"""
        return self.enqueue_splash(
            self.virtdesk_state.monitor_state_from_cursor().switch_workspace,
            workspace_index,
        )

    def show_splash(self):
        self.splash.show_splash.emit(self.virtdesk_state.monitor_state_from_cursor())

    def enqueue_splash(self, fn: callable, *args):
        """Enqueue a callable with splash window"""
        self.enqueue(fn, *args)
        self.enqueue(self.show_splash)
        return lambda: self.enqueue(self.splash.hide_splash.emit)

    ########################################
    # Window Management Actions
    ########################################

    def next_window(self) -> Callable:
        """Activate the managed window next to the last activated managed window"""
        return self.switch_window_splash(+1)

    def prev_window(self) -> Callable:
        """Activate the managed window prior to the last activated managed window"""
        return self.switch_window_splash(-1)

    def swap_next(self):
        """Swap the current active managed window with its next in list"""
        return self.enqueue(self.virtdesk_state.swap_window, +1)

    def swap_prev(self):
        """Swap the current active managed window with its previous in list"""
        self.enqueue(self.virtdesk_state.swap_window, -1)

    def set_master(self):
        """Set the active managed window as the Master or the second window
        in the list if it is Master already
        """
        self.enqueue(self.virtdesk_state.set_master)

    def roll_next(self):
        """Roll the next window to the top of the list as master"""
        self.enqueue(self.virtdesk_state.roll_window, 1)

    def roll_prev(self):
        """Roll the next window to the top of the list as master"""
        self.enqueue(self.virtdesk_state.roll_window, -1)

    def switch_monitor(self, delta: int):
        """Switch to another monitor by given offset"""
        return self.enqueue_splash(self.virtdesk_state.switch_monitor, delta)

    def move_to_monitor(self, delta: int):
        """Move active window to another monitor by offset"""
        self.enqueue(self.virtdesk_state.move_to_monitor, delta)

    def toggle_mono(self):
        """Toggle mono theme"""
        self.enqueue(
            self.virtdesk_state.monitor_state_from_cursor().workspace.toggle_mono_theme
        )

    def prev_theme(self):
        """Switch to previous theme in the themes list"""
        return self.switch_theme_splash(-1)

    def next_theme(self) -> Callable:
        """Switch to next theme in the themes list"""
        return self.switch_theme_splash(+1)

    def prev_monitor(self):
        """Switch to previous monitor"""
        return self.switch_monitor_splash(-1)

    def next_monitor(self):
        """Switch to next monitor"""
        return self.switch_monitor_splash(+1)

    def move_to_prev_monitor(self):
        """Move active window to previous monitor"""
        self.enqueue(self.virtdesk_state.move_to_monitor, -1)

    def move_to_next_monitor(self):
        """Move active window to next monitor"""
        self.enqueue(self.virtdesk_state.move_to_monitor, +1)

    def toggle_tilable(self):
        """Toggle the active window between tilable and floating state"""
        self.enqueue(self.virtdesk_state.toggle_tilable)

    def toggle_splash(self):
        """Toggle the splash screen"""

        def toggle_splash():
            if self.splash.isHidden():
                self.splash.show_splash.emit(
                    self.virtdesk_state.monitor_state_from_cursor()
                )
            else:
                self.splash.hide_splash.emit()

        self.enqueue(toggle_splash)

    def switch_to_workspace(
        self,
        workspace_index: int,
    ) -> Callable:
        """Switch to a specific workspace"""
        return self.enqueue_splash(
            self.virtdesk_state.monitor_state_from_cursor().switch_workspace,
            workspace_index,
        )

    def switch_workspace_delta(
        self,
        delta: int,
    ) -> Callable:
        """Switch to workspace by offset"""
        return self.switch_to_workspace(
            self.virtdesk_state.monitor_state_from_cursor().active_workspace_index
            + delta
        )

    def next_workspace(self) -> Callable:
        """Switch to next workspace"""
        return self.switch_workspace_delta(+1)

    def prev_workspace(self) -> Callable:
        """Switch to next workspace"""
        return self.switch_workspace_delta(-1)

    def move_to_workspace(self, workspace_index: int):
        """Move active window to a specific workspace"""
        self.enqueue(self.virtdesk_state.move_to_workspace, workspace_index)

    def move_to_workspace_delta(self, delta: int):
        """Move active window to a workspace by offset"""
        self.enqueue(self.virtdesk_state.move_to_workspace, delta, is_delta=True)

    def move_to_next_workspace(self):
        """Move active window to next workspace"""
        return self.move_to_workspace_delta(+1)

    def move_to_prev_workspace(self):
        """Move active window to previous workspace"""
        return self.move_to_workspace_delta(-1)

    ########################################
    # Other helper functions
    ########################################

    def release_hidden_workspaces(self):
        """Unhide all workspaces"""
        for virtdesk_state in self.virtdesk_states.values():
            for ms in virtdesk_state.monitor_states.values():
                for ws in ms.workspaces:
                    for w in ws.windows:
                        if w.exists():
                            ws.toggle_window(w, True)

    def inspect_state(self):
        """Inspect the state of the virtual desktops"""
        inspect_virtdesk_states(self.virtdesk_states)

    def inspect_active_window(self):
        """Inspect active window"""
        self.virtdesk_state.window_detector.foreground_window().inspect()
