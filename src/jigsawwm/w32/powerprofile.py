from ctypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import *  # pylint: disable=wildcard-import,unused-wildcard-import

powrprof = WinDLL("powrprof", use_last_error=True)
kernel32 = WinDLL("kernel32", use_last_error=True)

def set_suspsend_state() -> None:
    """Suspends the system."""
    if not powrprof.SetSuspendState(False, False, False):
        raise WinError(get_last_error())


def set_system_power_state() -> None:
    """Suspends the system."""
    if not kernel32.SetSystemPowerState(True, False):
        raise WinError(get_last_error())


suspend_system = set_system_power_state