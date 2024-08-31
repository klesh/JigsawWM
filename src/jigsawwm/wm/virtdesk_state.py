"""Virtual Desktop State module"""
import logging
from typing import Dict, Set, Optional, Tuple, List

from jigsawwm.w32.monitor import Monitor, monitor_from_cursor, monitor_from_window, get_monitor_from_window, HMONITOR, enum_display_monitors
from jigsawwm.w32.window import Window, HWND, filter_windows

from .config import WmConfig
from .monitor_state import MonitorState 
from .workspace_state import WorkspaceState
from .pickable_state import PickableState
from .const import PREFERRED_MONITOR_INDEX, PREFERRED_WORKSPACE_INDEX, WORKSPACE_STATE

logger = logging.getLogger(__name__)


class VirtDeskState(PickableState):
    """VirtDeskState holds variables needed by a Virtual Desktop

    :param WindowManager manager: associated WindowManager
    :param bytearray desktop_id: virtual desktop id
    """

    config: WmConfig
    desktop_id: bytearray
    monitors: List[Monitor] = []
    windows: Dict[HWND, Window] = {}
    monitor_states: Dict[HMONITOR, MonitorState] = {}
    active_monitor_index: int = 0

    def __init__(self, desktop_id: bytearray):
        self.desktop_id = desktop_id

    def update_config(self, config: WmConfig):
        """Update the monitor states based on configuration"""
        self.config = config
        for monitor_state in self.monitor_states.values():
            monitor_state.update_config(config)
        self.sync_monitors()
        self.sync_windows()

    def sync_monitors(self):
        """Syncs the monitor states with the virtual desktop"""
        new_hmons, removed_hmons = self.detect_monitors_change()
        windows_tobe_rearranged = set()
        # process new monitors
        if new_hmons:
            windows_tobe_rearranged = set(self.windows.values())
            for hm in new_hmons:
                m = Monitor(hm)
                logger.info("new monitor connected: %s", m)
                self.monitor_states[hm] = MonitorState(m)
        # remove monitor states
        if removed_hmons:
            for hm in removed_hmons:
                ms = self.monitor_states.pop(hm)
                logger.info("monitor disconnected: %s", ms.monitor)
                windows_tobe_rearranged |= ms.windows
        # rearrange windows
        for w in windows_tobe_rearranged:
            hmon = self.monitors[w.attrs.get(PREFERRED_MONITOR_INDEX, 0)] 
            monitor_state: MonitorState = self.monitor_states[hmon]
            monitor_state.add_window(w)

    def detect_monitors_change(self) -> Tuple[Set[HMONITOR], Set[HMONITOR]]:
        """Detects new and removed monitors in the virtual desktop"""
        old_hmons = set(self.monitor_states.keys())
        hmons = enum_display_monitors()
        if old_hmons == hmons or not hmons:
            return
        new_monitors = hmons - old_hmons
        removed_monitors = old_hmons -hmons
        self.moni
        return new_monitors, removed_monitors

    def sync_windows(self):
        """Syncs the window states with the virtual desktop"""
        if not self.monitors:
            logger.warning("no monitors found")
            return
        new_windows, removed_windows = self.detect_windows_change()
        # handle new windows
        if new_windows:
            logger.info("new windows appeared: %s", new_windows)
            for w in new_windows:
                self.apply_rule_to_window(w)
                if PREFERRED_MONITOR_INDEX not in w.attrs:
                    logger.debug("window %s has no preferred monitor index", w)
                    w.attrs[PREFERRED_MONITOR_INDEX] = (
                        get_monitor_from_window(w.handle)
                        or monitor_from_cursor()
                    ).name
                monitor_state = self.monitor_state_by_name(w.attrs[PREFERRED_MONITOR_INDEX])
                monitor_state.add_window(w)
        # handle removed windows
        if removed_windows:
            logger.info("window disappeared: %s", removed_windows)
            for w in removed_windows:
                workspace_state: WorkspaceState = w.attrs[WORKSPACE_STATE]
                workspace_state.remove_window(w)
        for ms in self.monitor_states.values():
            monitor_state.sync_windows()
        if new_windows or removed_windows:
            self.save_state()
            self._managed_windows = windows
        else:
            # unchanged: restrict window into places
            for monitor_state in self.virtdesk_state.monitor_states.values():
                monitor_state.workspace.sync_windows()

    def detect_windows_change(self) -> Tuple[Set[Window], Set[Window]]:
        """Detects new and removed windows in the virtual desktop"""
        def is_new_window(hwnd: HWND) -> Optional[Window]:
            window = self.windows.get(hwnd)
            if window:
                return
            window = Window(hwnd)
            if not window.manageable:
                return
            return window
        new_windows = filter_windows(is_new_window)
        for w in new_windows:
            self.windows[w.handle] = w
        removed_windows = {w for w in self.windows.values() if not w.exists}
        for w in removed_windows:
            del self.windows[w.handle]
        return new_windows, removed_windows

    def apply_rule_to_window(self, window: Window) -> bool:
        """Check if window is to be tilable"""
        rule = self.config.find_rule_for_window(window)
        if rule:
            logger.info("applying rule %s on %s", rule, window)
            if rule.manageable is not None:
                window.manageable = rule.manageable
            if rule.tilable is not None:
                window.tilable = rule.tilable
            if rule.preferred_monitor_index:
                window.attrs[PREFERRED_MONITOR_INDEX] = self.monitors[rule.preferred_monitor_index % len(self.monitors)].name
            if rule.preferred_workspace_index:
                window.attrs[PREFERRED_WORKSPACE_INDEX] = rule.preferred_workspace_index

    def monitor_state_from_cursor(self) -> MonitorState:
        """Retrieve monitor_state from current cursor"""
        return self.monitor_states[monitor_from_cursor()]

    def monitor_state_from_window(self, window: Window) -> MonitorState:
        """Retrieve monitor_state from window"""
        return self.monitor_state[monitor_from_window(window.handle)]