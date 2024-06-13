"""MonitorState maintains state of a specific Monitor under a Virtual Desktop"""
import logging
from typing import Set, List

from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window

from .config import WmConfig
from .theme import Theme
from .workspace_state import WorkspaceState

logger = logging.getLogger(__name__)


class MonitorState:
    """MonitorState holds variables needed by a Monitor


    :param VirtDeskState virtdesk_state: associated virtual desktop
    :param Monitor monitor: associated system monitor
    :param str theme: the active theme for the monitor in the virtual desktop
    """

    monitor: Monitor
    workspaces: list[WorkspaceState]
    active_workspace_index: int

    def __init__(self, config: WmConfig, monitor: Monitor):
        self.config = config
        self.monitor = monitor
        self.workspaces = [
            WorkspaceState(config, workspace_name, self.monitor)
            for workspace_name in config.workspace_names
        ]
        self.active_workspace_index = 0

    @property
    def workspace(self) -> WorkspaceState:
        """Get the active workspace of the monitor"""
        return self.workspaces[self.active_workspace_index]

    @property
    def windows(self) -> List[Window]:
        """Get the windows of the active workspace of the monitor"""
        return self.workspace.windows

    @property
    def theme(self) -> Theme:
        """Get the active theme of the monitor"""
        return self.workspace.theme

    def set_theme(self):
        """Set the theme of the active workspace of the monitor"""
        self.workspace.set_theme()

    def arrange(self):
        """Arrange the windows in the active workspace of the monitor"""
        self.workspace.arrange()

    def add_window(self, window: Window):
        """Add a window to the active workspace of the monitor"""
        self.workspace.add_window(window)

    def remove_window(self, window: Window):
        """Remove a window from the active workspace of the monitor"""
        self.workspace.remove_window(window)

    def switch_workspace(self, workspace_index: int):
        """Switch to the workspace by index"""
        logger.debug("switch workspace %s", workspace_index)
        workspace_index = workspace_index % len(self.workspaces)
        if workspace_index == self.active_workspace_index:
            logger.warning("already in workspace %s", workspace_index)
            return
        self.workspaces[self.active_workspace_index].toggle(False)
        self.workspaces[workspace_index].toggle(True)
        self.active_workspace_index = workspace_index

    def move_to_workspace(self, window: Window, workspace_index: int, switch: bool = False):
        """Move the window to the workspace by index"""
        logger.debug("move window %s to workspace %s", window, workspace_index)
        if workspace_index >= len(self.workspaces):
            logger.warning("workspace %s does not exist", workspace_index)
            return
        if workspace_index == self.active_workspace_index:
            logger.warning("window %s already in workspace %s", window, workspace_index)
            return
        if window not in self.workspace.windows:
            logger.warning("window %s not in active workspace", window)
            return
        # remove the window from its current workspace
        self.workspace.remove_window(window)
        self.workspaces[workspace_index].add_window(window)
        if switch:
            self.switch_workspace(workspace_index)
            self.arrange()
        else:
            window.hide()

    def sync_windows(self, windows: Set[Window]):
        """Synchronize managed windows with given actual windows currently visible and arrange them
        accordingly

        :param Set[Window] windows: latest visible windows
        """
        logger.debug("sync monitor %s with %d windows", self.monitor, len(windows))
        self.workspace.sync_windows(windows)

    def unhide_workspaces(self):
        """Unhide all workspaces of the monitor"""
        for workspace in self.workspaces:
            for window in workspace.windows:
                window.show()
