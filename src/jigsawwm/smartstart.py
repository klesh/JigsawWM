import json
import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable, Dict, List, Optional, Union

from jigsawwm.state import get_state_manager
from jigsawwm.w32.process import is_exe_running


def open_chrome_fav_folder(root, fav_folder):
    """Opens the Chrome Favorites folder"""
    path = os.path.join(
        os.getenv("LOCALAPPDATA"),
        "Google",
        "Chrome",
        "User Data",
        "Default",
        "Bookmarks",
    )
    bookmarks = None
    with open(path, encoding="utf8") as f:
        bookmarks = json.load(f)

    # open folder recursively
    def open_folder(folder):
        for child in folder["children"]:
            if child.get("type") == "url":
                os.startfile(child["url"])
            else:
                open_folder(child)

    # locate the initial folder
    folder = bookmarks["roots"][root]
    for component in fav_folder.split("."):
        for child in folder["children"]:
            if child["name"] == component and child["type"] == "folder":
                folder = child
                break
    open_folder(folder)


def daily_once(name: str, day_start: Optional[time] = time(hour=8)):
    """Returns True if the given name has not been called today"""
    now = datetime.now().astimezone()
    if now.time() < day_start:
        return False
    today = now.date()
    state = get_state_manager()
    last_date = state.getdate("daily", name)
    state.setdate("daily", name, today)
    state.save()
    return last_date != today


Launch = Union[str, Callable]


@dataclass
class SmartStartEntry:
    """A smart start entry, which will only run when the condition is true

    :param str name: the name of the entry
    :param Union[Launch, List[Launch]] launch: the launch item
    :param Callable condition: the condition to check
    """

    name: str
    launch: Union[Launch, List[Launch]]
    condition: Callable[[], bool]

    def __call__(self):
        if self.condition and not self.condition():
            return
        self.run_anyway()

    def run_anyway(self):
        """Runs the launch item regardless of the condition"""

        def launch(launch):
            if isinstance(launch, str):
                if not is_exe_running(launch):
                    os.startfile(launch)
            elif callable(launch):
                launch()

        if isinstance(self.launch, list):
            for item in self.launch:
                launch(item)
        else:
            launch(self.launch)


class SmartStartManager:
    _smartstarts: Dict[str, SmartStartEntry]

    def __init__(self):
        self._smartstarts = dict()

    def register(
        self,
        entry=SmartStartEntry,
    ):
        """Registers a smart start entry"""
        if entry.name in self._smartstarts:
            raise ValueError(f"smart_start: {entry.name} already exists")
        self._smartstarts[entry.name] = entry
        entry()

    def get_all(self):
        """Returns all smart start entries"""
        return self._smartstarts.values()


smartstart = SmartStartManager()
register_smartstart = smartstart.register
get_smartstarts = smartstart.get_all

if __name__ == "__main__":
    # open_chrome_fav_folder("bookmark_bar", "daily")
    print("daily once", daily_once("test"))
    print("daily once", daily_once("test"))
