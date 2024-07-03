import os
from datetime import timedelta

from log import *
from mailcalaid.cal.holiday import ChinaHolidayBook

from jigsawwm import browser, daemon, smartstart


class DailyRoutine(daemon.Task):
    name = "daily routine"

    def run(self):
        browser.wait_for_network_ready()
        browser.open_fav_folder(os.getenv("JWM_TASK_DAILY_BROWSER",  "chrome"), "daily")

    def condition(self):
        return smartstart.daily_once("daily websites")


class WorkdayRoutine(daemon.Task):
    name = "workday routine"

    def __init__(self) -> None:
        super().__init__()
        self.holiday_book = ChinaHolidayBook()

    def run(self):
        smartstart.start_if_not_running(
            r"C:\Users\Klesh\AppData\Local\Feishu\Feishu.exe"
        )
        smartstart.start_if_not_running(
            r"C:\Program Files\Betterbird\betterbird.exe"
        )
        smartstart.start_if_not_running(
            r"C:\Users\Klesh\AppData\Local\Programs\obsidian\Obsidian.exe"
        )

    def condition(self):
        return self.holiday_book.is_workhour(extend=timedelta(hours=2))


daemon.register(DailyRoutine)
daemon.register(WorkdayRoutine)

if __name__ == "__main__":
    daemon.message_loop()
