"""WindowManagerCore is the core of the WindowManager, it manages the windows"""
import logging
import os
import pickle
import time
from typing import Dict, List, Set, Tuple, Optional, Callable
from queue import SimpleQueue
from threading import Thread

from jigsawwm.w32.monitor import (
    Monitor,
    get_monitor_from_window,
    get_monitors,
    get_cursor_pos,
)
from jigsawwm.w32.reg import get_current_desktop_id
from jigsawwm.w32.window import (
    HWND,
    Window,
    get_active_window,
    lookup_window,
    filter_windows,
    get_seen_windows,
)
from jigsawwm.w32.winevent import WinEvent
from jigsawwm.jmk import sysinout, Vk
from jigsawwm import ui, workers

from .virtdesk_state import VirtDeskState, MonitorState
from .config import WmConfig
from .debug_state import inspect_virtdesk_states
from .theme import Theme
from .const import *

logger = logging.getLogger(__name__)
class WindowManagerCore:
    """
    WindowManagerCore processes the event queue for the Manager, handling all necessary operations.
    The primary goal is to serialize all events and user actions through the queue to prevent
    concurrency issues. This approach is crucial because manipulating windows within the manager
    can sometimes generate new events, which could potentially lead to an infinite loop.
    """

    DEFAULT_STATE_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "jigsawwm", "wm.state")
    virtdesk_states: Dict[bytearray, VirtDeskState]
    config: WmConfig
    _wait_mouse_released: bool = False
    _queue: Optional[SimpleQueue]  = None
    _consumer: Optional[Thread] = None
    _monitors: List[Monitor] = []
    _managed_windows: Set[Window] = set()
    _previous_switch_workspace_for_window_activation = 0.0

    def __init__(
        self,
        config: WmConfig
    ):
        self.config = config
        self.virtdesk_states = {}
        self._queue = SimpleQueue()

    @property
    def virtdesk_state(self) -> VirtDeskState:
        """Retrieve virtual desktop state"""
        desktop_id = get_current_desktop_id()
        virtdesk_state = self.virtdesk_states.get(desktop_id)
        if virtdesk_state is None:
            # make sure monitor_state for current virtual desktop exists
            virtdesk_state = VirtDeskState(self.config, desktop_id)
            self.virtdesk_states[desktop_id] = virtdesk_state
        return virtdesk_state

    def _consume_events(self):
        event, args, timestamp = None, None, None
        while True:
            try:
                # wait for the next task
                event, args, timestamp = self._queue.get()
                if event == WinEvent.CMD_EXIT:
                    break # terminate
                elif event == WinEvent.CMD_CALL:
                    fn, args = args[0], args[1:]
                    fn(*args)
                else:
                    # delay for a certain time for windows state to be stable
                    #  case 1: CVR won't be tiled when restored with maximized mode
                    #  case 2: libreoffice is not tiled on first launch
                    hwnd = args[0] if len(args) > 0 else None
                    delay = self.is_event_interested(event, hwnd)
                    if delay:
                        tts = delay - (time.time() - timestamp)
                        if tts > 0:
                            time.sleep(tts)
                        logger.info("!!! REACT on event %s for window %s", event.name, hwnd)
                        self.sync_windows()
            except: # pylint: disable=bare-except
                logger.exception("consume_queue error, event: %s, args: %s, ts: %s", event, args, timestamp)

    def is_event_interested(self, event: WinEvent, hwnd: HWND) -> float:
        """Check if event is interested"""
        if event == WinEvent.EVENT_SCREEN_CHANGED:
            return 0.5
        # ignore if left mouse button is pressed in case of dragging
        if not self._wait_mouse_released and event == WinEvent.EVENT_OBJECT_PARENTCHANGE and sysinout.state.get( Vk.LBUTTON )  :
            # delay the sync until button released to avoid flickering
            self._wait_mouse_released = True
            return False
        elif self._wait_mouse_released:
            if not sysinout.state.get( Vk.LBUTTON ):
                self._wait_mouse_released = False
            else:
                return False
        if not hwnd:
            return False
        window = lookup_window(hwnd)
        if not window.manageable:
            return False
        # # filter by event
        if event == WinEvent.EVENT_OBJECT_SHOW or event == WinEvent.EVENT_OBJECT_UNCLOAKED:
            if self.try_switch_workspace_for_window_activation(window):
                return False
            if window in self._managed_windows:
                return False
        elif event == WinEvent.EVENT_OBJECT_HIDE: # same as above
            # fix case: toggle chrome fullscreen
            # window.is_visible is for vscode, it somehow genertes hide event when unfocused
            if window not in self._managed_windows or window.is_visible or not window.attrs[WORKSPACE_STATE].showing:
                return False
            # if logger.isEnabledFor(logging.DEBUG):
            #     inspect_virtdesk_states(self.virtdesk_states)
        elif event == WinEvent.EVENT_SYSTEM_MOVESIZEEND:
            if self.try_swapping_window(window):
                return False
        elif event == WinEvent.EVENT_SYSTEM_MINIMIZEEND:
            if not window.is_visible:
                return False
            # if logger.isEnabledFor(logging.DEBUG):
            #     inspect_virtdesk_states(self.virtdesk_states)
        elif event == WinEvent.EVENT_SYSTEM_MINIMIZESTART:
            if not window.is_visible:
                return False
        else:
            if event not in (
                WinEvent.EVENT_OBJECT_LOCATIONCHANGE,
                WinEvent.EVENT_OBJECT_NAMECHANGE,
                # WinEvent.EVENT_OBJECT_CREATE,
                WinEvent.EVENT_SYSTEM_MENUSTART,
                WinEvent.EVENT_SYSTEM_MENUEND,
                WinEvent.EVENT_OBJECT_REORDER,
                WinEvent.EVENT_SYSTEM_CAPTURESTART,
                WinEvent.EVENT_SYSTEM_CAPTUREEND,
            ):
                # do NOT inspect Window instance here, would crash the app
                # logger.debug("ignore winevent %s for window %s", event.name, hwnd)
                pass
            return False

        return 0.2

    def try_switch_workspace_for_window_activation(self, window: Window):
        """Try to switch workspace for window activation"""
        # a window belongs to hidden workspace just got activated
        # put your default browser into workspace and then ctrl-click a link, e.g. http://google.com 
        now = time.time()
        elapsed = now - self._previous_switch_workspace_for_window_activation
        if elapsed < 1:
            # some app might use multiple top level windows, like fusion360 which
            # might cause the event to be triggered multiple times
            logger.warning("workspace switching happened too frequently, possible loop")
            return
        if MONITOR_STATE not in window.attrs or window.manageable is False:
            return
        monitor_state, workspace_state = window.attrs[MONITOR_STATE], window.attrs[WORKSPACE_STATE]
        if not workspace_state.showing:
            self._previous_switch_workspace_for_window_activation = now
            monitor_state.switch_workspace_by_name(workspace_state.name, no_activation=True)
            logger.info("switch to workspace %s due window %s got activated", workspace_state, window)
            return True

    def try_swapping_window(self, window: Window) -> Optional[Tuple[Window, MonitorState]]:
        """Check if the window is being reordered"""
        logger.info("try swapping windows")
        # when dragging chrome tab into a new window, the window will not have MONITOR_STATE
        monitor_state: MonitorState = (
            window.attrs[MONITOR_STATE]
            if MONITOR_STATE in window.attrs
            else self.virtdesk_state.monitor_state_from_window(window)
        )
        target_monitor_state = self.virtdesk_state.monitor_state_from_cursor()
        logger.info("target monitor: %s", target_monitor_state.monitor)
        # window being dragged to another monitor
        if target_monitor_state != monitor_state:
            logger.debug("move window %s to another monitor", window)
            monitor_state.remove_window(window)
            target_monitor_state.add_window(window)
            self.save_state()
            return
        if not window.tilable:
            return False
        window_index = -1
        try:
            window_index = monitor_state.tilable_windows.index(window)
        except ValueError:
            return
        target_window = None
        target_window_index = -1
        pos = get_cursor_pos()
        for i, w in enumerate(target_monitor_state.tilable_windows):
            r = w.restricted_actual_rect
            if pos.x > r.left and pos.x < r.right and pos.y > r.top and pos.y < r.bottom:
                target_window = w
                target_window_index = i
        if not target_window or target_window == window:
            return False
        # swap
        a = monitor_state.tilable_windows
        b = target_monitor_state.tilable_windows
        a[window_index], b[target_window_index] = target_window, window
        a = window.restricted_rect
        if a is None:
            raise ValueError(f"window has no restricted rect: {window}")
        b = target_window.restricted_rect
        if b is None:
            raise ValueError(f"target window has no restricted rect: {target_window}")
        window.set_restrict_rect(b)
        target_window.set_restrict_rect(a)
        self.save_state()
        return True

    def sync_windows(self) -> bool:
        """Synchronize internal windows state to the system state synchronously"""
        # gather all manageable windows
        self.sync_monitors()
        windows = set(filter_windows(lambda w: w.handle != ui.instance.winId() and w.manageable and w.is_visible))
        old_windows = self._managed_windows
        # new windows
        new_windows = windows - old_windows
        if new_windows:
            logger.info("new windows appeared: %s", new_windows)
            for window in new_windows:
                if window.root_window != window:
                    logger.debug("window %s is not root window", window)
                    window.attrs[RULE_APPLIED] = True
                    if PREFERRED_MONITOR_NAME not in window.root_window.attrs:
                        logger.exception("window %s has no preferred monitor name", window.root_window)
                    else:
                        window.attrs[PREFERRED_MONITOR_NAME] = window.root_window.attrs[PREFERRED_MONITOR_NAME]
                        window.attrs[PREFERRED_WORKSPACE_INDEX] = window.root_window.attrs[PREFERRED_WORKSPACE_INDEX]
                if RULE_APPLIED not in window.attrs:
                    logger.debug("applying rule to window %s", window)
                    self.apply_rule_to_window(window)
                    window.attrs[RULE_APPLIED] = True
                if PREFERRED_MONITOR_NAME not in window.attrs:
                    logger.debug("window %s has no preferred monitor name", window)
                    window.attrs[PREFERRED_MONITOR_NAME] = (
                        get_monitor_from_window(window.handle)
                        or self.virtdesk_state.monitor_state_from_cursor().monitor
                    ).name
                monitor_state = (
                    self.virtdesk_state.monitor_state_by_name(window.attrs[PREFERRED_MONITOR_NAME])
                    or self.virtdesk_state.monitor_state_from_window(window)
                )
                if PREFERRED_WORKSPACE_INDEX not in window.attrs:
                    logger.debug("window %s has no preferred workspace index", window)
                    window.attrs[PREFERRED_WORKSPACE_INDEX] = monitor_state.active_workspace_index
                logger.debug("adding window %s to %s", window, monitor_state)
                window.attrs[PREFERRED_WINDOW_ORDER] = monitor_state.add_window(window)
        # removed windows
        removed_windows = old_windows - windows
        if removed_windows:
            logger.info("window disappeared: %s", removed_windows)
            for window in removed_windows:
                workspace_state: MonitorState = window.attrs[WORKSPACE_STATE]
                workspace_state.remove_window(window)
        if new_windows or removed_windows:
            # change
            self.save_state()
            self._managed_windows = windows
        else:
            # unchanged: restrict window into places
            for monitor_state in self.virtdesk_state.monitor_states.values():
                monitor_state.workspace.sync_windows()

    def sync_monitors(self):
        """Sync monitor states"""
        virtdesk_state = self.virtdesk_state
        old_monitors = set(self._monitors)
        monitors = set(get_monitors())
        if old_monitors == monitors:
            return
        self._monitors = list(sorted(monitors, key=lambda m: m.name))
        windows_tobe_rearranged = set()
        # new monitors
        new_monitors = monitors - old_monitors
        if new_monitors:
            logger.info("new monitor connected: %s rearrange all windows", new_monitors)
            for ms in virtdesk_state.monitor_states.values():
                for ws in ms.workspaces:
                    windows_tobe_rearranged |= ws.windows
        # remove monitor states
        removed_monitors = old_monitors - monitors
        if removed_monitors:
            logger.info("monitor disconnected: %s", removed_monitors)
            for removed_monitor in removed_monitors:
                removed_state = virtdesk_state.monitor_states.pop(removed_monitor)
                for ws in removed_state.workspaces:
                    windows_tobe_rearranged |= ws.windows
        # rearrange windows
        groups = {}
        for window in windows_tobe_rearranged:
            if not window.exists():
                continue
            monitor = next(filter(lambda m: m.name == window.attrs[PREFERRED_MONITOR_NAME], monitors), self._monitors[0]) # pylint: disable=cell-var-from-loop
            if monitor not in groups:
                groups[monitor] = set()
            groups[monitor].add(window)
        for monitor, windows in groups.items():
            virtdesk_state.monitor_state(monitor).workspace.add_windows(windows)

    def apply_rule_to_window(self, window: Window) -> bool:
        """Check if window is to be tilable"""
        rule = self.config.find_rule_for_window(window)
        if rule:
            logger.info("applying rule %s on %s", rule, window)
            if rule.manageable is not None:
                window.manageable = rule.manageable
            if rule.tilable is not None:
                window.tilable = rule.tilable
            if rule.to_monitor_index:
                window.attrs[PREFERRED_MONITOR_NAME] = self._monitors[rule.to_monitor_index % len(self._monitors)].name
            if rule.to_workspace_index:
                window.attrs[PREFERRED_WORKSPACE_INDEX] = rule.to_workspace_index

    def save_state(self):
        """Save the windows state"""
        logger.info("saving state")
        with open(self.DEFAULT_STATE_PATH, "wb") as f:
            pickle.dump([self.virtdesk_states, get_seen_windows(), self._managed_windows, self._monitors], f)

    def _switch_workspace(self, monitor_state: MonitorState, workspace_index: int, hide_splash_in: Optional[float] = None) -> Callable:
        logger.debug("switch workspace to %d", workspace_index)
        monitor_state.switch_workspace(workspace_index)
        self.save_state()
        if hide_splash_in:
            logger.debug("hide splash in %s", hide_splash_in)
            workers.submit_with_delay(ui.hide_windows_splash, hide_splash_in)

    def _move_to_workspace(self, window: Window, workspace_index: int):
        monitor_state: MonitorState = window.attrs[MONITOR_STATE]
        window.attrs[PREFERRED_WORKSPACE_INDEX] = workspace_index
        window.attrs[PREFERRED_WINDOW_ORDER] = monitor_state.move_to_workspace(window, workspace_index)
        self.save_state()

    def _reorder(self, reorderer: Callable[[List[Window], int], None]):
        window = get_active_window()
        if not window.manageable or not window.tilable:
            return
        monitor_state = window.attrs[MONITOR_STATE]
        if len(monitor_state.tilable_windows) < 2:
            return
        next_active_window = reorderer(monitor_state.tilable_windows, monitor_state.tilable_windows.index(window))
        monitor_state.arrange()
        (next_active_window or window).activate()
        for i, w in enumerate(monitor_state.tilable_windows):
            w.attrs[PREFERRED_WINDOW_ORDER] = i
        self.save_state()

    def _set_theme(self, monitor_state: MonitorState, theme: Theme):
        monitor_state.set_theme(theme)
        self.save_state()

    def _move_to_monitor(self, monitor_state: MonitorState, window: Window, dst_monitor_state: MonitorState):
        window.attrs[PREFERRED_MONITOR_NAME] = dst_monitor_state.monitor.name
        window.attrs[PREFERRED_WORKSPACE_INDEX] = dst_monitor_state.active_workspace_index
        window.attrs[PREFERRED_WINDOW_ORDER] = dst_monitor_state.add_window(window)
        monitor_state.remove_window(window)
        if monitor_state.tilable_windows:
            monitor_state.tilable_windows[0].activate()
        self.save_state()

    def _toggle_tilable(self, window: Window):
        window.tilable = not window.tilable
        logger.info("toggle window %s tilable state to %s", window, window.tilable)
        # shrink the window a little bit to avoid covering tialbe windows
        if not window.tilable:
            # window.unrestrict()
            window.shrink()
        window.attrs[MONITOR_STATE].sync_windows()
        self.save_state()

    def inspect_state(self):
        """Inspect the state of the virtual desktops"""
        inspect_virtdesk_states(self.virtdesk_states)

    def inspect_active_window(self):
        """Inspect active window"""
        get_active_window().inspect()