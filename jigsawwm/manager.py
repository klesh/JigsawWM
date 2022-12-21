from typing import Set, Dict, List
from jigsawwm.w32.monitor import Monitor, get_monitor_from_window
from jigsawwm.w32.window import Window, get_normal_windows, RECT
from jigsawwm.w32.ivirtualdesktopmanager import GUID
from jigsawwm.tiler.tilers import *
from os import path
import math


class WindowManager:
    _state: Dict[Monitor, List[Window]]
    new_window_as_master: bool
    layout_tilers: List[LayoutTiler]
    ignore_exe_names: Set[str]

    def __init__(
        self,
        new_window_as_master: bool = True,
        layout_tilers: List[LayoutTiler] = None,
        ignore_exe_names: Set[str] = None,
    ):
        self._state = {}
        self.new_window_as_master = new_window_as_master
        self.layout_tilers = layout_tilers or [
            widescreen_dwindle_layout_tiler,
            obs_dwindle_layout_tiler,
            dwindle_layout_tiler,
        ]
        self.current_layout_tiler_index = 0
        self.ignore_exe_names = set(ignore_exe_names or [])

    def sync(self) -> bool:
        state: Dict[Monitor, Set[Window]] = {}
        # get all normal windows
        for window in get_normal_windows():
            # skip certain exe file name
            if path.basename(window.exe) in self.ignore_exe_names:
                continue
            # group them by monitor
            monitor = get_monitor_from_window(window.handle)
            windows = state.get(monitor)
            if not windows:
                windows = set()
                state[monitor] = windows
            windows.add(window)
        # compare and update _state
        for monitor, windows in state.items():
            # found new monitor
            if monitor not in self._state:
                self._state[monitor] = list(windows)
                self.arrange(monitor)
                continue
            # monitor exists, respect the existing windows order
            # first, remove disappeared windows
            old_list = self._state[monitor]
            new_list = []
            for w in old_list:
                if w in windows:
                    new_list.append(w)
                windows.remove(w)
            # and then, prepend or append the new windows
            if self.new_window_as_master:
                new_list = list(windows) + new_list
            else:
                new_list = new_list = list(windows)
            # skip if there is nothing changed
            if new_list == old_list:
                continue
            self._state[monitor] = new_list
            self.arrange(monitor)

    def arrange(self, monitor: Monitor):
        # now, here is the tricky part, thanks to the chaotic Win32 API
        #
        #   1. the `SetWindowPos` api accept RECT in (x,y,w,h) order
        #   2. the `dwmapi` renders window with DropShadow called Extended Frame Bounds
        #      which may or may not make the actual window smaller than we expected
        #   3. even worst, formmer api works in Scaled-Pixel while the latter in
        #      Physical-Pixel
        #   4. the monitor RECt works in Scaled-Pixel mode as well
        #
        # Ideally, we want the all windows sharing the same visible sizing.
        # So, we gonna utilizing the dwmapi to gather the extended frame bounds and
        # convert it into Scaled-Pixel
        scale_factor = monitor.get_scale_factor().value / 100
        wr = monitor.get_info().rcWork
        work_area = (wr.left, wr.top, wr.right, wr.bottom)
        windows = self._state[monitor]
        i = 0
        for rect in self.current_layout_tiler(work_area, len(windows)):
            window = windows[i]
            # calculate the margin to the Extended Frame Bounds
            r = window.get_rect()
            b = window.get_extended_frame_bounds()
            adjusted_rect = (
                round(rect[0] + r.left - (b.left / scale_factor)),
                round(rect[1] + r.top - (b.top / scale_factor)),
                round(rect[2] + r.right - (b.right / scale_factor)),
                round(rect[3] + r.bottom - (b.bottom / scale_factor)),
            )
            print(window.title, rect, adjusted_rect)

            # now, here is the tricky part
            # the
            window.set_rect(RECT(*adjusted_rect))
            i += 1

    @property
    def current_layout_tiler(self) -> LayoutTiler:
        return self.layout_tilers[self.current_layout_tiler_index]


if __name__ == "__main__":
    wm = WindowManager()
    wm.sync()
    print()
    wm.sync()
