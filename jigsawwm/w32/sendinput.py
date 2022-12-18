from ctypes import *
from ctypes.wintypes import *
from typing import List

user32 = WinDLL('user32', use_last_error=True)

ULONG_PTR = LPARAM

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004

class KEYBDINPUT(Structure):
  _fields_ = (
    ('wVk', WORD),
    ('wScan', WORD),
    ('dwFlags', DWORD),
    ('time', DWORD),
    ('dwExtraInfo', ULONG_PTR),
  )

class MOUSEINPUT(Structure):
  _fields_ = (
    ('dx', LONG),
    ('dy', LONG),
    ('mouseData', DWORD),
    ('dwFlags', DWORD),
    ('time', DWORD),
    ('dwExtraInfo', ULONG_PTR),
  )

class HARDWAREINPUT(Structure):
  _fields_ = (
    ('uMsg', LONG),
    ('wParamL', WORD),
    ('wParamH', WORD),
  )

class INPUTDATA(Union):
  _fields_ = (
    ('mi', MOUSEINPUT),
    ('ki', KEYBDINPUT),
    ('hi', HARDWAREINPUT),
  )

class INPUT(Structure):
  _anonymous_ = ['u']
  _fields_ = (
    ('type', DWORD),
    ('u', INPUTDATA),
  )

def send_input(*inputs: List[INPUT]):
  length = len(inputs)
  array = INPUT * length
  if not user32.SendInput(length, array(*inputs), sizeof(INPUT)):
    raise WinError(get_last_error())


if __name__ == "__main__":
  send_input(
    INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0x41, dwExtraInfo=123)),
    INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0x41, dwFlags=KEYEVENTF_KEYUP)),
  )

