"""Virtual Desktop State module"""
import logging
from typing import Dict, Optional, Tuple
from ctypes.wintypes import HWND

from jigsawwm.w32.monitor import Monitor, get_monitors, monitor_from_cursor
from jigsawwm.w32.window import Window

from .config import WmConfig
from .monitor_state import MonitorState 
from .pickable_state import PickableState

logger = logging.getLogger(__name__)


class VirtDeskState(PickableState):
    """VirtDeskState holds variables needed by a Virtual Desktop

    :param WindowManager manager: associated WindowManager
    :param bytearray desktop_id: virtual desktop id
    """

    config: WmConfig
    desktop_id: bytearray
    monitor_states: Dict[Monitor, MonitorState]

    def __init__(self, config: WmConfig, desktop_id: bytearray):
        self.config = config
        self.desktop_id = desktop_id
        self.monitor_states = {
            monitor: MonitorState(config, monitor) for monitor in get_monitors()
        }

    def update_config(self, config: WmConfig):
        """Update the monitor states based on configuration"""
        self.config = config
        for monitor_state in self.monitor_states.values():
            monitor_state.update_config(config)

    def get_monitor_state(self, monitor: Monitor) -> MonitorState:
        """Retrieves the monitor state for the specified monitor in the virtual desktop

        :param Monitor monitor: monitor
        :returns: monitor state
        :rtype: MonitorState
        """
        monitor_state = self.monitor_states.get(monitor)
        if monitor_state is None:
            monitor_state = MonitorState(self.config, monitor)
            self.monitor_states[monitor] = monitor_state
        return monitor_state

    def get_monitor_state_by_name(self, monitor_name: str) -> MonitorState:
        """Retrieves the monitor state for the specified monitor byname in the virtual desktop

        :param str monitor_name: monitor_name
        :returns: monitor state
        :rtype: MonitorState
        """
        for monitor, monitor_state in self.monitor_states.items():
            if monitor.name == monitor_name:
                return monitor_state

    def find_monitor_of_window(self, window: Window) -> Optional[Monitor]:
        """Find the monitor state of the monitor that contains the window

        :param Window window: window
        :returns: monitor state
        :rtype: Optional[MonitorState]
        """
        for monitor, monitor_state in self.monitor_states.items():
            if window in monitor_state.windows:
                return monitor
        return None

    def find_window_in_hidden_workspaces(self, hwnd: HWND) -> Optional[Tuple[MonitorState, int]] :
        """Find the MonitorState and workspace index of givin window in the hidden workspaces

        :param Window window: window
        :returns: monitor state and workspace index
        :rtype: Optional[str]
        """
        for monitor_state in self.monitor_states.values():
            for workspace_index, workspace_state in enumerate(monitor_state.workspaces):
                for window in workspace_state.windows:
                    if window.handle == hwnd:
                        if workspace_state.showing:
                            return None
                        return monitor_state, workspace_index
        return None

    def monitor_state_from_cursor(self) -> MonitorState:
        """Retrieve monitor_state from current cursor"""
        return self.get_monitor_state(Monitor(monitor_from_cursor()))