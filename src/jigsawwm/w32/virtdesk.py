from pyvda import AppView, VirtualDesktop
from .window import Window
from typing import  Optional

# number_of_active_desktops = len(get_virtual_desktops())
# print(f"There are {number_of_active_desktops} active desktops")

# current_desktop = VirtualDesktop.current()
# print(f"Current desktop is number {current_desktop}")

# current_window = AppView.current()
# target_desktop = VirtualDesktop(4)
# current_window.move(target_desktop)
# print(f"Moved window {current_window.hwnd} to {target_desktop.number}")

# print("Going to desktop number 5")
# target_desktop.go()

# print("Pinning the current window")
# AppView.current().pin()


def switch_desktop(desktop_number):
    target_desktop = VirtualDesktop(desktop_number)
    target_desktop.go()

def switch_desktop_delta(delta: int):
    switch_desktop(desktop_delta_to_number(delta))

def move_to_desktop(desktop_number, window: Optional[Window]  = None):
    appview = AppView(window.handle) if window else AppView.current()
    target_desktop = VirtualDesktop(desktop_number)
    appview.move(target_desktop)

def move_to_desktop_delta(delta: int, window: Optional[Window]  = None):
    move_to_desktop(desktop_delta_to_number(delta), window)

def desktop_delta_to_number(delta: int):
    current_desktop = VirtualDesktop.current()
    return current_desktop.number + delta