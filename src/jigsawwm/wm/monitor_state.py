"""MonitorState maintains state of a specific Monitor under a Virtual Desktop"""
import logging
from typing import Set, List

from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window

from .config import WmConfig, WmRule
from .theme import Theme
from .workspace_state import WorkspaceState
from .pickable_state import PickableState

logger = logging.getLogger(__name__)


class MonitorState(PickableState):
    """MonitorState holds variables needed by a Monitor


    :param VirtDeskState virtdesk_state: associated virtual desktop
    :param Monitor monitor: associated system monitor
    :param str theme: the active theme for the monitor in the virtual desktop
    """

    config: WmConfig
    monitor: Monitor
    workspaces: List[WorkspaceState]
    active_workspace_index: int

    def __init__(self, config: WmConfig, monitor: Monitor):
        self.config = config
        self.monitor = monitor
        self.workspaces = [
            WorkspaceState(config, workspace_name, self.monitor)
            for workspace_name in config.workspace_names
        ]
        self.active_workspace_index = 0
        self.workspaces[0].toggle(True)

    def __repr__(self) -> str:
        return f"<MonitorState {self.monitor.name}>"

    def update_config(self, config: WmConfig):
        """Update the workspaces based on configuration"""
        self.config = config
        # if the number of workspaces has increased
        for workspace_index, workspace_name in enumerate(self.config.workspace_names):
            if workspace_index >= len(self.workspaces):
                self.workspaces.append(WorkspaceState(self.config, workspace_name, self.monitor))
            else:
                self.workspaces[workspace_index].name = workspace_name
        # or it has decrease
        l = len(self.config.workspace_names)
        i = l
        while i < len(self.workspaces):
            tobe_removed = self.workspaces[i]
            target_ws = self.workspaces[i % l]
            target_ws.windows = target_ws.windows.union(tobe_removed.windows)
            i += 1
        self.workspaces = self.workspaces[:l]
        for workspace in self.workspaces:
            workspace.update_config(config)

    @property
    def workspace(self) -> WorkspaceState:
        """Get the active workspace of the monitor"""
        return self.workspaces[self.active_workspace_index]

    @property
    def windows(self) -> Set[Window]:
        """Get the windows of the active workspace of the monitor"""
        return self.workspace.windows

    @property
    def tilable_windows(self) -> List[Window]:
        """Get the windows of the active workspace of the monitor"""
        return self.workspace.tilable_windows

    @property
    def theme(self) -> Theme:
        """Get the active theme of the monitor"""
        return self.workspace.theme

    def set_theme(self, theme: Theme):
        """Set the theme of the active workspace of the monitor"""
        self.workspace.set_theme(theme)

    def arrange(self):
        """Arrange the windows in the active workspace of the monitor"""
        self.workspace.arrange()

    def add_window(self, window: Window):
        """Add a window to the active workspace of the monitor"""
        self.workspace.add_window(window)

    def remove_window(self, window: Window):
        """Remove a window from the active workspace of the monitor"""
        self.workspace.remove_window(window)

    def find_workspace_by_name(self, name: str):
        """Find the workspace by name"""
        return next(filter(lambda w: w.name == name, self.workspaces), None)

    def switch_workspace(self, workspace_index: int, no_activation=False):
        """Switch to the workspace by index"""
        logger.debug("%s switch workspace by index to #%d", self, workspace_index)
        workspace_index = workspace_index % len(self.workspaces)
        if workspace_index == self.active_workspace_index:
            logger.warning("already in workspace index %s", workspace_index)
            return
        self.workspaces[self.active_workspace_index].toggle(False)
        self.workspaces[workspace_index].toggle(True, no_activation=no_activation)
        self.active_workspace_index = workspace_index

    def switch_workspace_by_name(self, workspace_name: str):
        """Switch to the workspace by index"""
        logger.debug("%s switch workspace by name to %s", self, workspace_name)
        for i, workspace in enumerate(self.workspaces):
            if workspace.name == workspace_name:
                self.switch_workspace(i)
                return

    def move_to_workspace(self, window: Window, workspace_index: int):
        """Move the window to the workspace by index"""
        logger.debug("%s move window %s to #%d", self, window, workspace_index)
        if workspace_index >= len(self.workspaces):
            logger.warning("workspace index %s does not exist", workspace_index)
            return
        if workspace_index == self.active_workspace_index:
            logger.warning("window %s already in workspace index %s", window, workspace_index)
            return
        if window not in self.workspace.windows:
            logger.warning("window %s not in active workspace", window)
            return
        # remove the window from its current workspace
        window.hide()
        windows = {window}
        for child in self.workspace.windows:
            if child.parent_handle == window.handle:
                child.hide()
                windows.add(child)
        self.workspace.remove_windows(windows)
        self.workspaces[workspace_index].add_windows(windows)

    def sync_windows(self, windows: Set[Window]) -> bool:
        """Synchronize managed windows with given actual windows currently visible and arrange them
        accordingly

        :param Set[Window] windows: latest visible windows
        """
        changed = False
        changed |= self.workspace.sync_windows(windows)
        for window in self.windows:
            rule: WmRule = window.attrs.pop("rule", None)
            if rule:
                if rule.to_workspace_index is not None and rule.to_monitor_index != 0:
                    self.move_to_workspace(window, rule.to_workspace_index)
                    changed = True
        logger.debug("%s sync windows %s", self, "changed" if changed else "unchanged")
        return changed

    def unhide_workspaces(self):
        """Unhide all workspaces of the monitor"""
        logger.debug("%s unhide workspaces", self)
        for workspace in self.workspaces:
            for window in workspace.windows:
                window.show()
