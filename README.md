# JRE TrainSim Auto-Pilot

**Language:** English | [简体中文](https://github.com/cyanichord/JRE-TrainSim-Auto-Pilot/blob/main/doc/README.zh-CN.md) | [日本語](https://github.com/cyanichord/JRE-TrainSim-Auto-Pilot/blob/main/doc/README.ja.md)

JRE TrainSim Auto-Pilot is a Python desktop assistant for **JR East Train Simulator**. It reads game state from memory, calculates a comfortable target notch, and sends normal keyboard inputs to control the train. The project is designed around gentle driving behavior: avoid unnecessary harsh braking, keep notch changes small, and make the ride feel like there are real passengers on board.

> This project is an experimental driving assistant for personal use. Use it responsibly and only in environments where automation is allowed.

## Features

- Reads speed, limit, distance, power notch, and brake notch from the simulator process.
- Controls the train through keyboard input instead of directly modifying game values.
- Supports one-handle and two-handle train configurations.
- Uses configurable notch rules for `CUT`, `P1-P5`, `SUPPRESS`, and `B1-B7`.
- Avoids emergency brake commands during normal operation.
- Includes a PyQt UI with start/stop controls and a selectable stop-region helper.
- Supports optional file logging through `conf.yaml`.

## Requirements

- Windows
- Python 3.10 or newer recommended
- JR East Train Simulator running as `JREAST_TrainSimulator.exe`
- Python packages:
  - `PyQt5`
  - `pymem`
  - `keyboard`
  - `PyYAML`

Install dependencies with:

```powershell
pip install PyQt5 pymem keyboard PyYAML
```

The `keyboard` package may need administrator privileges for global hotkeys while the game window is focused.

## Quick Start

1. Start JR East Train Simulator.
2. Open a terminal in this project folder.
3. Run:

```powershell
python .\run.py
```

`run.py` automatically loads the bundled `conf.yaml` from the project directory.

You can also run the main script directly:

```powershell
python .\auto_pilot.py .\conf.yaml
```

## Using the App

1. Click **Select Stop Region** and drag over the UI area that indicates whether the next stop is a stop/pass point.
2. After a valid region is selected, the **Start** button becomes available.
3. Click **Start** or use the configured hotkey.
4. Click **Stop** or use the configured hotkey to disable the auto-pilot.

The default hotkeys are:

- Start: `,`
- Stop: `.`

## Configuration

Most behavior is configured in [conf.yaml](conf.yaml).

Important sections:

- `hotkeys`: global start/stop hotkeys.
- `train_type`: `1handle` or `2handle`.
- `control`: loop rate, target speed margin, stopping distance, and idle speed.
- `keys_1handle` / `keys_2handle`: keyboard bindings used to operate the train.
- `logging`: log level and optional file logging.
- `comfort_control`: notch-selection rules and keyboard tap timing.

To enable file logging:

```yaml
logging:
  level: "DEBUG"
  file_enabled: true
  file_path: "jre.log"
```

## Project Layout

```text
run.py             Project entry point that loads conf.yaml automatically
auto_pilot.py      Application wiring and main function
app_config.py      Configuration defaults and YAML loading
game_memory.py     GameState and memory reader
train_control.py   Train control and comfort logic
auto_worker.py     Background control loop and Qt signals
ui.py              PyQt user interface
conf.yaml          User configuration
```

## Notes

- The memory offsets are specific to the supported simulator build. If game updates change memory layout, readings may become incorrect.
- The controller sends keyboard input; it does not write throttle or brake values directly into game memory.
- Use conservative settings first, then tune `comfort_control` gradually.

