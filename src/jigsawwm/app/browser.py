"""Useful functions to access browsers data"""

import time
import sqlite3
import json
import os
import os.path
import logging
import urllib.request
from typing import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def open_chrome_fav_folder(
    bookmarks_path: str,
    fav_folder: str = "daily",
    root_folder: str = "bookmark_bar",
    start_proto: str = None,
):
    """Open chrome fav folder"""
    bookmarks = None
    with open(bookmarks_path, encoding="utf8") as f:
        bookmarks = json.load(f)

    # open folder recursively
    def open_folder(folder):
        for child in folder["children"]:
            if child.get("type") == "url":
                url = child["url"]
                if start_proto:
                    url = f"{start_proto}:{url}"
                os.startfile(url)
            else:
                open_folder(child)

    # locate the initial folder
    folder = bookmarks["roots"][root_folder]
    for component in fav_folder.split("."):
        for child in folder["children"]:
            if child["name"] == component and child["type"] == "folder":
                folder = child
                break
    open_folder(folder)


def open_firefox_fav_folder(places_path, fav_folder="daily"):
    """Open firefox fav folder"""
    # Firefox profile path: Menu -> Help -> More Troubleshooting Information -> Application Basics -> Profile Folder
    # browser.open_firefox_fav_folder(r"C:\Users\Klesh\AppData\Roaming\Mozilla\Firefox\Profiles\jmhvf542.default-release\places.sqlite")
    # browser.open_firefox_fav_folder(r"C:\Users\Klesh\AppData\Roaming\Floorp\Profiles\qv6occsk.default-release\places.sqlite")

    sql_query = """
        select
            -- mb.title,
            mp.url
        from
            moz_bookmarks mb
        left join moz_places mp on
            (mb.fk = mp.id)
        where
            mb.parent =(
            select
                id
            from
                moz_bookmarks
            where
                title = ?
                and type = 2)   
    """
    con = sqlite3.connect(places_path)
    cur = con.cursor()
    res = cur.execute(sql_query, [fav_folder])
    for (url,) in res.fetchall():
        time.sleep(1)  # open too fast will cause firefox to skip some tabs
        os.startfile(url)
    res.close()
    cur.close()


@dataclass
class BrowserProfile:
    """Browser profile"""

    name: str
    path: str
    entry: Callable[[str, str], None]


BROWSER_BOOKMARK_PATHS = {
    "chrome": BrowserProfile(
        name="chrome",
        path=os.path.join(
            os.getenv("LOCALAPPDATA"),
            "Google",
            "Chrome",
            "User Data",
            "Default",
            "Bookmarks",
        ),
        entry=open_chrome_fav_folder,
    ),
    "thorium": BrowserProfile(
        name="thorium",
        path=os.path.join(
            os.getenv("LOCALAPPDATA"),
            "Thorium",
            "User Data",
            "Default",
            "Bookmarks",
        ),
        entry=open_chrome_fav_folder,
    ),
    "edge": BrowserProfile(
        name="edge",
        path=os.path.join(
            os.getenv("LOCALAPPDATA"),
            "Microsoft",
            "Edge",
            "User Data",
            "Default",
            "Bookmarks",
        ),
        entry=open_chrome_fav_folder,
    ),
    "firefox": BrowserProfile(  # to be done
        name="firefox",
        path=os.path.join(
            os.getenv("APPDATA"),
            "Mozilla",
            "Firefox",
            "Profiles",
            "?",
            "places.sqlite",
        ),
        entry=open_firefox_fav_folder,
    ),
    "floorp": BrowserProfile(  # to be done
        name="floorp",
        path=os.path.join(
            os.getenv("APPDATA"),
            "Floorp",
            "Profiles",
            "?",
            "places.sqlite",
        ),
        entry=open_firefox_fav_folder,
    ),
}


def open_fav_folder(browser_name, fav_folder):
    """Open browser's fav folder"""
    profile = BROWSER_BOOKMARK_PATHS.get(browser_name)
    if not profile:
        logger.error("Unsupported browser %s", browser_name)
    profile.entry(profile.path, fav_folder)


def wait_for_network_ready(test_url: str, proxy_url: str = None):
    """sleep untill the network is ready"""
    if proxy_url:
        proxy_support = urllib.request.ProxyHandler(
            {"http": proxy_url, "https": proxy_url}
        )
        opener = urllib.request.build_opener(proxy_support)
        urllib.request.install_opener(opener)

    while True:
        try:
            res = urllib.request.urlopen(test_url, timeout=3)
            if res:
                break
        except:  # pylint: disable=bare-except
            logger.debug("test network by accessing %s", test_url)
            time.sleep(1)


if __name__ == "__main__":
    wait_for_network_ready("https://bing.com")
    # open_firefox_fav_folder(
    #     r"C:\Users\Klesh\AppData\Roaming\Floorp\Profiles\qv6occsk.default-release\places.sqlite"
    # )
