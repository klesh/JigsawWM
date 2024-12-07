from ctypes import *  # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import *  # pylint: disable=wildcard-import,unused-wildcard-import

powrprof = WinDLL("powrprof", use_last_error=True)


def suspend_system() -> None:
    """Suspends the system."""
    if not powrprof.SetSuspendState(False, False, False):
        raise WinError(get_last_error())
