"""Virtual Desktop State module"""
import logging
from typing import Dict

from jigsawwm.w32.monitor import Monitor, get_monitors, monitor_from_cursor, monitor_from_window
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

    def monitor_state(self, monitor: Monitor) -> MonitorState:
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

    def monitor_state_by_name(self, monitor_name: str) -> MonitorState:
        """Retrieves the monitor state for the specified monitor byname in the virtual desktop

        :param str monitor_name: monitor_name
        :returns: monitor state
        :rtype: MonitorState
        """
        for monitor, monitor_state in self.monitor_states.items():
            if monitor.name == monitor_name:
                return monitor_state

    def monitor_state_from_cursor(self) -> MonitorState:
        """Retrieve monitor_state from current cursor"""
        return self.monitor_state(Monitor(monitor_from_cursor()))

    def monitor_state_from_window(self, window: Window) -> MonitorState:
        """Retrieve monitor_state from window"""
        return self.monitor_state(Monitor(monitor_from_window(window.handle)))