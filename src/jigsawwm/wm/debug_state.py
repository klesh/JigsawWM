import pickle
import logging
import os

logger = logging.getLogger(__name__)

def inspect_virtdesk_states(virtdesk_states):
    """Inspect the state of the virtual desktops"""
    for vdid, vdstate in virtdesk_states.items():
        logger.info("virt_desk: %s", vdid)
        for monitor, monitor_state in vdstate.monitor_states.items():
            logger.info("  monitor: %s", monitor.name)
            for ws in monitor_state.workspaces:
                logger.info("    workspace: %s %s", ws.name, "showing" if ws.showing else "")
                for i, win in enumerate(ws.tilable_windows):
                    logger.info("      %s %d %s", '*' if ws.last_active_window == win else ' ',i, win)
                for win in ws.windows:
                    if win in ws.tilable_windows:
                        continue
                    logger.info("      %s%s", '*' if ws.last_active_window == win else ' ', win)

if __name__ == "__main__":
    DEFAULT_STATE_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "jigsawwm", "wm.state")
    logging.basicConfig(level=logging.DEBUG)
    with open(DEFAULT_STATE_PATH, "rb") as f:
        try:
            virtdesk_states = pickle.load(f)
            inspect_virtdesk_states(virtdesk_states)
        except: # pylint: disable=bare-except
            logger.exception("load windows states error", exc_info=True)