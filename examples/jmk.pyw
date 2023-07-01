from datetime import datetime

from log import *

from jigsawwm import daemon
from jigsawwm.jmk import *
from jigsawwm.w32.sendinput import send_combination, send_text
from jigsawwm.w32.vk import Vk, parse_key
from jigsawwm.w32.window import minimize_active_window, toggle_maximize_active_window

#######################
#  configuration
#######################

send_today = lambda: send_text(datetime.now().strftime("%Y-%m-%d"))
send_now = lambda: send_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
ctrl_w = lambda: send_combination(Vk.LCONTROL, Vk.W)
ctrl_shift_t = lambda: send_combination(Vk.LCONTROL, Vk.LSHIFT, Vk.T)
ctrl_pgup = lambda: send_combination(Vk.LCONTROL, Vk.PRIOR)
ctrl_pgdn = lambda: send_combination(Vk.LCONTROL, Vk.NEXT)


layers = [
    {  # layer 0
        # map capslock to ctrl when held and `  when tapped
        Vk.CAPITAL: JmkTapHold(tap=parse_key("`"), hold=Vk.LCONTROL),
        # Vk.ESCAPE: JmkTapHold(tap=Vk.ESCAPE, hold=Vk.LWIN),
        Vk.T: JmkTapHold(tap=Vk.T, hold=3),
        Vk.Y: JmkTapHold(tap=Vk.Y, hold=3),
        Vk.A: JmkTapHold(tap=Vk.A, hold=Vk.LMENU),
        Vk.S: JmkTapHold(tap=Vk.S, hold=Vk.LSHIFT),
        Vk.D: JmkTapHold(tap=Vk.D, hold=Vk.LWIN),
        Vk.F: JmkTapHold(tap=Vk.F, hold=Vk.LCONTROL),
        Vk.G: JmkTapHold(tap=Vk.G, hold=1),
        Vk.H: JmkTapHold(tap=Vk.H, hold=1),
        Vk.J: JmkTapHold(tap=Vk.J, hold=Vk.RCONTROL),
        Vk.K: JmkTapHold(tap=Vk.K, hold=Vk.RWIN),
        Vk.L: JmkTapHold(tap=Vk.L, hold=Vk.RSHIFT),
        # hold ; as Alt
        Vk.OEM_1: JmkTapHold(tap=Vk.OEM_1, hold=Vk.RMENU),
        # Vk.TAB: JmkTapHold(tap=Vk.TAB, hold=2),
        # hold ' to switch to layer 2
        Vk.N: JmkTapHold(tap=Vk.N, hold=2),
        Vk.B: JmkTapHold(tap=Vk.B, hold=2),
        # hold Forward Button on the Mouse for swithcing to layer 1
        Vk.XBUTTON2: JmkTapHold(tap=Vk.XBUTTON2, hold=2),
        Vk.SPACE: JmkTapHold(tap=Vk.SPACE, hold=Vk.LSHIFT),
    },
    {  # layer 1
        # left hand
        Vk.A: JmkKey(Vk.HOME),
        Vk.E: JmkKey(Vk.END),
        # right hand
        Vk.H: JmkKey(Vk.LEFT),
        Vk.J: JmkKey(Vk.DOWN),
        Vk.K: JmkKey(Vk.UP),
        Vk.L: JmkKey(Vk.RIGHT),
        Vk.U: JmkKey(ctrl_pgup),
        Vk.I: JmkKey(ctrl_pgdn),
        Vk.N: JmkKey(Vk.MEDIA_NEXT_TRACK),
        Vk.P: JmkKey(Vk.MEDIA_PREV_TRACK),
        Vk.OEM_COMMA: JmkKey(Vk.VOLUME_DOWN),
        Vk.OEM_PERIOD: JmkKey(Vk.VOLUME_UP),
        parse_key("/"): JmkKey(Vk.MEDIA_PLAY_PAUSE),
    },
    {  # layer 2
        # tap to send today's date, hold to send now
        Vk.T: JmkTapHold(on_tap=send_today, on_hold_down=send_now),
        # tap to close tab, hold to reopen for Chrome
        Vk.LBUTTON: JmkTapHold(on_tap=ctrl_w, on_hold_down=ctrl_shift_t, term=0.5),
        # forward button + whell up  = ctrl + page up (previous tab)
        Vk.WHEEL_UP: JmkKey(ctrl_pgup),
        # forward button + wheel down  = ctrl + page down (next tab)
        Vk.WHEEL_DOWN: JmkKey(ctrl_pgdn),
        # exit
        Vk.ESCAPE: JmkKey(daemon.stop),
        # symbol
        Vk.A: JmkKey(lambda: send_text("@")),
        Vk.E: JmkKey(lambda: send_text("!")),
        Vk.S: JmkKey(lambda: send_text("#")),
        Vk.D: JmkKey(lambda: send_text("$")),
        Vk.X: JmkKey(lambda: send_text("%")),
        Vk.Y: JmkKey(lambda: send_text("^")),
        Vk.N: JmkKey(lambda: send_text("&")),
        Vk.R: JmkKey(lambda: send_text("*")),
        Vk.F: JmkKey(lambda: send_text("(")),
        Vk.G: JmkKey(lambda: send_text(")")),
        Vk.M: JmkKey(lambda: send_text("-")),
        Vk.P: JmkKey(lambda: send_text("+")),
        Vk.U: JmkKey(lambda: send_text("_")),
        Vk.Q: JmkKey(lambda: send_text("=")),
    },
    {  # layer 3
        # left hand
        Vk.Z: JmkKey(Vk.F1),
        Vk.X: JmkKey(Vk.F2),
        Vk.C: JmkKey(Vk.F3),
        Vk.V: JmkKey(Vk.F4),
        Vk.A: JmkKey(Vk.F5),
        Vk.S: JmkKey(Vk.F6),
        Vk.D: JmkKey(Vk.F7),
        Vk.F: JmkKey(Vk.F8),
        Vk.Q: JmkKey(Vk.F9),
        Vk.W: JmkKey(Vk.F10),
        Vk.E: JmkKey(Vk.F11),
        Vk.R: JmkKey(Vk.F12),
        # right hand
        Vk.SPACE: JmkKey(Vk.KEY_0),
        Vk.M: JmkKey(Vk.KEY_1),
        Vk.OEM_COMMA: JmkKey(Vk.KEY_2),
        Vk.OEM_PERIOD: JmkKey(Vk.KEY_3),
        Vk.J: JmkKey(Vk.KEY_4),
        Vk.K: JmkKey(Vk.KEY_5),
        Vk.D: JmkKey(Vk.KEY_6),
        Vk.U: JmkKey(Vk.KEY_7),
        Vk.I: JmkKey(Vk.KEY_8),
        Vk.O: JmkKey(Vk.KEY_9),
        Vk.H: JmkKey(Vk.SUBTRACT),
        Vk.OEM_1: JmkKey(Vk.ADD),
        Vk.P: JmkKey(Vk.OEM_PLUS),
        Vk.N: JmkKey(Vk.MULTIPLY),
        Vk.OEM_2: JmkKey(Vk.DIVIDE),
    },
]

hotkeys = [
    ("Win+q", "LAlt+F4"),
    # Win+n to minimize active window
    ([Vk.WIN, Vk.N], minimize_active_window),
    # Win+m to maximize active window
    ([Vk.WIN, Vk.M], toggle_maximize_active_window),
]


#######################
#  setup jmk
#######################

sysin, jmk, hks, sysout = create_jmk(layers, hotkeys)


class JmkService(daemon.Service):
    name = "jmk"
    is_running = False

    def start(self):
        self.is_running = True
        sysin.install()

    def stop(self):
        sysin.uninstall()
        self.is_running = False


daemon.register(JmkService)

if __name__ == "__main__":
    daemon.message_loop()
