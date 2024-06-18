"""This module contains the configuration dataclass for the window manager"""
import re
import pickle
import logging
import struct
from os import path
from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional, Tuple
from multiprocessing.shared_memory import SharedMemory
from ctypes.wintypes import HWND
from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window, is_window
from .theme import Theme

logger = logging.getLogger(__name__)

@dataclass
class WmRule:
    """WmRule holds the rule for managing windows"""
    exe_regex: Optional[str] = None
    title_regex: Optional[str] = None
    to_monitor_index: Optional[int] = 0
    to_workspace_index: Optional[int] = 0

@dataclass
class WmConfig:
    """WmConfig holds the configuration of the window manager"""
    themes: List[Theme] = None
    ignore_exe_names: Set[str] = None
    force_managed_exe_names: Set[str] = None
    init_exe_sequence: List[List[str]] = None
    workspace_names: List[str] = field(default_factory=lambda: ["1", "2", "3", "4"])
    rules: Optional[List[WmRule]] = None
    _monitor_themes: Dict[str, Theme] = field(default_factory=dict)
    _rules_regexs: List[List[re.Pattern]] = None
    _shared_memory: SharedMemory = None
    _windows_state: Dict[HWND, Tuple[str, str, bool]] = None

    def prepare(self):
        """Prepare the configuration"""
        if self.rules:
            self._rules_regexs = []
            for rule in self.rules:
                self._rules_regexs.append([
                    re.compile(rule.exe_regex) if rule.exe_regex else None,
                    re.compile(rule.title_regex) if rule.title_regex else None
                ])
        try:
            self._shared_memory = SharedMemory("jigsawwm.windows.state", create=True, size=128 * 1024)
        except FileExistsError:
            self._shared_memory = SharedMemory("jigsawwm.windows.state", size=128 * 1024)
        self._windows_state = {}
        self.load_from_shared_memory()

    def get_theme_index(self, theme_name: str) -> int:
        """Retrieves the index of given theme name, useful to switching theme"""
        i = len(self.themes) - 1
        while i > 0:
            if self.themes[i].name == theme_name:
                return i
            i -= 1
        return i

    def get_theme_by_name(self, theme_name: str) -> Theme:
        """Retrieves the theme by name"""
        for theme in self.themes:
            if theme.name == theme_name:
                return theme
        return self.themes[0]

    def get_theme_for_monitor(self, monitor: Monitor) -> Theme:
        """Retrieves the theme with the highest affinity index for the monitor"""
        if monitor.name not in self._monitor_themes:
            self._monitor_themes[monitor.name] = sorted(
                self.themes,
                key=lambda x: x.affinity_index(monitor.get_screen_info()), reverse=True
            )[0]
        return self._monitor_themes[monitor.name]

    def get_theme_for_workspace(self, monitor: Monitor, _workspace_name: str) -> Theme:
        """Retrieves the theme for the workspace"""
        return self.get_theme_for_monitor(monitor)

    def is_window_manageable(self, window: Window) -> bool:
        """Check if window is to be managed"""
        exebasename = path.basename(window.exe)
        if self.force_managed_exe_names:
            if exebasename in self.force_managed_exe_names:
                return True
        if self.ignore_exe_names:
            if exebasename in self.ignore_exe_names:
                return False
        return True

    def find_rule_for_window(self, window: Window) -> Optional[WmRule]:
        """Find the rule for the window"""
        if not self._rules_regexs:
            return
        for i, regexs in enumerate(self._rules_regexs):
            exe_regex, title_regex = regexs
            if exe_regex and not exe_regex.search(window.exe):
                continue
            if title_regex and not title_regex.search(window.title):
                continue
            return self.rules[i]

    def find_window_state(self, hwnd: HWND) -> Tuple[str, str, bool]:
        """Find the monitor and workspace name for the window across sessions"""
        return self._windows_state.get(hwnd, (None, None, False))

    def save_windows_state(self, windows: List[Window], monitor_name: str, workspace_name: str, show: bool):
        """Mark the windows as hidden"""
        for hwnd in list(self._windows_state.keys()):
            # clean up windows that do not exit anymore
            if not is_window(hwnd):
                self._windows_state.pop(hwnd)
        # update list
        for window in windows:
            self._windows_state[window.handle] = (monitor_name, workspace_name, show)
        self.save_to_shared_memory()

    def save_to_shared_memory(self):
        """Save the windows state to shared memory"""
        buffer = pickle.dumps(self._windows_state)
        if len(buffer) > self._shared_memory.size:
            raise ValueError("windows state too large")
        length = len(buffer)
        struct.pack_into("I", self._shared_memory.buf, 0, length)
        self._shared_memory.buf[4:4+length] = buffer
        logger.info("save_to_shared_memory")

    def load_from_shared_memory(self):
        """Load the windows state from shared memory"""
        length, = struct.unpack_from("I", self._shared_memory.buf, 0)
        if length > 0:
            self._windows_state = pickle.loads(bytes(self._shared_memory.buf[4:4+length]))
        logger.info("load_from_shared_memory")

if __name__ == "__main__":
    config = WmConfig()
    config.prepare()
    try:
        mn, wn, sh = config.find_window_state(1)
        print("loaded from previous session: monitor_name", mn, "workspace_name", wn, "show", sh)
    except:
        config.save_windows_state([Window(1)], "display1", "workspace2", False)
        print("saved in first session")
