"""WindowManagerCore is the core of the WindowManager, it manages the windows"""
import logging
import time
from typing import Dict, List, Set, Tuple, Optional
from queue import SimpleQueue
from threading import Thread

from jigsawwm.w32 import hook
from jigsawwm.w32.monitor import (
    Monitor,
    get_monitor_from_window,
    get_monitors,
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
    get_active_window,
)
from jigsawwm.w32.monitor import get_monitor_from_cursor
from jigsawwm.w32.winevent import WinEvent
from jigsawwm.jmk import sysinout, Vk
from jigsawwm import ui

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
    _managed_windows: Set[Window] = set()
    _queue: Optional[SimpleQueue]  = None
    _consumer: Optional[Thread] = None

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

    def get_active_monitor_state(self) -> MonitorState:
        """Get active monitor state"""
        monitor = get_monitor_from_cursor()
        return self.virtdesk_state.get_monitor_state(monitor)

    def get_active_window(self) -> Tuple[Window, MonitorState]:
        """Get active windows"""
        logger.debug("get_active_window")
        monitor_state = self.get_active_monitor_state()
        if not monitor_state.windows:
            return None, None
        window = get_active_window()
        if window and window not in monitor_state.windows:
            return None, None
        return window, monitor_state

    def start(self):
        """Start the WindowManagerCore service"""
        self.config.prepare()
        self._queue = SimpleQueue()
        self._consumer = Thread(target=self._consume_events)
        self._consumer.start()
        self.sync_windows(init=True)
        self.install_hooks()
        ui.on_screen_changed(self.sync_windows)
    
    def stop(self):
        """Stop the WindowManagerCore service"""
        ui.on_screen_changed(None)
        self.uninstall_hooks()
        self._queue.put(False)
        self._consumer.join()

    def _consume_events(self):
        while True:
            try:
                # wait for the next task
                event = self._queue.get()
                if not event:
                    break # terminate
                # clear the queue
                events = [event]
                while not self._queue.empty():
                    event = self._queue.get_nowait()
                    if not event:
                        break # terminate
                    events.append(event)
                if self.any_interesting_event(events):
                    time.sleep(0.1)
                    self.sync_windows()
            except : # pylint: disable=bare-except
                logger.exception("consume_queue error", exc_info=True)
    
    def any_interesting_event(self, events: List[Tuple[WinEvent, HWND]]) -> bool:
        """Check if any event is interesting"""
        for event, hwnd in events:
            # ignore if left mouse button is pressed in case of dragging
            if event == WinEvent.EVENT_OBJECT_PARENTCHANGE and sysinout.state.get( Vk.LBUTTON )  :
                # delay the sync until button released to avoid flickering
                logger.debug("wait_mouse_released on event %s", event.name)
                self._wait_mouse_released = True
                return False
            elif self._wait_mouse_released:
                logger.debug("mouse_released on event %s", event.name)
                if not sysinout.state.get( Vk.LBUTTON ):
                    self._wait_mouse_released = False
                    return True
                else:
                    return False
            # # filter by event
            window = Window(hwnd)
            if event == WinEvent.EVENT_OBJECT_SHOW or event == WinEvent.EVENT_OBJECT_UNCLOAKED:
                # restore telegram from the traybar only trigger EVENT_OBJECT_UNCLOAKED
                if not self.is_window_manageable(window):
                    return False
                # a window belongs to hidden workspace just got activated
                # put your default browser into workspace and then ctrl-click the link http://google.com 
                monitor_name, workspace_name, show = self.config.find_window_state(window.handle)
                if monitor_name and workspace_name and not show:
                    logger.debug("switch workspace for activated window to %s %s", monitor_name, workspace_name)
                    monitor_state= self.virtdesk_state.get_monitor_state_by_name(monitor_name)
                    monitor_state.switch_workspace_by_name(workspace_name)
                    return False
            elif event == WinEvent.EVENT_OBJECT_HIDE: # same as above
                # when window is hidden or destryed, it would not pass the is_window_manageable check
                # fix case: toggle chrome fullscreen
                if window not in self._managed_windows:
                    return False
            # elif event == WinEvent.EVENT_SYSTEM_MOVESIZEEND:
            #     return self.restrict(hwnd)
            elif event not in (
                WinEvent.EVENT_SYSTEM_MINIMIZESTART,
                WinEvent.EVENT_SYSTEM_MINIMIZEEND,
                WinEvent.EVENT_SYSTEM_MOVESIZEEND, # fix case: resizing any app window
            ):
                if event not in (
                    WinEvent.EVENT_OBJECT_LOCATIONCHANGE,
                    WinEvent.EVENT_OBJECT_NAMECHANGE,
                    WinEvent.EVENT_OBJECT_CREATE,
                    WinEvent.EVENT_SYSTEM_MENUSTART,
                    WinEvent.EVENT_SYSTEM_MENUEND,
                    WinEvent.EVENT_OBJECT_REORDER,
                    WinEvent.EVENT_SYSTEM_CAPTURESTART,
                    WinEvent.EVENT_SYSTEM_CAPTUREEND,
                ):
                    logger.debug("ignore winevent %s", event.name)
                return False

            logger.info("sync_windows on event %s", event.name)
            return True
        return False

    def sync_windows(self, init=False) -> bool:
        """Synchronize internal windows state to the system state synchronously"""
        logger.debug("sync_windows init %s", init)
        virtdesk_state = self.virtdesk_state
        # gather all manageable windows
        manageable_windows = set(self.get_manageable_windows())
        # sync monitors
        monitors = set(get_monitors())
        group_wins_by_mons: Dict[Monitor, Set[Window]] = {
            monitor: set() for monitor in monitors
        }
        removed_monitors = set(virtdesk_state.monitor_states.keys()) - monitors
        for removed_monitor in removed_monitors:
            removed_state = virtdesk_state.monitor_states.pop(removed_monitor)
            for workspace in removed_state.workspaces:
                # unhide all windows in the workspace and append them to the list
                # to be re-arranged
                for window in workspace.windows:
                    logger.debug("unhide %s", window)
                    window.show()
                    manageable_windows.add(window)
        if not manageable_windows:
            return
        # group manageable windows by their current monitor
        monitors = list(monitors)
        self._managed_windows = set()
        for window in manageable_windows:
            self._managed_windows.add(window)
            monitor = (
                virtdesk_state.find_monitor_of_window(window) # window has been managed
                or self.find_monitor_from_config(window, monitors) # window has a rule
                or (init and get_monitor_from_window(window.handle)) # fallback: window existing before manager start
                or get_monitor_from_cursor() #  fallback: window appearing after manager start
            )
            # add window to lists
            group_wins_by_mons[monitor].add(window)
            logger.debug("%s owns %s", monitor, window)
        # synchronize windows on each monitor
        # pass down to monitor_state for further synchronization
        for monitor, windows in group_wins_by_mons.items():
            monitor_state = virtdesk_state.get_monitor_state(monitor)
            monitor_state.sync_windows(windows)

    def find_monitor_from_config(self, window: Window, monitors: List[Monitor]) -> Optional[Monitor]:
        """Find monitor from the config rules for the window"""
        logger.debug("find_monitor_from_config %s", window)
        rule = self.config.find_rule_for_window(window)
        if rule:
            logger.debug("rule %s found for %s", rule, window)
            window.attrs["rule"] = rule
            if len(monitors) > rule.to_monitor_index:
                return monitors[rule.to_monitor_index]
        logger.debug("no rule found for %s", window)
        return None

    def get_manageable_windows(self) -> List[Window]:
        """Retrieve all manageable windows"""
        def check_window(hwnd: HWND) -> EnumCheckResult:
            window = Window(hwnd)
            if self.is_window_manageable(window):
                logger.debug("manageable %s", window)
                return EnumCheckResult.CAPTURE
            return EnumCheckResult.SKIP
        return map(Window, enum_windows(check_window))
    
    def is_window_manageable(self, window: Window) -> bool:
        """Check if the window is manageable by the WindowManager"""
        return window.title and is_app_window(window.handle) and self.config.is_window_manageable(window)

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
        self._queue.put_nowait((event, hwnd))

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
