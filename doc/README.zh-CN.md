# JRE TrainSim Auto-Pilot

**语言：** [English](https://github.com/cyanichord/JRE-TrainSim-Auto-Pilot/blob/main/README.md) | 简体中文 | [日本語](https://github.com/cyanichord/JRE-TrainSim-Auto-Pilot/blob/main/doc/README.ja.md)

JRE TrainSim Auto-Pilot 是一个面向 **JR East Train Simulator** 的 Python 桌面辅助驾驶工具。它从游戏内存读取列车状态，根据配置计算更舒适的目标档位，并通过普通键盘输入控制列车。项目的核心目标是平顺驾驶：减少不必要的急促制动，限制档位变化幅度，让驾驶表现更像车上真的有乘客。

> 本项目是个人使用的实验性辅助工具。请负责任地使用，并只在允许自动化操作的环境中运行。

## 功能

- 从模拟器进程读取速度、限速、距离、牵引档位和制动档位。
- 通过键盘输入控制列车，而不是直接修改游戏数值。
- 支持单手柄和双手柄列车配置。
- 可配置 `CUT`、`P1-P5`、`SUPPRESS`、`B1-B7` 的档位选择规则。
- 正常运行中不会使用紧急制动档。
- 提供 PyQt 图形界面，包括启动、停止和停车区域选择。
- 支持通过 `conf.yaml` 开启可选文件日志。

## 环境要求

- Windows
- 建议使用 Python 3.10 或更新版本
- JR East Train Simulator 正在运行，进程名为 `JREAST_TrainSimulator.exe`
- Python 依赖：
  - `PyQt5`
  - `pymem`
  - `keyboard`
  - `PyYAML`

安装依赖：

```powershell
pip install PyQt5 pymem keyboard PyYAML
```

`keyboard` 库在游戏窗口获得焦点时使用全局热键，可能需要管理员权限。

## 快速开始

1. 启动 JR East Train Simulator。
2. 在本项目目录中打开终端。
3. 运行：

```powershell
python .\run.py
```

`run.py` 会自动加载项目目录中的 `conf.yaml`。

也可以直接运行主脚本：

```powershell
python .\auto_pilot.py .\conf.yaml
```

## 使用方法

1. 点击 **Select Stop Region**，拖选游戏中用于判断下一站停车/通过的区域。
2. 成功选择有效区域后，**Start** 按钮会变为可用。
3. 点击 **Start** 或使用配置的热键启动辅助驾驶。
4. 点击 **Stop** 或使用配置的热键停止辅助驾驶。

默认热键：

- 启动：`,`
- 停止：`.`

## 配置

主要行为都在 [conf.yaml](conf.yaml) 中配置。

重要配置项：

- `hotkeys`：全局启动/停止热键。
- `train_type`：`1handle` 或 `2handle`。
- `control`：循环频率、目标速度余量、停车制动距离和停车判定速度。
- `keys_1handle` / `keys_2handle`：用于操作列车的键位。
- `logging`：日志等级和可选文件日志。
- `comfort_control`：舒适驾驶档位规则和按键轻触时间。

开启文件日志：

```yaml
logging:
  level: "DEBUG"
  file_enabled: true
  file_path: "jre.log"
```

## 项目结构

```text
run.py             项目入口，自动加载 conf.yaml
auto_pilot.py      应用启动和对象组装
app_config.py      默认配置和 YAML 加载
game_memory.py     GameState 与内存读取
train_control.py   列车控制与舒适驾驶逻辑
auto_worker.py     后台控制循环和 Qt 信号
ui.py              PyQt 用户界面
conf.yaml          用户配置文件
```

## 注意事项

- 内存地址偏移与特定模拟器版本相关。游戏更新后，读取结果可能不再正确。
- 控制器发送的是键盘输入，不会直接写入牵引或制动数值。
- 建议先使用保守设置，再逐步调整 `comfort_control`。

