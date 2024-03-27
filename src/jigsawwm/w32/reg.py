import winreg


def read_reg_key(key, subkey, value):
    """
    Reads a value from the registry
    """
    try:
        with winreg.OpenKey(key, subkey) as handle:
            return winreg.QueryValueEx(handle, value)[0].hex()
    except FileNotFoundError:
        return None


def get_current_desktop_id():
    """
    Returns the GUID of the current virtual desktop
    """
    return read_reg_key(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\VirtualDesktops",
        "CurrentVirtualDesktop",
    )


if __name__ == "__main__":
    print(get_current_desktop_id())
