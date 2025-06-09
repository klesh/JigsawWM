# JigsawWM

**JigsawWM** is a free and open-source productivity toolkit for Windows that brings advanced automation and tiling window management to your desktop.

It combines:

* **JMK Module** — a programmable keyboard/mouse automation system inspired by [QMK](https://qmk.fm) and an alternative to [AutoHotkey](https://autohotkey.com).
* **Tiling Window Manager** — automatically arranges your windows, freeing you from tedious manual window placement.
* **Daemon Framework** — enables background services and daily workflow automation, all easily customizable.

---

## 🎥 Demo

[https://user-images.githubusercontent.com/61080/210168366-e70dd649-f6ef-41bb-a8e5-941e392d770a.mp4](https://user-images.githubusercontent.com/61080/210168366-e70dd649-f6ef-41bb-a8e5-941e392d770a.mp4)

---

## 📦 Installation

Tested on:

* **Windows 11 (Build 22000)**
* **Python 3.11.1**

Also compatible with:

* **Windows 10**
* **Python 3.8+**

### Install from PyPI:

```bash
pip install jigsawwm
```

### Install from GitHub:

```bash
pip install git+https://github.com/klesh/JigsawWM.git
```

---

## ⚡ Quick Start

### Step 1: Download and Customize

Download the example config file: [`example/full.pyw`](example/full.pyw) and adjust it to your needs.

---

### 🔧 Step 1.1 - Configure General Keybindings (JMK)

JMK is a programmable input automation engine. Here are some useful examples:

#### 1. Tap-Hold Modifier (e.g., `CapsLock` as `Esc` on tap, `Ctrl` on hold):

```python
daemon.jmk.core.register_layers([
    {
        Vk.CAPITAL: JmkTapHold(tap=Vk.ESCAPE, hold=Vk.LCONTROL),
    },
])
```

💡 *Tip:* Tap it and hold within `quick_tap_term` (default: 120ms) to send multiple `Esc`.

#### 2. Access Keys with Layers (e.g., press `T+Z` to get `F1`):

```python
daemon.jmk.core.register_layers([
    { Vk.T: JmkTapHold(tap=Vk.T, hold=3) },  # Layer switch
    {}, {}, {},
    { Vk.Z: JmkKey(Vk.F1) },  # Layer 3
])
```

#### 3. Hotkeys (e.g., `Win+Q` to close window):

```python
daemon.jmk.hotkeys.register_triggers([
    ("Win+q", "LAlt+F4"),
    ([Vk.WIN, Vk.N], minimize_active_window),
])
```

---

### 🪟 Step 1.2 - Configure the Window Manager

JigsawWM follows the [suckless philosophy](https://suckless.org/philosophy/) and mimics [dwm](https://dwm.suckless.org/), organizing windows in a strict order and layout for automatic tiling.

#### 1. Window Navigation & Layouts

```python
daemon.wm.hotkeys = [
    ([Vk.WIN, Vk.CTRL, Vk.J], daemon.wm.manager.next_window),
    ([Vk.WIN, Vk.CTRL, Vk.K], daemon.wm.manager.prev_window),
    ([Vk.WIN, Vk.SHIFT, Vk.J], daemon.wm.manager.swap_next),
    ([Vk.WIN, Vk.SHIFT, Vk.K], daemon.wm.manager.swap_prev),
    ("Win+Ctrl+/", daemon.wm.manager.set_master),
    ("Win+Ctrl+.", daemon.wm.manager.roll_next),
    ("Win+Ctrl+,", daemon.wm.manager.roll_prev),
    ([Vk.WIN, Vk.CONTROL, Vk.M], daemon.wm.manager.toggle_mono),
    ("Win+Shift+Space", daemon.wm.manager.toggle_tilable),
]
```

#### 2. Workspaces (Per Monitor)

```python
# Switch workspace
("Win+Ctrl+a", partial(daemon.wm.manager.switch_to_workspace, 0)),
("Win+Ctrl+s", partial(daemon.wm.manager.switch_to_workspace, 1)),

# Move window to workspace
("Win+Shift+a", partial(daemon.wm.manager.move_to_workspace, 0)),
("Win+Shift+s", partial(daemon.wm.manager.move_to_workspace, 1)),
```

#### 3. Multi-Monitor Support

```python
([Vk.WIN, Vk.U], daemon.wm.manager.prev_monitor),
([Vk.WIN, Vk.I], daemon.wm.manager.next_monitor),
([Vk.WIN, Vk.SHIFT, Vk.U], daemon.wm.manager.move_to_prev_monitor),
([Vk.WIN, Vk.SHIFT, Vk.I], daemon.wm.manager.move_to_next_monitor),
```

#### 4. Window Rules

```python
daemon.wm.manager.config = WmConfig(
    rules=[
        WmRule(exe="Flow.Launcher.exe", manageable=False),
        WmRule(exe="7zFM.exe", tilable=False),
    ]
)
```

---

### ⚙️ Step 1.3 - Manage Background Services

JigsawWM can manage external processes via tray menu:

```python
daemon.register(
    ProcessService(
        name="syncthing",
        args=["syncthing.exe", "-no-browser", "-no-restart", "-no-upgrade"],
        log_path=os.path.join(os.getenv("LOCALAPPDATA"), "syncthing.log"),
    )
)
```

![Tray](https://github.com/klesh/JigsawWM/assets/61080/dd6b0c05-19eb-4a55-a7b6-8c66afff09b9)

---

### 🤖 Step 1.4 - Automate Daily Routines

#### 1. Open your `daily` folder in a browser once per day:

```python
daemon.register(
    DailyWebsites(
        browser_name="thorium",
        fav_folder="daily",
        test_url="https://google.com",
        proxy_url="http://localhost:7890",
    )
)
```

#### 2. Auto-launch apps on workdays:

```python
daemon.register(
    WorkdayAutoStart(
        country_code="CN",
        apps=[
            r"C:\Users\Klesh\AppData\Local\Feishu\Feishu.exe",
            r"C:\Program Files\Betterbird\betterbird.exe",
            r"C:\Users\Klesh\AppData\Local\Programs\obsidian\Obsidian.exe",
        ],
    )
)
```

---

## 🚀 Step 2: Launch and Manage

Double-click your `.pyw` file.
A tray icon will appear — right-click it to manage services.

---

## 🔄 Step 3: Launch at Startup

1. Press `Win + R` → type `shell:startup` → hit Enter
2. Add a shortcut to your `.pyw` script in the folder

---

## 📚 Documentation

👉 [Read the Docs](https://jigsawwm.readthedocs.io/en/latest/)
