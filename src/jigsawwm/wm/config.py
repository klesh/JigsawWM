"""This module contains the configuration dataclass for the window manager"""
import re
from os import path
from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional
from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window
from .theme import Theme


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
    themes: List[Theme]
    ignore_exe_names: Set[str]
    force_managed_exe_names: Set[str]
    init_exe_sequence: List[List[str]]
    workspace_names: List[str] = field(default_factory=lambda: ["1", "2", "3", "4"])
    rules: Optional[List[WmRule]] = None
    _monitor_themes: Dict[str, Theme] = field(default_factory=dict)
    _rules_regexs: List[List[re.Pattern]] = None

    def prepare(self):
        """Prepare the configuration"""
        if self.rules:
            self._rules_regexs = []
            for rule in self.rules:
                self._rules_regexs.append([
                    re.compile(rule.exe_regex) if rule.exe_regex else None,
                    re.compile(rule.title_regex) if rule.title_regex else None
                ])

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
