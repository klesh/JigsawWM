"""WindowManagerCore is the core of the WindowManager, it manages the windows"""
import logging
from typing import Dict, List, Set, Tuple, Optional

from jigsawwm.w32 import hook
from jigsawwm.w32.monitor import (
    Monitor,
    get_monitor_from_window,
)
from jigsawwm.w32.reg import get_current_desktop_id
from jigsawwm.w32.window import (
    DWORD,
    HWND,
    LONG,
    Window,
    is_app_window,
    enum_windows,
    EnumCheckResult,
    get_foreground_window,
)
from jigsawwm.w32.monitor import get_monitor_from_cursor, get_topo_sorted_monitors
from jigsawwm.w32.winevent import WinEvent
from jigsawwm.jmk import sysinout, Vk

from .virtdesk_state import VirtDeskState, MonitorState
from .config import WmConfig

logger = logging.getLogger(__name__)


class WindowManagerCore:
    """WindowManager detect the monitors/windows state and arrange them dynamically
    keep in mind that not all windows are managed by the WindowManager, only those
    returned by `jigsawwm.w32.get_normal_windows()` and not ignored would be managed.

    The WindowManager works just like other Dynamic Window Managers, it store all
    managed windows in a list, the first one in the list is called Master, it would
    normally take up most area of the screen while others occuppy the rest.

    :param List[Theme] themes: all avaiable themes for user to switch
    :param ignore_exe_names: list of executable filenames that you don't want them
                             to be managed/arranged
    :param init_exe_sequence: list of executable filenames and title search criteria
                              that are to be kept in exactly this order when
                              distributing into windows
    """

    virtdesk_states: Dict[bytearray, VirtDeskState]
    config: WmConfig
    _hook_ids: List[int] = []
    _wait_mouse_released: bool = False

    def __init__(
        self,
        config: WmConfig
    ):
        self.config = config
        self.virtdesk_states = {}

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

    def get_active_managed_winmon(self) -> Tuple[Window, MonitorState]:
        """Get active windows"""
        logger.debug("get_active_managed_winmon")
        hwnd = get_foreground_window()
        if hwnd:
            monitor = get_monitor_from_window(hwnd)
        else:
            monitor = get_monitor_from_cursor()
        monitor_state = self.virtdesk_state.get_monitor_state(monitor)
        if not monitor_state.windows:
            return None, monitor_state
        if not hwnd:
            return monitor_state.windows[0], monitor_state
        active_window = Window(hwnd)
        if active_window not in monitor_state.windows:
            return monitor_state.windows[0], monitor_state
        return active_window, monitor_state

    def get_monitor_state_by_offset(self, delta: int, src_monitor_state: Optional[MonitorState]=None) -> MonitorState:
        """Retrieves a pair of monitor_states, the current active one and its offset in the list"""
        if not src_monitor_state:
            _, src_monitor_state = self.get_active_managed_winmon()
        monitors = get_topo_sorted_monitors()
        src_idx = monitors.index(src_monitor_state.monitor)
        dst_idx = (src_idx + delta) % len(monitors)
        dst_monitor = monitors[dst_idx]
        dst_monitor_state = self.virtdesk_state.get_monitor_state(dst_monitor)
        return dst_monitor_state

    def start(self):
        """Start the WindowManagerCore service"""
        self.install_hooks()
        self.sync_windows(init=True)
    
    def stop(self):
        """Stop the WindowManagerCore service"""
        self.uninstall_hooks()

    def sync_windows(self, init=False) -> bool:
        """Synchronize internal windows state to the system state"""
        logger.debug("sync_windows")
        virtdesk_state = self.virtdesk_state
        # gather all manageable windows
        manageable_windows = self.get_manageable_windows()
        if not manageable_windows:
            return
        # group manageable windows by their current monitor
        group_wins_by_mons: Dict[Monitor, Set[Window]] = {}
        for window in manageable_windows:
            if init: # use the monitor of the window when starting up
                monitor = get_monitor_from_window(window.handle)
            else:
                monitor = virtdesk_state.find_monitor_of_window(window)
                if not monitor:
                    monitor = get_monitor_from_cursor()
            if monitor not in group_wins_by_mons:
                group_wins_by_mons[monitor] = set()
            # add window to lists
            group_wins_by_mons[monitor].add(window)
            logger.debug("%s owns %s", monitor, window)
        # synchronize windows on each monitor
        # pass down to monitor_state for further synchronization
        for monitor, windows in group_wins_by_mons.items():
            monitor_state = virtdesk_state.get_monitor_state(monitor)
            monitor_state.sync_windows(windows)

    def get_manageable_windows(self) -> List[Window]:
        """Retrieve all manageable windows"""
        return map(Window, enum_windows(
            lambda hwnd: EnumCheckResult.CAPTURE
            if self.is_window_manageable(Window(hwnd))
            else EnumCheckResult.SKIP
        ))
    
    def is_window_manageable(self, window: Window) -> bool:
        """Check if the window is manageable by the WindowManager"""
        return is_app_window(window.handle) and self.config.is_window_manageable(window)

    def unhide_workspaces(self):
        """Unhide all workspaces"""
        for virtdesk_state in self.virtdesk_states.values():
            for monitor_state in virtdesk_state.monitor_states.values():
                monitor_state.unhide_workspaces()

    def _winevent_callback(
        self,
        event: WinEvent,
        hwnd: HWND,
        _id_obj: LONG,
        _id_chd: LONG,
        _id_evt_thread: DWORD,
        _evt_time: DWORD,
    ):
        # ignore if left mouse button is pressed in case of dragging
        force_sync = False
        if sysinout.state.get( Vk.LBUTTON ) and event == WinEvent.EVENT_SYSTEM_MOVESIZEEND:
            # delay the sync until button released to avoid flickering
            self._wait_mouse_released = True
            return
        elif self._wait_mouse_released:
            if not sysinout.state.get( Vk.LBUTTON ):
                self._wait_mouse_released = False
                force_sync = True
            else:
                return
        if force_sync:
            logger.debug("force sync")
            self.sync()
            return
        # # filter by event
        # if event not in (
        #     WinEvent.EVENT_OBJECT_LOCATIONCHANGE,
        #     WinEvent.EVENT_OBJECT_NAMECHANGE,
        # ):
        #     logger.warning(
        #         "[A] event: %30s hwnd: %8s id_obj: %8x id_chd: %8x id_evt_thread: %8d title: %s",
        #         event.name, hwnd, id_obj, id_chd, id_evt_thread, get_window_title(hwnd)
        #     )
        window = Window(hwnd)
        if event == WinEvent.EVENT_OBJECT_SHOW: # for app that minimized to tray, show event is the only way to detect
            if not self.is_window_manageable(window):
                return
        elif event == WinEvent.EVENT_OBJECT_HIDE: # same as above
            if not self.is_window_manageable(window):
                return
        # elif event == WinEvent.EVENT_SYSTEM_MOVESIZEEND:
        #     return self.restrict()
        elif event not in (
            WinEvent.EVENT_SYSTEM_MINIMIZESTART,
            WinEvent.EVENT_SYSTEM_MINIMIZEEND,
        ):
            return

        self.sync_windows()

    def install_hooks(self):
        """Install hooks for window events"""
        self._hook_ids = [
            hook.hook_winevent(
                WinEvent.EVENT_MIN,
                WinEvent.EVENT_MAX,
                self._winevent_callback,
            ),
        ]

    def uninstall_hooks(self):
        """Uninstall hooks for window events"""
        for hook_id in self._hook_ids:
            hook.unhook_winevent(hook_id)
        self._hook_ids = []
        self.unhide_workspaces()
