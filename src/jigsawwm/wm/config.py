"""This module contains the configuration dataclass for the window manager"""
import re
import logging
from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional
from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window
from .theme import Theme

logger = logging.getLogger(__name__)


@dataclass
class WmRule:
    """WmRule holds the rule for managing windows"""
    exe_regex: Optional[str] = None
    title_regex: Optional[str] = None
    to_monitor_index: Optional[int] = None
    to_workspace_index: Optional[int] = None
    manageable: Optional[bool] = None # managed in workspace
    tilable: Optional[bool] = None # is it tilable in a workspace

@dataclass
class WmConfig:
    """WmConfig holds the configuration of the window manager"""
    themes: List[Theme] = None
    ignore_exe_names: Set[str] = None
    force_managed_exe_names: Set[str] = None
    init_exe_sequence: List[List[str]] = None
    workspace_names: List[str] = field(default_factory=lambda: ["0", "1", "2", "3"])
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

    def find_rule_for_window(self, window: Window) -> Optional[WmRule]:
        """Find the rule for the window"""
        if not self._rules_regexs:
            return
        for i, regexs in enumerate(self._rules_regexs):
            exe_regex, title_regex = regexs
            window_exe = window.exe
            if window_exe and exe_regex and not exe_regex.search(window_exe):
                continue
            if title_regex and not title_regex.search(window.title):
                continue
            return self.rules[i]
