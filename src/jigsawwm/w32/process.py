"""Windows API for process management"""
import os
from ctypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from ctypes.wintypes import * # pylint: disable=wildcard-import,unused-wildcard-import
from typing import List
from enum import IntEnum

kernel32 = WinDLL("kernel32", use_last_error=True)
advapi32 = WinDLL("advapi32", use_last_error=True)
psapi = WinDLL("psapi", use_last_error=True)
shcore  = WinDLL("shcore", use_last_error=True)

TOKEN_QUERY = DWORD(8)
PROCESS_QUERY_LIMITED_INFORMATION = DWORD(0x1000)
TOKEN_ELEVATION = INT(20)

def open_process_for_limited_query(pid: int) -> HANDLE:
    """Opens an existing local process object with permission to query limited information

    Ref: https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights

    :param int pid: process id
    :return:  process handle
    :rtype: HANDLE
    """
    hprc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not hprc:
        raise WinError(get_last_error())
    return hprc


def is_elevated(pid: int) -> bool:
    """Check if specified process is elevated (run in Administrator Role)

    :param int pid: process id
    :return: `True` if elevated, `False` otherwise
    :rtype: bool
    """
    hprc = None
    try:
        hprc = open_process_for_limited_query(pid)
    except OSError:
        return True
    htoken = PHANDLE()
    if not windll.advapi32.OpenProcessToken(hprc, TOKEN_QUERY, byref(htoken)):
        windll.kernel32.CloseHandle(hprc)
        return
    result = BOOL()
    returned_length = DWORD()
    if not advapi32.GetTokenInformation(
        htoken,
        TOKEN_ELEVATION,
        byref(result),
        4,
        byref(returned_length),
    ):
        raise WinError(get_last_error())
    kernel32.CloseHandle(hprc)
    kernel32.CloseHandle(htoken)
    return bool(result.value)


def get_exepath(pid: int) -> str:
    """Retrieves the full name of the executable image for the specified process.

    :param int pid: process id
    :return: the full path of the executable
    :rtype: str
    """
    if not pid:
        return
    try:
        hprc = open_process_for_limited_query(pid)
    except OSError:
        return ""
    buff = create_unicode_buffer(512)
    size = DWORD(sizeof(buff))
    if not kernel32.QueryFullProcessImageNameW(hprc, 0, buff, pointer(size)):
        kernel32.CloseHandle(hprc)
        raise WinError(get_last_error())
    kernel32.CloseHandle(hprc)
    return str(buff.value)


def get_all_processes(total: int = 1024) -> List[DWORD]:
    """Retrieves the process identifiers of all running processes.

    :param in total: the number of processes to retrieve

    :return: list of process identifiers
    :rtype: List[DWORD]
    """
    buff = (DWORD * total)()
    size = DWORD(sizeof(buff))
    if not psapi.EnumProcesses(byref(buff), size, pointer(size)):
        raise WinError(get_last_error())
    return list(buff[: size.value // sizeof(DWORD)])


def is_exe_running(exe: str, nameonly: bool = False) -> bool:
    """Check if specified executable is running

    :param str exe: executable name
    :param bool nameonly: if `True`, only check the executable name, otherwise check the full path
    :return: `True` if running, `False` otherwise
    :rtype: bool
    """
    exe = exe.lower()
    if nameonly:
        exe = os.path.basename(exe)
    for pid in get_all_processes():
        try:
            ppath = get_exepath(pid).lower()
            if nameonly:
                ppath = os.path.basename(ppath)
            if exe == ppath:
                return True
        except: # pylint: disable=bare-except
            pass
    return False


def get_session_id():
    """Get the current session id

    :return: session id
    :rtype: int
    """
    session_id = DWORD()
    kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), byref(session_id))
    return kernel32.WTSGetActiveConsoleSessionId()

class ProcessDpiAwareness(IntEnum):
    """Process DPI Awareness Level"""
    UNKNOWN = 0
    PROCESS_DPI_UNAWARE = 0
    PROCESS_SYSTEM_DPI_AWARE = 1
    PROCESS_PER_MONITOR_DPI_AWARE = 2

def get_process_dpi_awareness(pid: int) -> ProcessDpiAwareness:
    """Retrieves the DPI awareness of the process"""
    try:
        hprc = open_process_for_limited_query(pid)
        awareness = c_int()
        if shcore.GetProcessDpiAwareness(hprc, pointer(awareness)):
            raise WinError(get_last_error())
        return ProcessDpiAwareness(awareness.value)
    except: # pylint: disable=bare-except
        return ProcessDpiAwareness.UNKNOWN

if __name__ == "__main__":
    # import sys

    # print(is_exe_running(sys.argv[1], bool(sys.argv[2])))
    print(get_session_id())
