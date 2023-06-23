import json
import os


def open_fav_folder(root, fav_folder):
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
