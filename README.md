# JigsawWM

JigsawWM is a free and open-source project that aims to increase your productivity by offering a set of automation facilities, including the jmk module as an AHK alternative, a Tiling Window Manager to free you from managing windows manually and the Daemon to support any customization you may have in mind.

# What Can I Do?

## Service: jmk
Software-defined keyboard/mouse automation which mimics the [QMK](https://qmk.fm) as an alternative to [AutoHotkey](https://autohotkey.com)

1. My pinky is hurting - the dual-role key
You should try using `F` as the `Control` key, the following code would turn it into a dual-role key: it acts as the `LControl` when held, `F` when tapped:
```
        Vk.F: JmkTapHold(tap=Vk.F, hold=Vk.LCONTROL),
```
What if I need to enter a bunch of `F`?
Tap it and then hold it down within `quick_tap_term`(default 120ms)

2. I use F12 a lot, can I tap it without looking at the keyboard? - the layers
Sure, the problem with modern keyboards is they are enormous, 104 or even more. It is inconvenient when the keys you use frequently are far away from the Home Row (`a`, `s`, `d`, `f`, ...). With `layer` you may "move" the needed key into your reach:
```
layers = [
    { # layer 0
        # activate layer 3 when held
        Vk.T: JmkTapHold(tap=Vk.T, hold=3),
    },
    { # layer 1
      ...
    },
    { # layer 2
      ...
    },
    { # layer 3
        Vk.Z: JmkKey(Vk.F1),
    }
```
Now, hold the key `T` and press `Z`, you get `F1`

3. I would like to press `Win+Q` to close the active Window.
`hotkey` at your service, furthermore, you may press `Win+N` to minimize or `Win+M` to maximize the active window
```python
hotkeys = [
    ("Win+q", "LAlt+F4"),
    # Win+n to minimize active window
    ([Vk.WIN, Vk.N], minimize_active_window),
    # Win+m to maximize active window
    ([Vk.WIN, Vk.M], toggle_maximize_active_window),
]
```

4. For browsing smoothingly with the Mouse, try the following setup
- `Mouse Forward + Left Button`: send `Ctrl + w` (close tab in Chrome and other apps)
- `Mouse Forward + Wheel Up`: send `Ctrl + PageUp` (previous tab in Chrome and other apps)
- `Mouse Forward + Wheel Down`: send `Ctrl + PageDown` (next tab in Chrome and other apps)

5. Check out the [examples/jmk.pyw](example/jmk.pyw) to find out more


## Service: tiling window manager

The **WindowManager** follows the [suckless philosophy](https://suckless.org/philosophy/) and works just like the [dwm](https://dwm.suckless.org/). All windows are treated as an `Ordered List`, they will be moved into places based on their `Order` and specified `Layout` **automatically**, save you from arranging them manually.

### Demo

https://user-images.githubusercontent.com/61080/210168366-e70dd649-f6ef-41bb-a8e5-941e392d770a.mp4

### Default keybindings

- `Win + j`: activate next window and move the cursor to its center
- `Win + k`: activate the previous window and move the cursor to its center
- `Win + Shift + j`: move the active window down in the list (swap with the next one) 
- `Win + Shift + k`: move the active window up in the list (swap with the previous one)
- `Win + /`: swap the active window with **the first window** in the list or **the second window** if it is the first window already
- `Win + Space`: next theme, `Theme` consists of `Layout`, `Background`, `gap`, etc. to determine how windows should be placed
- `Win + i`: activate the first window of the next monitor if any or move cursor only
- `Win + u`: activate the first window of the previous monitor if any or move cursor only
- `Win + Shift + i`: move the active window to the next monitor
- `Win + Shift + u`: move the active window to the previous monitor

## Service: run console program in the background

Sometimes, software that should be run as a system service may not offer an installer to do the job, worse, it may ship as a Console Program. Nobody wants a Console Window stays on their desktops, and yes, I'm talking about [SyncThing](https://syncthing.net/). I love it but I would like it to run in the background quietly.

```py
class SyncthingService(daemon.ProcessService):
    name = "syncthing"
    args = [
        r"C:\Programs\syncthing-windows-amd64-v1.23.2\syncthing.exe",
        "-no-browser",
        "-no-restart",
        "-no-upgrade",
    ]
    log_path = r"C:\Programs\syncthing-windows-amd64-v1.23.2\syncthing.log"


daemon.register(SyncthingService)
```


## Task: automate your workflows with tasks

1. I would like to open a folder inside the Chromium Bookmark on the first boot-up every day.
```python
class DailyRoutine(daemon.Task):
    name = "daily routine"

    def run(self):
        chrome.open_fav_folder("bookmark_bar", "daily")

    def condition(self):
        # trigger only once on daily-basis
        return smartstart.daily_once("daily websites")


daemon.register(DailyRoutine)
```

2. I would like to launch my IM / Mail Client on workdays
```python
class WorkdayRoutine(daemon.Task):
    name = "workday routine"

    def __init__(self) -> None:
        super().__init__()
        self.holiday_book = ChinaHolidayBook()

    def run(self):
        smartstart.start_if_not_running(
            r"C:\Users\Klesh\AppData\Local\Feishu\Feishu.exe"
        )
        smartstart.start_if_not_running(
            r"C:\Program Files\Mozilla Thunderbird\thunderbird.exe"
        )

    def condition(self):
        return self.holiday_book.is_workhour(extend=timedelta(hours=2))


daemon.register(WorkdayRoutine)
```


# Installation

Tested on **Windows 11 Build 22000** and **Python 3.11.1**.
Should work on **Windows 10** and **Python 3.8**


Install from pypi
```
pip install jigsawwm
```

Install from Github repo
```
pip install git+https://github.com/klesh/JigsawWM.git
```

## Quick Start



### Step 1: Create a `.pyw` file as your "Configuration"

Choose services you like from the [examples](examples) folder, you may use any of the following directly.

- [examples/jmk.pyw](examples/jmk.pyw) if you are looking for a QMK/AutoHotkey alternative
- [examples/services.pyw](examples/services.pyw) if you are trying to run some Console Program as Service in the background
- [examples/tasks.pyw](examples/tasks.pyw) if you are looking for a solution to automate your workflow smartly on startup
- [examples/wm.pyw](examples/wm.pyw) if you are looking for a tiling window manager
- [examples/jigsaw.pyw](examples/wm.pyw) the whole package of the above

### Step 2: Launch your `.pyw` file and manage your services

Double-click the `.pyw` file and a tray icon should appear, right-click the icon to manage your services.
![image](https://github.com/klesh/JigsawWM/assets/61080/dd6b0c05-19eb-4a55-a7b6-8c66afff09b9)


### Step 3: Launch at startup

1. Open your **Startup** folder by pressing `Win + r` to activate the **Run** dialog and type in `shell:startup`, a FileExplorer should pop up.
2. Create a shortcut to your `.pyw` file. Done!


## Document

[Read the Docs](https://jigsawwm.readthedocs.io/en/latest/)

