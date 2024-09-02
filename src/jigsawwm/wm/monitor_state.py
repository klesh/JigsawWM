"""MonitorState maintains state of a specific Monitor under a Virtual Desktop"""

import logging
from typing import List

from jigsawwm.w32.window import Window, Rect

from .theme import Theme
from .workspace_state import WorkspaceState
from .const import PREFERRED_WORKSPACE_INDEX, MONITOR_STATE, WORKSPACE_STATE

logger = logging.getLogger(__name__)


class MonitorState:
    """MonitorState holds variables needed by a Monitor


    :param VirtDeskState virtdesk_state: associated virtual desktop
    :param Monitor monitor: associated system monitor
    :param str theme: the active theme for the monitor in the virtual desktop
    """

    index: int
    name: str
    rect: Rect
    theme: Theme
    workspaces: List[WorkspaceState]
    active_workspace_index: int

    def __init__(
        self,
        index: int,
        name: str,
        workspace_names: List[str],
        rect: Rect,
        theme: Theme,
    ):
        self.index = index
        self.name = name
        self.rect = rect
        self.theme = theme
        self.active_workspace_index = 0
        self.workspaces = []
        self.set_workspaces(workspace_names)

    def __repr__(self) -> str:
        return f"<MonitorState #{self.index}>"

    def set_workspaces(self, workspace_names: List[str]):
        """Update the workspaces"""
        if len(self.workspaces) > len(workspace_names):
            self.active_workspace_index = self.active_workspace_index % len(
                workspace_names
            )
            active_workspace = self.workspaces[self.active_workspace_index]
            while len(self.workspaces) > len(workspace_names):
                ws = self.workspaces.pop()
                active_workspace.windows |= ws.windows
        if len(self.workspaces) < len(workspace_names):
            while len(self.workspaces) < len(workspace_names):
                self.workspaces.append(
                    WorkspaceState(
                        self.index,
                        len(self.workspaces),
                        workspace_names[len(self.workspaces)],
                        self.rect,
                        self.theme,
                    )
                )
        for i, workspace_name in enumerate(workspace_names):
            self.workspaces[i].name = workspace_name
        self.workspace.toggle(True)

    def set_rect(self, rect: Rect):
        """Update the monitor rect"""
        self.rect = rect
        for workspace in self.workspaces:
            workspace.set_rect(rect)

    @property
    def workspace(self) -> WorkspaceState:
        """Get the active workspace of the monitor"""
        return self.workspaces[self.active_workspace_index]

    def add_windows(self, *windows: List[Window]):
        """Add new windows to the active workspace of the monitor"""
        for w in windows:
            workspace_index: int = w.attrs.get(
                PREFERRED_WORKSPACE_INDEX, self.active_workspace_index
            )
            ws = self.workspaces[workspace_index]
            ws.windows.add(w)
            w.attrs[MONITOR_STATE] = self
            w.attrs[WORKSPACE_STATE] = ws
            logger.info("added window %s to %s", w, ws)

    def remove_windows(self, *windows: List[Window]):
        """Remove windows from the active workspace of the monitor"""
        for w in windows:
            ws: WorkspaceState = w.attrs[WORKSPACE_STATE]
            ws.windows.remove(w)
            # del w.attrs[MONITOR_STATE]
            # del w.attrs[WORKSPACE_STATE]
            logger.info("removed window %s from %s", w, ws)

    def switch_workspace(self, workspace_index: int):
        """Switch to the workspace by index"""
        logger.debug("%s switch workspace by index to #%d", self, workspace_index)
        workspace_index = workspace_index % len(self.workspaces)
        if workspace_index == self.active_workspace_index:
            logger.warning("already in workspace index %s", workspace_index)
            return
        self.workspaces[self.active_workspace_index].toggle(False)
        self.workspaces[workspace_index].toggle(True)
        self.active_workspace_index = workspace_index

    def move_to_workspace(self, window: Window, workspace_index: int):
        """Move the window to the workspace by index"""
        logger.debug("%s move window %s to #%d", self, window, workspace_index)
        if workspace_index >= len(self.workspaces):
            logger.warning("workspace index %s does not exist", workspace_index)
            return
        if workspace_index == self.active_workspace_index:
            logger.warning(
                "window %s already in workspace index %s", window, workspace_index
            )
            return
        if window not in self.workspace.windows:
            logger.warning("window %s not in active workspace", window)
            return
        # remove the window from its current workspace
        root = window.root_window
        children = window.find_manageable_children()
        self.workspace.remove_windows(children)
        self.workspace.remove_window(root)
        self.workspaces[workspace_index].add_windows(children)
        return self.workspaces[workspace_index].add_window(window)
