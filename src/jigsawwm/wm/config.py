"""This module contains the configuration dataclass for the window manager"""

import re
import logging
from typing import Set, List, Dict, Optional
from jigsawwm.w32.monitor import Monitor
from jigsawwm.w32.window import Window
from .theme import Theme, all_themes

logger = logging.getLogger(__name__)


class WmRule:
    """WmRule holds the rule for managing windows"""

    exe_regex: Optional[re.Pattern] = None
    title_regex: Optional[re.Pattern] = None
    exe_and_title: bool
    preferred_monitor_index: Optional[int] = None
    preferred_workspace_index: Optional[int] = None
    static_window_index: Optional[int] = None
    manageable: Optional[bool] = None  # managed in workspace
    tilable: Optional[bool] = None  # is it tilable in a workspace

    def __init__(
        self,
        exe: Optional[str] = None,
        exe_is_literal: bool = True,
        title: Optional[str] = None,
        title_is_literal: bool = True,
        exe_and_title: bool = True,
        preferred_monitor_index: Optional[int] = None,
        preferred_workspace_index: Optional[int] = None,
        static_window_index: Optional[int] = None,
        manageable: Optional[bool] = None,
        tilable: Optional[bool] = None,
    ):
        if exe:
            self.exe_regex = self.parse_pattern(exe, exe_is_literal)
        if title:
            self.title_regex = self.parse_pattern(title, title_is_literal)
        self.exe_and_title = exe_and_title
        self.preferred_monitor_index = preferred_monitor_index
        self.preferred_workspace_index = preferred_workspace_index
        self.static_window_index = static_window_index
        self.manageable = manageable
        self.tilable = tilable

    @staticmethod
    def parse_pattern(pattern: str, literal: bool) -> re.Pattern:
        """Parse regex pattern"""
        if literal:
            pattern = r"\b" + re.escape(pattern) + r"$"
        return re.compile(pattern, re.I)

    @staticmethod
    def match_pattern(pattern: Optional[re.Pattern], target: str) -> bool:
        """Match pattern"""
        if not pattern:
            return True
        if not target:
            return False
        return bool(pattern.search(str(target)))

    def match(self, window: Window) -> bool:
        """Check if window matches the rule"""
        exe_matched = self.match_pattern(self.exe_regex, window.exe)
        if exe_matched:
            if not self.exe_and_title:
                return True
            return exe_matched and self.match_pattern(self.title_regex, window.title)
        return False

    def __repr__(self):
        marks = ""
        if self.manageable:
            marks += "M"
        if self.tilable:
            marks += "T"
        if marks:
            marks = f" ({marks})"
        return f"<WmRule exe={self.exe_regex} title={self.title_regex} pmi={self.preferred_monitor_index} pwi={self.preferred_workspace_index}{marks}>"


class WmConfig:
    """WmConfig holds the configuration of the window manager"""

    themes: List[Theme] = None
    ignore_exe_names: Set[str] = None
    force_managed_exe_names: Set[str] = None
    workspace_names: List[str]
    rules: Optional[List[WmRule]] = None
    _monitor_themes: Dict[str, Theme]
    _rules_regexs: List[List[re.Pattern]] = None

    def __init__(self, themes: List[str] = None, rules: List[WmRule] = None):
        self.themes = (
            [t for t in all_themes if t.name in themes] if themes else all_themes
        )
        self.rules = rules
        self.workspace_names = ["0", "1", "2", "3"]
        self._monitor_themes = {}

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
                key=lambda x: x.affinity_index(monitor.get_screen_info()),
                reverse=True,
            )[0]
        return self._monitor_themes[monitor.name]

    def find_rule_for_window(self, window: Window) -> Optional[WmRule]:
        """Find the rule for the window"""
        for rule in self.rules:
            if rule.match(window):
                return rule
