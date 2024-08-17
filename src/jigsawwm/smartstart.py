import logging
from datetime import datetime, time
from typing import Optional
import subprocess

from jigsawwm.state import get_state_manager
from jigsawwm.w32.process import is_exe_running

logger = logging.getLogger(__name__)


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


def start_if_not_running(exe_path: str, name_only: bool=True):
    """Returns True if the given name has not been called today"""
    if not is_exe_running(exe_path, name_only):
        # os.startfile(exe_path) # behaviors changed: app would be killed in 2024-08-16 win11 update
        r = subprocess.run(["start", exe_path], shell=True, check=False)
        if r.returncode != 0:
            logger.error("Failed to start %s, err: %s, out: %s, code: %s", exe_path, r.stderr, r.stdout, r.returncode)
