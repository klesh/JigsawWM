"""Manage persisten state"""

import os
from configparser import ConfigParser
from datetime import date
from typing import Optional

DEFAULT_STATE_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "jigsawwm", "state.json")


class StateManager:
    """Manage persisten state"""

    config: ConfigParser
    state_path: str

    def __init__(self, state_path: str = DEFAULT_STATE_PATH):
        self.config = ConfigParser()
        self.state_path = state_path
        self.load()

    def load(self):
        """load state from disk"""
        if os.path.exists(self.state_path):
            self.config.read(self.state_path, encoding="utf-8")

    def save(self):
        """save state to disk"""
        if not os.path.exists(self.state_path):
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w+", encoding="utf8") as f:
            self.config.write(f)

    def get(self, section: str, option: str, default: str = None) -> str:
        """get state by key"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        return self.config.get(section, option, fallback=default)

    def set(self, section: str, option: str, value: str = None):
        """set state by key"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)

    def getbool(self, section: str, option: str, default: bool = False) -> bool:
        """get state as boolean"""
        return bool(self.get(section, option, default))

    def setbool(self, section: str, option: str, value: bool):
        """set state by boolean"""
        self.set(section, option, str(value).lower())

    def getdate(
        self, section: str, option: str, default: date = None
    ) -> Optional[date]:
        """get state as date"""
        d = self.get(section, option, default)
        if d:
            return date.fromisoformat(d)
        return None

    def setdate(self, section: str, option: str, value: Optional[date] = None):
        """set state as date"""
        self.set(section, option, value.isoformat() if value else None)


state_manager = StateManager(DEFAULT_STATE_PATH)
