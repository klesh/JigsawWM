from ctypes import *
from ctypes.wintypes import *

kernel32 = WinDLL("kernel32", use_last_error=True)
advapi32 = WinDLL("advapi32", use_last_error=True)

TOKEN_QUERY = DWORD(8)


def open_process_for_limited_query(pid: int) -> HANDLE:
    """Opens an existing local process object with permission to query limited information

    Ref: https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights

    :param pid: int
    :return:  process handle
    :rtype: HANDLE
    """
    PROCESS_QUERY_LIMITED_INFORMATION = DWORD(0x1000)
    hprc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not hprc:
        raise WinError(get_last_error())
    return hprc


def is_elevated(pid: int) -> bool:
    """Check if specified process is elevated (run in Administrator Role)

    :param pid: int
    :return: `True` if elevated, `False` otherwise
    :rtype: bool
    """
    hprc = open_process_for_limited_query(pid)
    htoken = PHANDLE()
    if not windll.advapi32.OpenProcessToken(hprc, TOKEN_QUERY, byref(htoken)):
        windll.kernel32.CloseHandle(hprc)
        return
    TOKEN_ELEVATION = INT(20)
    is_elevated = BOOL()
    returned_length = DWORD()
    if not advapi32.GetTokenInformation(
        htoken,
        TOKEN_ELEVATION,
        byref(is_elevated),
        4,
        byref(returned_length),
    ):
        raise WinError(get_last_error())
    kernel32.CloseHandle(hprc)
    kernel32.CloseHandle(htoken)
    return bool(is_elevated.value)


def get_exepath(pid: int) -> str:
    """Retrieves the full name of the executable image for the specified process.

    :param pid: int
    :return: the full path of the executable
    :rtype: str
    """
    if not pid:
        return
    hprc = open_process_for_limited_query(pid)
    buff = create_unicode_buffer(512)
    size = DWORD(sizeof(buff))
    if not kernel32.QueryFullProcessImageNameW(hprc, 0, buff, pointer(size)):
        kernel32.CloseHandle(hprc)
        raise WinError(get_last_error())
    kernel32.CloseHandle(hprc)
    return str(buff.value)
