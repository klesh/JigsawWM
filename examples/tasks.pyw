from datetime import timedelta

from log import *
from mailcalaid.cal.holiday import ChinaHolidayBook

from jigsawwm import chrome, daemon, smartstart


class DailyRoutine(daemon.Task):
    name = "daily routine"

    def run(self):
        chrome.open_fav_folder("bookmark_bar", "daily")
        # chrome.open_edge_fav_folder("bookmark_bar", "daily")

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
            r"C:\Program Files\Mozilla Thunderbird\thunderbird.exe"
        )
        smartstart.start_if_not_running(
            r"C:\Users\Klesh\AppData\Local\Obsidian\Obsidian.exe"
        )

    def condition(self):
        return self.holiday_book.is_workhour(extend=timedelta(hours=2))


daemon.register(DailyRoutine)
daemon.register(WorkdayRoutine)

if __name__ == "__main__":
    daemon.message_loop()
