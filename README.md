# JigsawWM

JigsawWM is a dynamic window manager for Windows10/11 just like the suckless dwm for the X.

## Demo

https://user-images.githubusercontent.com/61080/210168366-e70dd649-f6ef-41bb-a8e5-941e392d770a.mp4

## Installation

Tested on **Windows 11 Build 22000** and **Python 3.11.1**.
Should work on **Windows 10** and **Python 3.8**


```
pip install git+https://github.com/klesh/JigsawWM.git
```

## Quick Start

**JigsawWm** follows the [suckless philosophy](https://suckless.org/philosophy/) and works just like [dwm - dynamic window manager | suckless.org software that sucks less](https://dwm.suckless.org/). All windows are treated as a `Ordered List`, they will be moved into places based on their `Order` and specified `Layout` **automatically** to improve your productivity.


### Step 1: Create a `.pyw` file as the "Configuration"

1. Download the [example.pyw](example.pyw) to your local hard drive
2. Edit the code as you see fit
3. Double-click the file and it should launch with a tray icon, or you may have to create a file association to the `Python` program
4. Create a shortcut in your `Startup` folder if you like it

### Step 2: Using hotkeys to manage your windows

- `Win + j`: activate next window and move cursor to its center
- `Win + k`: activate previous window and move cursor to its center
- `Win + Shift + j`: move active window down in the list / swap with the next one
- `Win + Shift + k`: move active window up in the list / swap with the previous one
- `Win + n`: minimized active window
- `Win + m`: maximize/unmaximized active window
- `Win + /`: swap active window with **first window** in the list or **second window** if it is the first window already
- `Win + q`: kill active window
- `Win + Space`: next theme, `Theme` consists of `Layout`, `Background`, `gap`, etc. to determine how windows should be placed
- `Win + i`: activate first window of the next monitor if any or move cursor only
- `Win + u`: activate first window of the previous monitor if any or move cursor only
- `Win + Shift + i`: move active window to next monitor
- `Win + Shift + u`: move active window to previous monitor
- `Win + Control + i`: inspect active window

### Step 3: Launch at startup

1. Open your **Startup** folder by pressing `Win + r` to activate the **Run** dialog and type in `shell:startup`, a FileExplorer should pop up.
2. Create a shortcut to your `.pyw` file. Done!


## Changelog

### 2023-02-02

- support portrait mode monitor (rotate layout by 90 degree)
- update readme