"""Window Manager Operations"""

import logging
import pickle
import os
import time
from typing import Dict, List, Callable
from ctypes.wintypes import HWND, LONG, DWORD

from jigsawwm.ui import Splash, app
from jigsawwm.w32 import hook
from jigsawwm.w32.winevent import WinEvent
from jigsawwm.w32.reg import get_current_desktop_id
from jigsawwm.worker import ThreadWorker

from .theme import Theme
from .config import WmConfig, WmRule
from .virtdesk_state import VirtDeskState
from .debug_state import inspect_virtdesk_states


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
        self.virtdesk_state.on_monitors_changed()
        self.virtdesk_state.on_windows_changed(starting_up=True)
        self.start_worker()
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

    def save_state(self):
        """Save the windows state"""
        logger.info("saving state")
        with open(self.DEFAULT_STATE_PATH, "wb") as f:
            pickle.dump(self.virtdesk_states, f)

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
        self.sleep_till(ts + 0.5)
        self.virtdesk_state.on_monitors_changed()

    def on_window_event(self, event: WinEvent, hwnd: HWND, ts: float):
        """Handle the winevent"""
        self.sleep_till(ts + 0.2)
        self.virtdesk_state.handle_window_event(event, hwnd)

    def enqueue_splash(self, fn: callable, *args):
        """Enqueue a callable with splash window"""
        self.enqueue(fn, *args)
        return lambda: self.enqueue(self.splash.hide_splash.emit)

    ########################################
    # Window Management Actions
    ########################################

    def next_window(self) -> Callable:
        """Activate the managed window next to the last activated managed window"""
        return self.enqueue_splash(self.virtdesk_state.switch_window_splash, +1)

    def prev_window(self) -> Callable:
        """Activate the managed window prior to the last activated managed window"""
        return self.enqueue_splash(self.virtdesk_state.switch_window_splash, -1)

    def swap_next(self):
        """Swap the current active managed window with its next in list"""
        return self.enqueue(self.virtdesk_state.swap_window, +1)

    def swap_prev(self):
        """Swap the current active managed window with its previous in list"""
        self.enqueue(self.virtdesk_state.swap_window, -1)

    def set_master(self):
        """Set the active active managed window as the Master or the second window
        in the list if it is Master already
        """
        self.enqueue(self.virtdesk_state.set_master)

    def switch_monitor(self, delta: int):
        """Switch to another monitor by given offset"""
        return self.enqueue_splash(self.virtdesk_state.switch_monitor_splash, delta)

    def move_to_monitor(self, delta: int):
        """Move active window to another monitor by offset"""
        self.enqueue(self.virtdesk_state.move_to_monitor, delta)

    def prev_theme(self):
        """Switch to previous theme in the themes list"""
        return self.enqueue_splash(self.virtdesk_state.switch_theme_splash, -1)

    def next_theme(self) -> Callable:
        """Switch to next theme in the themes list"""
        return self.enqueue_splash(self.virtdesk_state.switch_theme_splash, +1)

    def prev_monitor(self):
        """Switch to previous monitor"""
        return self.enqueue_splash(self.virtdesk_state.switch_monitor_splash, -1)

    def next_monitor(self):
        """Switch to next monitor"""
        return self.enqueue_splash(self.virtdesk_state.switch_monitor_splash, +1)

    def move_to_prev_monitor(self):
        """Move active window to previous monitor"""
        self.enqueue(self.virtdesk_state.move_to_monitor, -1)

    def move_to_next_monitor(self):
        """Move active window to next monitor"""
        self.enqueue(self.virtdesk_state.move_to_monitor, +1)

    def toggle_tilable(self):
        """Toggle the active window between tilable and floating state"""
        self.enqueue(self.virtdesk_state.toggle_tilable)

    def move_to_workspace(self, workspace_index: int):
        """Move active window to a specific workspace"""

    def switch_workspace(
        self,
        workspace_index: int,
    ) -> Callable:
        """Switch to a specific workspace"""

        def _switch_workspace_splash():
            ms = self.virtdesk_state.monitor_state_from_cursor()
            ms.switch_workspace(workspace_index)
            self.splash.show_splash.emit(ms, None)

        return self.enqueue_splash(_switch_workspace_splash)

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
                            w.toggle(True)

    def inspect_state(self):
        """Inspect the state of the virtual desktops"""
        inspect_virtdesk_states(self.virtdesk_states)

    def inspect_active_window(self):
        """Inspect active window"""
        self.virtdesk_state.window_detector.foreground_window().inspect()
