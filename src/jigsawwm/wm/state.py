import logging
from typing import Dict, List, Optional, Set
from os import path

from jigsawwm.tiler.tilers import *
from jigsawwm.w32.monitor import Monitor, get_monitor_from_window
from jigsawwm.w32.window import RECT, Window, get_active_window
from jigsawwm.w32.process import ProcessDpiAwareness

from .theme import Theme

logger = logging.getLogger(__name__)


class WorkspaceState:
    monitor: Monitor
    theme: Optional[str]
    windows: List[Window]

    def __init__(self, theme: Optional[str] = None):
        self.theme = theme
        self.windows = []

    def toggle(self, show: bool):
        for window in self.windows:
            if show:
                window.show()
            else:
                window.hide()


class MonitorState:
    """MonitorState holds variables needed by a Monitor


    :param VirtDeskState virtdesk_state: associated virtual desktop
    :param Monitor monitor: associated system monitor
    :param str theme: the active theme for the monitor in the virtual desktop
    """

    virtdesk_state: "VirtDeskState"
    monitor: Monitor
    monitor_theme: Optional[str]
    last_active_window: Optional[Window] = None
    workspaces: list[WorkspaceState]
    active_workspace_index: int

    def __init__(
        self,
        virtdesk_state: "VirtDeskState",
        monitor: Monitor,
        theme: Optional[str] = None,
    ):
        self.virtdesk_state = virtdesk_state
        self.monitor = monitor
        self.last_active_window = None
        self.hook_ids = []
        self.monitor_theme = theme
        self.workspaces = [
            WorkspaceState(theme=theme),
        ]
        self.active_workspace_index = 0

    @property
    def workspace(self):
        return self.workspaces[self.active_workspace_index]

    @property
    def windows(self):
        return self.workspace.windows

    @windows.setter
    def windows(self, windows: List[Window]):
        self.workspace.windows = windows

    @property
    def theme(self):
        return self.workspace.theme

    @theme.setter
    def theme(self, theme: str):
        self.workspace.theme = theme

    def _ensure_workspace(self, workspace_index: int):
        while len(self.workspaces) < workspace_index + 1:
            self.workspaces.append(WorkspaceState(theme=self.monitor_theme))
    
    def switch_workspace(self, workspace_index: int):
        if workspace_index == self.active_workspace_index:
            return
        self.workspace.toggle(False)
        self._ensure_workspace(workspace_index)
        self.active_workspace_index = workspace_index
        self.workspace.toggle(True)
        self.arrange()

    def move_to_workspace(self, window: Window, workspace_index: int):
        if workspace_index == self.active_workspace_index:
            return
        self._ensure_workspace(workspace_index)
        self.windows.remove(window)
        window.hide()
        self.arrange()
        self.workspaces[workspace_index].windows.append(window)

    def unhide_workspaces(self):
        for workspace in self.workspaces:
            workspace.toggle(True)

    def get_existing_windows(self) -> List[Window]:
        """Retrieves current managed windows"""
        return [w for w in self.windows if w.exists()]

    def sync(self, windows: Set[Window], restrict=False, window_sort_order=[]):
        """Synchronize managed windows with given actual windows currently visible and arrange them accordingly

        :param Set[Window] windows: latest visible windows
        :param bool restrict: optional, restrict windows to their specified rect no matter what
        """
        theme = self.virtdesk_state.get_theme(self.theme)


        #
        # remove invalid windows from list
        #

        old_list = self.windows
        new_list = []
        for w in old_list:
            if w not in windows:
                continue
            windows.remove(w)
            if not w.exists():
                continue
            new_list.append(w)


        #
        # prepend or append the new windows
        #

        if theme.new_window_as_master:
            new_list = list(windows) + new_list
        else:
            new_list = new_list + list(windows)


        #
        # sort windows according to init sequence
        #

        _i = 0
        sorted_list = []
        if len(window_sort_order) > 0:

            # over all window elements of desired sequence
            for w_seq in window_sort_order:
                # over all currently (to become) active window objects
                for w_cur in new_list:
                    # check for correspondence
                    if w_seq[0].lower() == path.basename(w_cur.exe).lower() \
                            and ( len(w_seq) < 2 or not w_seq[1] or w_seq[1].lower() in w_cur.title.lower() ):
                        # add window object at prioritized position
                        sorted_list.append(w_cur)
                        # remove window object from source list
                        new_list.remove(w_cur)
                        # continue with next window from sequence
                        break

            # compose new list of sorted part and remainder
            new_list = sorted_list + new_list


        #
        # skip if there is nothing changed unless strict mode
        #

        if new_list == old_list:
            if restrict:
                self.restrict(theme)
            return


        self.windows = new_list
        self.arrange(theme)

    def arrange(self, theme: Optional[Theme] = None):
        """Arrange windows based on the theme

        :param str theme: optional, fallback to theme of the instance
        """
        theme = theme or self.virtdesk_state.get_theme(self.theme)
        wr = self.monitor.get_info().rcWork
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self.get_existing_windows()
        i = 0
        gap = theme.gap
        for left, top, right, bottom in theme.layout_tiler(work_area, len(windows)):
            window = windows[i]
            # add gap
            if gap:
                if left == wr.left:
                    left += gap
                if top == wr.top:
                    top += gap
                if right == wr.right:
                    right -= gap
                if bottom == wr.bottom:
                    bottom -= gap
            left += gap
            top += gap
            right -= gap
            bottom -= gap
            rect = RECT(left, top, right, bottom)
            logger.debug("arrange %s %s", window, rect)
            window.set_rect(rect)
            i += 1
            if window.dpi_awareness != ProcessDpiAwareness.PROCESS_PER_MONITOR_DPI_AWARE:
                # seems like the `get_extended_frame_bounds` would return physical size 
                # for DPI unware window, skip them for now
                # TODO: convert physical size to logical size for DPI unware window
                continue
            # compensation
            r = window.get_rect()
            b = window.get_extended_frame_bounds()
            compensated_rect = (
                round(left + r.left - b.left),
                round(top + r.top - b.top),
                round(right + r.right - b.right),
                round(bottom + r.bottom - b.bottom),
            )
            window.set_rect(RECT(*compensated_rect))

    def restrict(self, theme: Optional[Theme] = None):
        """Restrict all managed windows to their specified rect"""
        theme = theme or self.get_theme()
        if not theme.strict:
            return
        for window in self.windows:
            window.restrict()


