import subprocess
import time
from ctypes import *
from ctypes.wintypes import *
from tkinter import *
from tkinter import ttk
from typing import Optional

SCREEN_NAME = "virtual desktop stub"

all_process = []

user32 = WinDLL("user32", use_last_error=True)


def find_virtdeskstub() -> Optional[HWND]:
    hwnds = []

    buff = create_unicode_buffer(100)

    @WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_windows_proc(hwnd: HWND, lParam: LPARAM) -> BOOL:
        user32.GetWindowTextW(hwnd, buff, 100)
        if str(buff.value) == SCREEN_NAME:
            hwnds.append(hwnd)
            return False
        return True

    user32.EnumDesktopWindows(None, enum_windows_proc, 0)
    if hwnds:
        return hwnds[0]


def find_or_create_virtdeskstub() -> HWND:
    hwnd = find_virtdeskstub()
    if hwnd:
        return hwnd
    global all_process
    proc = subprocess.Popen([r"py", __file__, "spawn"])
    all_process.append(proc)
    for _ in range(5):
        time.sleep(0.1)
        hwnd = find_virtdeskstub()
        if hwnd:
            break
    return hwnd, proc


def new_virtdeskstub():
    root = Tk(className=SCREEN_NAME)
    root.geometry("120x50+5+1390")
    root.resizable(width=False, height=False)
    frm = ttk.Frame(root, padding=5)
    frm.grid()
    # ttk.Label(
    #     frm,
    #     text="JigsawWM",
    # ).grid(column=0, row=0)
    ttk.Button(frm, text="Quit", command=root.destroy).grid(column=0, row=1)
    # root.overrideredirect(True)
    root.call("wm", "attributes", ".", "-topmost", "1")
    # root.withdraw()
    mainloop()


def kill_all():
    global all_process
    for p in all_process:
        p.kill()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "spawn":
        # print(r"py .\jigsawwm\virtdeskstub.py spawn")
        new_virtdeskstub()
    else:
        # print("py -m jigsawwm.virtdeskstub")
        from jigsawwm.w32.ivirtualdesktopmanager import virtual_desktop_manager
        from jigsawwm.w32.window import Window, inspect_window

        hwnd = find_or_create_virtdeskstub()
        print("hwnd", hwnd)
        if hwnd:
            inspect_window(Window(hwnd))
            try:
                virtual_desktop_manager.GetWindowDesktopId(hwnd)
            except:
                print()
                print("FAILED")
                print("FAILED")
                print("FAILED")
                print("FAILED")

        kill_all()
