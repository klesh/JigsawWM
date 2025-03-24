"""Virtual Desktop State module"""

import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

from jigsawwm.ui.splash import Splash
from jigsawwm.w32.monitor import set_cursor_pos
from jigsawwm.w32.monitor_detector import Monitor, MonitorDetector
from jigsawwm.w32.window import topo_sort_windows
from jigsawwm.w32.window_detector import Window, WindowDetector

from .config import WmConfig
from .const import (
    MONITOR_STATE,
    PREFERRED_MONITOR_INDEX,
    PREFERRED_WINDOW_INDEX,
    PREFERRED_WORKSPACE_INDEX,
    STATIC_WINDOW_INDEX,
    WORKSPACE_STATE,
)
from .monitor_state import MonitorState
from .workspace_state import WorkspaceState

logger = logging.getLogger(__name__)


class VirtDeskState:
    """VirtDeskState holds variables needed by a Virtual Desktop

    :param WindowManager manager: associated WindowManager
    :param bytearray desktop_id: virtual desktop id
    """

    desktop_id: bytearray
    config: WmConfig
    monitor_states: Dict[Monitor, MonitorState] = {}
    window_detector: WindowDetector
    monitor_detector: MonitorDetector
    no_ws_switching_untill = 0

    def __init__(self, desktop_id: bytearray, config: WmConfig, splash: Splash):
        self.desktop_id = desktop_id
        self.window_detector = WindowDetector(created=self.apply_rule_to_window)
        self.monitor_detector = MonitorDetector()
        self.config = config
        self.splash = splash

    def on_monitors_changed(self):
        """Syncs the monitor states with the virtual desktop"""
        result = self.monitor_detector.detect_monitor_changes()
        if not result.changed:
            logger.info("no monitor changes detected")
            return
        windows_tobe_rearranged = set()
        # process new monitors
        if result.new_monitors:
            windows_tobe_rearranged = self.window_detector.windows
            for m in result.new_monitors:
                monitor_index = self.monitor_detector.monitors.index(m)
                logger.info("new monitor connected: %s index: %d", m, monitor_index)
                self.monitor_states[m] = MonitorState(
                    index=monitor_index,
                    name=m.name,
                    workspace_names=self.config.workspace_names,
                    monitor=m,
                    theme=self.config.get_theme_for_monitor(m),
                )
        # remove monitor states
        if result.removed_monitors:
            for m in result.removed_monitors:
                ms = self.monitor_states.pop(m)
                logger.info("monitor disconnected: %s", ms.name)
                for ws in ms.workspaces:
                    windows_tobe_rearranged |= ws.windows
        # rearrange windows
        mi = self.monitor_detector.monitors.index(
            self.monitor_detector.monitor_from_cursor()
        )
        for w in windows_tobe_rearranged:
            msi = w.attrs.get(PREFERRED_MONITOR_INDEX, mi)
            ms = self.monitor_state_from_index(msi)
            wsi = w.attrs.get(PREFERRED_WORKSPACE_INDEX, ms.active_workspace_index)
            ms.add_window(w, wsi)
        for ms in self.monitor_states.values():
            ms.workspace.sync_windows()

    def on_windows_changed(self, starting_up=False):
        """Syncs the window states with the virtual desktop"""
        if not self.monitor_states:
            logger.warning("no monitors found")
            return
        result = self.window_detector.detect_window_changes()
        if not result.changed:
            logger.info("no window changes detected")
            return
        # handle new windows
        monitor_state = self.monitor_state_from_cursor()
        if result.new_windows:
            if starting_up:
                self.distribute_windows_on_starting_up(result.new_windows)
            else:
                self.distribute_new_windows(result.new_windows)
        # handle removed windows
        if result.removed_windows:
            logger.info("window disappeared: %s", result.removed_windows)
            for w in result.removed_windows:
                if MONITOR_STATE not in w.attrs:
                    logger.warning("window %s has no monitor state", w)
                    continue
                monitor_state: MonitorState = w.attrs[MONITOR_STATE]
                monitor_state.remove_window(w)
        for ms in self.monitor_states.values():
            ms.workspace.sync_windows()

    def apply_rule_to_window(self, window: Window) -> bool:
        """Apply rule to window"""
        if not window.applicable:
            return
        rule = self.config.find_rule_for_window(window)
        if rule:
            logger.debug("applying rule %s on %s", rule, window)
            if rule.manageable is not None:
                window.manageable = rule.manageable
            if rule.tilable is not None:
                window.tilable = rule.tilable
            if rule.preferred_monitor_index is not None:
                window.attrs[PREFERRED_MONITOR_INDEX] = (
                    rule.preferred_monitor_index % len(self.monitor_detector.monitors)
                )
            if rule.preferred_workspace_index is not None:
                window.attrs[PREFERRED_WORKSPACE_INDEX] = rule.preferred_workspace_index
            if rule.static_window_index is not None:
                window.attrs[STATIC_WINDOW_INDEX] = rule.static_window_index

    def distribute_windows_on_starting_up(self, windows: List[Window]):
        """Distribute windows on starting up JigsawWM - respect the current windows' positions"""
        logger.info("distributing windows on starting up")
        root_windows = [w for w in windows if not w.parent]
        for i, w in enumerate(topo_sort_windows(root_windows)):
            m = self.monitor_detector.monitor_from_window(w.handle)
            if m:
                ms = self.monitor_states[m]
                ms.assign_window(w, window_index=i)
        self.reclaim_hidden_workspaces()
        for m in self.monitor_states.values():
            m.workspace.sync_windows()

    def reclaim_hidden_workspaces(self):
        """Reclaim previously hidden workspaces"""
        # reclaim previously hidden workspace
        logger.info("reclaiming hidden workspaces")
        for w in self.window_detector.get_invisible_windows():
            logger.debug("try to reclaim hidden window: %s", w)
            result = self.find_ws_for_hidden_window(w)
            if result:
                w.off = True
                ms, ws = result
                ms.assign_window(w, workspace=ws)
                w.attrs[PREFERRED_MONITOR_INDEX] = ms.index
                w.attrs[PREFERRED_WORKSPACE_INDEX] = ws.index
                self.window_detector.windows.add(w)

    def find_ws_for_hidden_window(
        self, window: Window
    ) -> Optional[Tuple[MonitorState, WorkspaceState]]:
        """Find workspace for hidden window"""
        rect = window.get_rect()
        if window.exe_name == "7zFM.exe":
            logger.debug("find workspace for hidden window: %s %s", window, rect)
        for ms in self.monitor_states.values():
            for ws in ms.workspaces:
                if ws.alter_rect.contains_rect_center(rect):
                    return ms, ws

    def distribute_new_windows(self, windows: List[Window]):
        """Distribute new windows to the right monitor and workspace - respect rules for windows"""
        logger.info("distributing new windows")
        for w in windows:
            logger.info("new window appeared: %s", w)
            if w.parent:
                self.distribute_window_by_parent(w)
            else:
                self.distribute_window_by_preferred(w)

    def distribute_window_by_parent(self, window: Window):
        """Distribute window to its parent's workspace"""
        logger.info("distributing %s to its parent's workspace", window)
        if MONITOR_STATE not in window.parent.attrs:
            logger.warning("parent window %s has no monitor state", window.parent)
            return
        ms: MonitorState = window.parent.attrs[MONITOR_STATE]
        ws: WorkspaceState = window.parent.attrs[WORKSPACE_STATE]
        ms.assign_window(window, workspace=ws)

    def distribute_window_by_preferred(self, window: Window):
        """Distribute window to the preferred monitor and workspace"""
        logger.info("distributing %s by its preferred", window)
        default_msi = self.monitor_state_from_cursor().index
        msi = window.attrs.get(PREFERRED_MONITOR_INDEX, default_msi)
        ms = self.monitor_state_from_index(msi)
        wsi = window.attrs.get(PREFERRED_WORKSPACE_INDEX, ms.active_workspace_index)
        ws = ms.workspaces[wsi]
        ms.assign_window(window, workspace=ws)

    def on_foreground_window_changed(self, window: Window):
        """Try to switch workspace for window activation"""
        # a window belongs to hidden workspace just got activated
        # put your default browser into workspace and then ctrl-click a link, e.g. http://google.com
        now = time.time()
        if now < self.splash.hidden_at + 1:
            logger.warning(
                "splash hidden too fast might activate a hidden window, ignore it"
            )
            return
        if now < self.no_ws_switching_untill:
            # child windows got spread across multiple workspaces
            logger.warning("workspace switching happened too frequently, possible loop")
            return
        # closing window using taskbar right click menu would cause the window to be activated then closed
        if not window.exists():
            logger.warning("window doesn't %s exists", window)
        if MONITOR_STATE not in window.attrs:
            logger.warning("window %s has no monitor state", window)
            return
        ms: MonitorState = window.attrs[MONITOR_STATE]
        ws: WorkspaceState = window.attrs[WORKSPACE_STATE]
        ws.last_active_window = window
        if not ws.showing:
            self.no_ws_switching_untill = now + 1
            ms.switch_workspace(ws.index)
            logger.info(
                "switch to workspace %s due window %s got activated",
                ws,
                window,
            )

    def on_minimize_changed(self, window: Window):
        """Handle window minimized event"""
        ws: WorkspaceState = window.attrs.get(WORKSPACE_STATE)
        if ws:
            ws.sync_windows()

    def monitor_state_from_cursor(self) -> MonitorState:
        """Retrieve monitor_state from current cursor"""
        m = self.monitor_detector.monitor_from_cursor()
        if m not in self.monitor_states:
            self.on_monitors_changed()
        return self.monitor_states[m]

    def monitor_state_from_index(self, index: int) -> MonitorState:
        """Retrieve monitor_state from index"""
        index = index % len(self.monitor_detector.monitors)
        return self.monitor_states[self.monitor_detector.monitors[index]]

    def reorder_windows(
        self,
        reorderer: Callable[[List[Window], int], None],
        idx: Optional[int] = None,
        workspace: Optional[WorkspaceState] = None,
        activate: bool = True,
    ):
        """Reorder windows"""
        if workspace is None:
            window = self.window_detector.foreground_window()
            while window.parent:
                window = window.parent
            if not window.manageable or not window.tilable:
                return
            workspace = window.attrs[WORKSPACE_STATE]
            if idx is None:
                idx = window.attrs[PREFERRED_WINDOW_INDEX]
        if len(workspace.tiling_windows) < 2:
            return
        window = workspace.tiling_windows[idx]
        next_active_window = reorderer(workspace.tiling_windows, idx)
        workspace.arrange()
        if activate:
            (next_active_window or window).activate()

    def swap_window(
        self,
        delta: int,
        idx: Optional[int] = None,
        workspace: Optional[WorkspaceState] = None,
        activate: bool = True,
    ):
        """Swap current active managed window with its sibling by offset"""

        def swap(windows: List[Window], src_idx: int):
            dst_idx = (src_idx + delta) % len(windows)
            windows[src_idx], windows[dst_idx] = windows[dst_idx], windows[src_idx]

        self.reorder_windows(swap, idx=idx, workspace=workspace, activate=activate)

    def roll_window(
        self,
        delta: int,
        activate: bool = True,
    ):
        """Roll the window as master"""

        delta = -1 if delta < 0 else 1

        def swap(windows: List[Window], _src_idx: int):
            idx = 0
            start_idx = 1
            end_idx = len(windows)
            step = 1

            if delta < 0:
                idx = len(windows) - 1
                start_idx = len(windows) - 2
                end_idx = -1
                step = -1

            tmp = windows[idx]
            for i in range(start_idx, end_idx, step):
                windows[i - step] = windows[i]
            windows[end_idx - step] = tmp
            return windows[0]

        self.reorder_windows(swap, activate=activate)

    def set_master(self):
        """Set the active active managed window as the Master back and forth"""

        def set_master(windows: List[Window], src_idx: int):
            if src_idx == 0:
                src_idx = windows[0].attrs.get("prev_index", 1)
            windows[0], windows[src_idx] = windows[src_idx], windows[0]
            windows[0].attrs["prev_index"] = src_idx
            return windows[0]

        self.reorder_windows(set_master)

    def toggle_tilable(self):
        """Toggle window tilable"""
        window = self.window_detector.foreground_window()
        window.tilable = not window.tilable
        if not window.tilable:
            window.shrink()
        if WORKSPACE_STATE not in window.attrs:
            self.monitor_state_from_cursor().assign_window(window)
        else:
            workspace_state: WorkspaceState = window.attrs[WORKSPACE_STATE]
            workspace_state.sync_windows()

    ########################################
    # Monitor related methods
    ########################################

    def switch_monitor(self, delta: int):
        """Switch to another monitor"""
        srcms = self.monitor_state_from_cursor()
        dstms = self.monitor_state_from_index(srcms.index + delta)
        window = dstms.workspace.last_active_window
        if not window and dstms.workspace.tiling_windows:
            window = dstms.workspace.tiling_windows[0]
        if window and window.exists():
            window.activate()
        else:
            set_cursor_pos(dstms.rect.center_x, dstms.rect.center_y)

    def move_to_monitor(
        self,
        delta: int = 0,
        window: Optional[Window] = None,
        dst_ms: Optional[MonitorState] = None,
    ):
        """Move window to another monitor"""
        if len(self.monitor_detector.monitors) < 2:
            return
        window = window or self.window_detector.foreground_window()
        if not window.manageable:
            return
        if MONITOR_STATE not in window.attrs:
            logger.warning("window %s has no monitor state", window)
            return
        src_ms: MonitorState = window.attrs[MONITOR_STATE]
        if dst_ms is None:
            preferred_monitor_index = (src_ms.index + delta) % len(
                self.monitor_detector.monitors
            )
            window.attrs[PREFERRED_MONITOR_INDEX] = preferred_monitor_index
            dst_ms = self.monitor_state_from_index(src_ms.index + delta)
        src_ms.remove_window(window)
        dst_ms.assign_window(window)
        src_ms.workspace.sync_windows()
        dst_ms.workspace.sync_windows()
        if delta and src_ms.workspace.tiling_windows:
            src_ms.workspace.tiling_windows[0].activate()

    ########################################
    # Workspace related methods
    ########################################

    def move_to_workspace(
        self,
        workspace_index: int,
        window: Optional[Window] = None,
        is_delta: bool = False,
    ):
        """Switch to a specific workspace"""
        window = window or self.window_detector.foreground_window()
        if not window.manageable:
            return
        if MONITOR_STATE not in window.attrs:
            logger.warning("window %s has no monitor state", window)
            return
        ms: MonitorState = window.attrs[MONITOR_STATE]
        ms.move_to_workspace(window, workspace_index, is_delta)