class VirtDeskState:
    """VirtDeskState holds variables needed by a Virtual Desktop

    :param WindowManager manager: associated WindowManager
    :param bytearray desktop_id: virtual desktop id
    """

    desktop_id: bytearray
    managed_windows: Set[Window]
    monitors: Dict[Monitor, MonitorState]
    last_active_window: Optional[Window] = None
    themes: List[Theme]

    def __init__(self, get_theme: Callable[[str], Theme], desktop_id: bytearray, themes: List[Theme]):
        self.desktop_id = desktop_id
        self.managed_windows = set()
        self.monitors = {}
        self.last_active_window = None
        self.get_theme = get_theme
        self.themes = themes

    def get_monitor(self, monitor: Monitor) -> MonitorState:
        """Retrieves the monitor state for the specified monitor in the virtual desktop

        :param Monitor monitor: monitor
        :returns: monitor state
        :rtype: MonitorState
        """
        monitor_state = self.monitors.get(monitor)
        if monitor_state is None:
            theme = sorted(self.themes, key=lambda x: x.affinity_index(monitor.get_screen_info()), reverse=True)[0]
            logger.info("default to theme %s for monito %s", theme.name, monitor.name)
            monitor_state = MonitorState(self, monitor, theme=theme.name)
            self.monitors[monitor] = monitor_state
        return monitor_state

    def get_managed_active_window(self) -> Optional[Window]:
        """Retrieves the managed forground window if any"""
        window = get_active_window()
        logger.debug("get_managed_active_window: active window %s", window)
        if window is None:
            return None
        if window not in self.managed_windows:
            logger.debug(
                "get_managed_active_window: active window is NOT managed %s", window
            )
            return None
        return window

    def get_last_managed_active_window(self) -> Optional[Window]:
        """Retrieves the latest managed forground window if any"""
        if self.last_active_window and (
            self.last_active_window not in self.managed_windows
            or not self.last_active_window.exists()
        ):
            return None
        return self.last_active_window

    def find_owner(self, window: Window) -> Optional[MonitorState]:
        """Retrieves the windows list containing specified window and its index in the list"""
        monitor = get_monitor_from_window(window.handle)
        monitor_state = self.get_monitor(monitor)
        if window in monitor_state.windows:
            return monitor_state
        return None
