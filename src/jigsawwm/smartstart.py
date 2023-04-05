import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Union

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


def daily_once(name: str):
    today = datetime.today().date()
    state = get_state_manager()
    last_date = state.getdate("daily", name)
    state.setdate("daily", name, today)
    state.save()
    return last_date != today


Launch = Union[str, Callable]


@dataclass
class SmartStartEntry:
    name: str
    launch: Launch
    condition: Callable[[], bool]

    def __call__(self):
        if self.condition and not self.condition():
            return
        self.run_anyway()

    def run_anyway(self):
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


_all_smart_start: Dict[str, SmartStartEntry] = dict()


def smart_start(
    name: str, launch: Union[Launch, List[Launch]], condition: Callable[[], bool]
):
    global _all_smart_start
    if name in _all_smart_start:
        raise ValueError(f"smart_start: {name} already exists")
    entry = SmartStartEntry(name, launch, condition)
    _all_smart_start[name] = entry
    entry()


def get_all_smart_start():
    return _all_smart_start.values()


if __name__ == "__main__":
    # open_chrome_fav_folder("bookmark_bar", "daily")
    print("daily once", daily_once("test"))
    print("daily once", daily_once("test"))
