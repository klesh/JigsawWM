import time
import json
import os


def open_fav_folder_with(
    bookmarks_path: str,
    root_folder: str,
    fav_folder: str,
    start_proto: str = None,
):
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


def open_firefox_fav_folder(places_path, fav_folder='daily'):
    import sqlite3
    sql_query = f"""
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
    for url, in res.fetchall():
        time.sleep(1) # open too fast will cause firefox to skip some tabs
        os.startfile(url)


def open_chrome_fav_folder(root_folder, fav_folder, bookmarks_path=None):
    """Opens the Chrome Favorites folder"""
    bookmarks_path = bookmarks_path or os.path.join(
        os.getenv("LOCALAPPDATA"),
        "Google",
        "Chrome",
        "User Data",
        "Default",
        "Bookmarks",
    )
    return open_fav_folder_with(bookmarks_path, root_folder, fav_folder)


def open_edge_fav_folder(root_folder, fav_folder):
    """Opens the Chrome Favorites folder"""
    bookmarks_path = os.path.join(
        os.getenv("LOCALAPPDATA"),
        "Microsoft",
        "Edge",
        "User Data",
        "Default",
        "Bookmarks",
    )
    return open_fav_folder_with(
        bookmarks_path, root_folder, fav_folder, "microsoft-edge"
    )

def wait_for_network_ready():
    import urllib.request
    import time

    while True:
        try:
            res = urllib.request.urlopen("https://baidu.com")
            if res:
                break
        except Exception as e:
            time.sleep(1)

if __name__ == "__main__":
    open_firefox_fav_folder(r"C:\Users\Klesh\AppData\Roaming\Floorp\Profiles\qv6occsk.default-release\places.sqlite")