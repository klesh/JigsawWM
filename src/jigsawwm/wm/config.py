"""This module contains the configuration dataclass for the window manager"""
from os import path
from dataclasses import dataclass, field
from typing import Set, List, Dict
from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window
from .theme import Theme


@dataclass
class WmConfig:
    """WmConfig holds the configuration of the window manager"""
    themes: List[Theme]
    ignore_exe_names: Set[str]
    force_managed_exe_names: Set[str]
    init_exe_sequence: List[List[str]]
    workspace_names: List[str] = field(default_factory=lambda: ["1", "2", "3", "4"])
    _workspace_theme_cache: Dict[str, Theme] = field(default_factory=dict)

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
        return sorted(self.themes, key=lambda x: x.affinity_index(monitor.get_screen_info()), reverse=True)[0]

    def get_theme_for_workspace(self, monitor: Monitor, workspace_name: str) -> Theme:
        """Retrieves the theme for the workspace"""
        key = f'{monitor.name}_{workspace_name}'
        if key not in self._workspace_theme_cache:
            self._workspace_theme_cache[key] = self.get_theme_for_monitor(monitor)
        return self._workspace_theme_cache[key]


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