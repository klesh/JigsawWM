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


def open_fav_folder(root_folder, fav_folder):
    """Opens the Chrome Favorites folder"""
    bookmarks_path = os.path.join(
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
