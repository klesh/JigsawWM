from datetime import timedelta

from log import *
from mailcalaid.cal.holiday import ChinaHolidayBook

from jigsawwm import browser, daemon, smartstart


class DailyRoutine(daemon.Task):
    name = "daily routine"

    def run(self):
        browser.wait_for_network_ready()
        # browser.open_chrome_fav_folder("bookmark_bar", "daily")
        browser.open_chrome_fav_folder("bookmark_bar", "daily", bookmarks_path=os.path.join(
            os.getenv("LOCALAPPDATA"),
            "Thorium",
            "User Data",
            "Default",
            "Bookmarks",
        ))
        # browser.open_edge_fav_folder("bookmark_bar", "daily")
        # Firefox profile path: Menu -> Help -> More Troubleshooting Information -> Application Basics -> Profile Folder
        # browser.open_firefox_fav_folder(r"C:\Users\Klesh\AppData\Roaming\Mozilla\Firefox\Profiles\jmhvf542.default-release\places.sqlite")
        # browser.open_firefox_fav_folder(r"C:\Users\Klesh\AppData\Roaming\Floorp\Profiles\qv6occsk.default-release\places.sqlite")

    def condition(self):
        return smartstart.daily_once("daily websites")

    @property
    def nonblocking(self):
        return True


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
            r"C:\Users\Klesh\AppData\Local\Programs\obsidian\Obsidian.exe"
        )

    def condition(self):
        return self.holiday_book.is_workhour(extend=timedelta(hours=2))


daemon.register(DailyRoutine)
daemon.register(WorkdayRoutine)

if __name__ == "__main__":
    daemon.message_loop()
