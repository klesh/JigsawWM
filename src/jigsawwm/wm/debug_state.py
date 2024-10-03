import pickle
import logging
import os

logger = logging.getLogger(__name__)


def inspect_virtdesk_states(virtdesk_states):
    """Inspect the state of the virtual desktops"""
    for vdid, vdstate in virtdesk_states.items():
        logger.info("virt_desk: %s", vdid)
        for monitor, ms in vdstate.monitor_states.items():
            logger.info("  %s hmon=%s", ms, monitor.handle)
            for ws in ms.workspaces:
                logger.info(
                    "      %s workspace: %s", ws.name, "*" if ws.showing else " "
                )
                for i, win in enumerate(ws.tiling_windows):
                    logger.info(
                        "      %s %d %s",
                        "*" if ws.last_active_window == win else " ",
                        i,
                        win,
                    )
                for win in ws.floating_windows:
                    logger.info(
                        "        %s%s",
                        "*" if ws.last_active_window == win else " ",
                        win,
                    )


if __name__ == "__main__":
    DEFAULT_STATE_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "jigsawwm", "wm.state")
    logging.basicConfig(level=logging.DEBUG)
    with open(DEFAULT_STATE_PATH, "rb") as f:
        try:
            virtdesk_states, seen_windows, managed_windows = pickle.load(f)
            inspect_virtdesk_states(virtdesk_states)
        except:  # pylint: disable=bare-except
            logger.exception("load windows states error", exc_info=True)
