import os
from datetime import datetime, time
from typing import Optional

from jigsawwm.state import get_state_manager
from jigsawwm.w32.process import is_exe_running


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


def start_if_not_running(exe_path: str):
    """Returns True if the given name has not been called today"""
    if not is_exe_running(exe_path):
        os.startfile(exe_path)
