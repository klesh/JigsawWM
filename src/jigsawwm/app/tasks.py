"""Useful tasks"""

from datetime import timedelta
from typing import List

from mailcalaid.cal.holiday import ChinaHolidayBook, NagerDateHolidayBook

from .browser import open_fav_folder, wait_for_network_ready
from .job import Task
from .smartstart import is_today_done, mark_today_done, start_if_not_running


class DailyWebsites(Task):
    """Open all bookmarks in given fav folder once per day"""

    name = "daily websites"
    browser_name: str
    fav_folder: str
    test_url: str
    proxy_url: str

    def __init__(
        self,
        browser_name: str,
        fav_folder: str,
        test_url: str = "https://bing.com",
        proxy_url: str = None,
    ):
        self.browser_name = browser_name
        self.fav_folder = fav_folder
        self.test_url = test_url
        self.proxy_url = proxy_url

    def run(self):
        open_fav_folder(self.browser_name, self.fav_folder)
        mark_today_done(self.name)

    def condition(self):
        wait_for_network_ready(self.test_url, self.proxy_url)
        return is_today_done(self.name)


class WorkdayAutoStart(Task):
    """Launch apps if current time is in workhours"""

    name = "workday routine"

    def __init__(self, country_code: str, utc_offset: int = 0, apps: List[str] = None):
        super().__init__()
        if country_code == "CN":
            self.holiday_book = ChinaHolidayBook()
        else:
            self.holiday_book = NagerDateHolidayBook(
                utc_offset=utc_offset, country_code=country_code
            )
        self.apps = apps

    def run(self):
        for app in self.apps:
            start_if_not_running(app)

    def condition(self):
        return self.holiday_book.is_workhour(extend=timedelta(hours=2))
