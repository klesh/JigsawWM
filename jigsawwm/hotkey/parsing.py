from jigsawwm.w32.vk import Vk
from typing import Sequence


def combination_to_combkeys(combination: str) -> Sequence[Vk]:
    """Converts combination string to virtual keys sequence

    Ref: http://www.kbdedit.com/manual/low_level_vk_list.html
    """
    keylist = []
    for kn in combination.split("+"):
        # normalize key name
        key_name = kn.strip().upper()
        if key_name == "LCTRL":
            key_name = "LCONTROL"
        elif key_name == "LALT":
            key_name = "LMENU"
        elif key_name == "RCTRL":
            key_name = "RCONTROL"
        elif key_name == "RALT":
            key_name = "RMENU"
        elif key_name == "CTRL":
            key_name = "CONTROL"
        elif key_name == "MENU":
            key_name = "MENU"
        elif key_name == "-":
            key_name = "OEM_MINUS"
        elif key_name == "=":
            key_name = "OEM_PLUS"
        elif key_name == ";":
            key_name = "OEM_1"
        elif key_name == "/":
            key_name = "OEM_2"
        elif key_name == "`":
            key_name = "OEM_3"
        elif key_name == "[":
            key_name = "OEM_4"
        elif key_name == "\\":
            key_name = "OEM_5"
        elif key_name == "]":
            key_name = "OEM_6"
        elif key_name == "'":
            key_name = "OEM_7"
        elif key_name == ",":
            key_name = "OEM_COMMA"
        elif key_name == ".":
            key_name = "OEM_PERIOD"
        elif len(key_name) == 1:
            # alphabet and numbers
            key_name = f"KEY_{key_name}"
        key_name = f"VK_{key_name}"
        if key_name not in Vk.__members__:
            raise Exception(f"invalid key name {kn}")
        keylist.append(Vk[key_name])
    return keylist
