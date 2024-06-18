"""Virtual Desktop State module"""
import logging
from typing import Dict, Optional

from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window

from .config import WmConfig
from .monitor_state import MonitorState

logger = logging.getLogger(__name__)


class VirtDeskState:
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
        self.monitor_states = {}

    def get_monitor_state(self, monitor: Monitor) -> MonitorState:
        """Retrieves the monitor state for the specified monitor in the virtual desktop

        :param Monitor monitor: monitor
        :returns: monitor state
        :rtype: MonitorState
        """
        logger.debug("get_monitor_state: monitor %s", monitor)
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
        logger.debug("get_monitor_state_by_name: monitor %s", monitor_name)
        for monitor, monitor_state in self.monitor_states.items():
            if monitor.name == monitor_name:
                return monitor_state

    def find_monitor_of_window(self, window: Window) -> Optional[Monitor]:
        """Find the monitor state of the monitor that contains the window

        :param Window window: window
        :returns: monitor state
        :rtype: Optional[MonitorState]
        """
        logger.debug("find_monitor_of_window: window %s", window)
        for monitor, monitor_state in self.monitor_states.items():
            if window in monitor_state.windows:
                return monitor
        return None
