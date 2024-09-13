"""Launch applications in a smart way, e.g. only once a day, or only if not running"""

import os
import subprocess
import logging
from datetime import datetime, time
from typing import Optional

from jigsawwm.w32.process import is_exe_running

from .state import state_manager

logger = logging.getLogger(__name__)


def is_today_done(task_name: str, day_start: Optional[time] = time(hour=8)):
    """Check if today task was done"""
    now = datetime.now().astimezone()
    if now.time() < day_start:
        logger.info("day has not yet started: %s", day_start)
        return False
    today = now.date()
    last_date = state_manager.getdate("daily", task_name)
    return last_date != today


def mark_today_done(task_name: str):
    """Set tody task done"""
    today = datetime.now().astimezone().date()
    state_manager.setdate("daily", task_name, today)
    state_manager.save()
    logger.info("today task %s has been marked as done", task_name)


def start_if_not_running(exe_path: str, name_only: bool = True):
    """Returns True if the given name has not been called today"""
    if not is_exe_running(exe_path, name_only):
        # after windows 11 updated on 2024-08-16
        # apps with space in path can be launched by os.startfile
        if " " in exe_path:
            os.startfile(
                exe_path
            )  # behaviors changed: app would be killed in  win11 update
        else:
            # however, other apps would be killed when jigsawwm exited
            r = subprocess.run(["start", exe_path], shell=True, check=False)
            if r.returncode != 0:
                logger.error(
                    "Failed to start %s, err: %s, out: %s, code: %s",
                    exe_path,
                    r.stderr,
                    r.stdout,
                    r.returncode,
                )
