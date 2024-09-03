from jmk import hks
from log import *
from functools import partial

from jigsawwm import daemon
from jigsawwm.tiler import tilers
from jigsawwm.w32.vk import Vk
from jigsawwm.wm.manager import Theme, WindowManager, WmRule


wm = WindowManager(
    themes=[
        # Theme(
        #     name="OBS Dwindle",
        #     layout_tiler=tilers.obs_dwindle_layout_tiler,
        #     icon_name="obs.png",
        #     gap=2,
        #     strict=True,
        # ),
        Theme(
            name="Dwindle",
            layout_tiler=tilers.ratio_dwindle_layout_tiler,
            max_tiling_areas=3,
            strict=True,
            gap=4,
            new_window_as_master=True,
            affinity_index=lambda si: (4 if si.inch >= 20 else 0)
            + (5 if 1 < si.ratio < 2 else 0),
        ),
        Theme(
            name="Mono",
            layout_tiler=tilers.mono_layout_tiler,
            strict=True,
            affinity_index=lambda si: (
                10
                if si.inch < 20 or (si.width_px == 2048 and si.height_px == 1536)
                else 0
            ),
        ),
        Theme(
            name="WideScreen Dwindle",
            layout_tiler=tilers.widescreen_dwindle_layout_tiler,
            max_tiling_areas=4,
            icon_name="wide-dwindle.png",
            gap=2,
            strict=True,
            new_window_as_master=True,
            affinity_index=lambda si: (4 if si.inch >= 20 else 0)
            + (5 if si.ratio < 1 or si.ratio >= 2 else 0),
        ),
    ],
    rules=[
        WmRule(exe_regex=r"\bWindowsTerminal\.exe$", manageable=False),
        WmRule(exe_regex=r"\bSnippingTool\.exe$", manageable=False),
        WmRule(exe_regex=r"\bFlow\.Launcher\.exe", manageable=False),
        WmRule(exe_regex=r"\bmsedgewebview2.exe\.exe", manageable=False),
        WmRule(exe_regex=r"\bWeChat\.exe$", tilable=False),
        WmRule(exe_regex=r"\bMediaInfo\.exe$", tilable=False),
        WmRule(exe_regex=r"\bCloudflare WARP\.exe$", tilable=False),
        WmRule(exe_regex=r"\b7zFM\.exe$", tilable=False),
        WmRule(exe_regex=r"\bfdm\.exe$", tilable=False),
        WmRule(exe_regex=r"\bfoobar2000\.exe$", tilable=False),
        WmRule(exe_regex=r"\bApplicationFrameHost\.exe$", tilable=False),
        WmRule(exe_regex=r"\bnotepad\+\+\.exe", tilable=False),
        WmRule(exe_regex=r"\bPotPlayerMini64\.exe", tilable=False),
        # WmRule(exe_regex=r"\bmintty\.exe", tilable=False),
        WmRule(exe_regex=r"\bopenvpn-gui\.exe", tilable=False),
        WmRule(
            exe_regex=r"\bObsidian\.exe$", title_regex=None, preferred_monitor_index=1
        ),
        WmRule(exe_regex=r"\bFeishu\.exe$", preferred_monitor_index=1),
    ],
)

hotkeys = [
    ([Vk.WIN, Vk.J], wm.next_window),
    ([Vk.WIN, Vk.K], wm.prev_window),
    ([Vk.WIN, Vk.SHIFT, Vk.J], wm.swap_next),
    ([Vk.WIN, Vk.SHIFT, Vk.K], wm.swap_prev),
    ("Win+/", wm.set_master),
    ([Vk.WIN, Vk.CONTROL, Vk.SPACE], wm.next_theme),
    ([Vk.WIN, Vk.U], wm.prev_monitor),
    ([Vk.WIN, Vk.I], wm.next_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.U], wm.move_to_prev_monitor),
    ([Vk.WIN, Vk.SHIFT, Vk.I], wm.move_to_next_monitor),
    ([Vk.WIN, Vk.CONTROL, Vk.I], wm.inspect_active_window),
    ("Win+Ctrl+a", partial(wm.switch_workspace, 0)),
    ("Win+Ctrl+s", partial(wm.switch_workspace, 1)),
    ("Win+Ctrl+d", partial(wm.switch_workspace, 2)),
    ("Win+Ctrl+f", partial(wm.switch_workspace, 3)),
    ("Win+Shift+a", partial(wm.move_to_workspace, 0)),
    ("Win+Shift+s", partial(wm.move_to_workspace, 1)),
    ("Win+Shift+d", partial(wm.move_to_workspace, 2)),
    ("Win+Shift+f", partial(wm.move_to_workspace, 3)),
    ("Win+Shift+Space", wm.toggle_tilable),
    ("Win+Ctrl+u", wm.inspect_state),
]


class WindowManagerService(daemon.Service):  # , daemon.ServiceMenu
    """Window Manager Service"""

    name = "Window Manager"
    is_running = False

    def start(self):
        self.is_running = True
        wm.start()
        for args in hotkeys:
            hks.register(*args)

    def stop(self):
        wm.stop()
        for args in hotkeys:
            hks.unregister(args[0])
        self.is_running = False

    # def service_menu_items(self) -> Iterator[Union[daemon.QMenu, daemon.QAction]]:
    #     for monitor, monitor_state in wm.virtdesk_state.monitor_states.items():
    #         monitor_menu = daemon.QMenu()
    #         monitor_menu.setTitle(f"Monitor {monitor.name}")
    #         monitor_menu.menuitems = [] # prevent submenu from being garbage collected
    #         for workspace_index, workspace in enumerate( monitor_state.workspaces):
    #             workspace_act = daemon.QAction()
    #             workspace_act.setText(f"Workspace {workspace.name}")
    #             workspace_act.triggered.connect(partial(wm.switch_workspace, workspace_index, monitor_name=monitor.name, hide_splash_in=2))
    #             workspace_act.setCheckable(True)
    #             workspace_act.setChecked(workspace_index == monitor_state.active_workspace_index)
    #             monitor_menu.addAction(workspace_act)
    #             monitor_menu.menuitems.append(workspace_act)
    #         yield monitor_menu


daemon.register(WindowManagerService)

if __name__ == "__main__":
    daemon.message_loop()
