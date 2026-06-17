# JRE TrainSim Auto-Pilot

**言語:** [English](https://github.com/cyanichord/JRE-TrainSim-Auto-Pilot/blob/main/README.md) | [简体中文](https://github.com/cyanichord/JRE-TrainSim-Auto-Pilot/blob/main/doc/README.zh-CN.md) | 日本語

JRE TrainSim Auto-Pilot は、**JR East Train Simulator** 向けの Python 製デスクトップ補助ツールです。ゲームのメモリから列車状態を読み取り、設定に基づいて快適性を重視した目標ノッチを計算し、通常のキーボード入力で列車を操作します。急なブレーキや大きなノッチ変化を避け、実際に乗客がいるような自然で穏やかな運転を目指しています。

> このプロジェクトは個人利用を想定した実験的な運転補助ツールです。自動操作が許可されている環境で、責任を持って使用してください。

## 主な機能

- シミュレーターのプロセスから速度、制限速度、距離、力行ノッチ、ブレーキノッチを読み取ります。
- ゲーム内の値を直接書き換えず、キーボード入力で列車を操作します。
- ワンハンドル車両とツーハンドル車両の設定に対応します。
- `CUT`、`P1-P5`、`SUPPRESS`、`B1-B7` の選択ルールを設定できます。
- 通常運転では非常ブレーキを使用しません。
- PyQt ベースの UI を備え、開始、停止、停車判定エリアの選択ができます。
- `conf.yaml` で任意のファイルログ出力を有効にできます。

## 必要環境

- Windows
- Python 3.10 以降を推奨
- `JREAST_TrainSimulator.exe` として JR East Train Simulator が起動していること
- Python パッケージ：
  - `PyQt5`
  - `pymem`
  - `keyboard`
  - `PyYAML`

依存関係のインストール：

```powershell
pip install PyQt5 pymem keyboard PyYAML
```

ゲーム画面にフォーカスがある状態でグローバルホットキーを使う場合、`keyboard` パッケージには管理者権限が必要になることがあります。

## クイックスタート

1. JR East Train Simulator を起動します。
2. このプロジェクトフォルダーでターミナルを開きます。
3. 次のコマンドを実行します。

```powershell
python .\run.py
```

`run.py` は、プロジェクトフォルダー内の `conf.yaml` を自動で読み込みます。

メインスクリプトを直接実行することもできます。

```powershell
python .\auto_pilot.py .\conf.yaml
```

## 使い方

1. **Select Stop Region** をクリックし、次の駅が停車か通過かを判定するためのゲーム画面上の領域をドラッグで選択します。
2. 有効な領域が選択されると、**Start** ボタンが使用可能になります。
3. **Start** をクリックするか、設定済みのホットキーで補助運転を開始します。
4. **Stop** をクリックするか、設定済みのホットキーで補助運転を停止します。

既定のホットキー：

- 開始：`,`
- 停止：`.`

## 設定

主な動作は [conf.yaml](conf.yaml) で設定します。

重要な項目：

- `hotkeys`：開始/停止のグローバルホットキー。
- `train_type`：`1handle` または `2handle`。
- `control`：制御ループ頻度、目標速度の余裕、停車制動距離、停止判定速度。
- `keys_1handle` / `keys_2handle`：列車操作に使うキー設定。
- `logging`：ログレベルと任意のファイルログ出力。
- `comfort_control`：快適性を重視したノッチ選択ルールとキー入力時間。

ファイルログを有効にする例：

```yaml
logging:
  level: "DEBUG"
  file_enabled: true
  file_path: "jre.log"
```

## プロジェクト構成

```text
run.py             conf.yaml を自動で読み込む起動用エントリ
auto_pilot.py      アプリケーションの起動とオブジェクトの接続
app_config.py      既定設定と YAML 読み込み
game_memory.py     GameState とメモリ読み取り
train_control.py   列車制御と快適運転ロジック
auto_worker.py     バックグラウンド制御ループと Qt シグナル
ui.py              PyQt ユーザーインターフェース
conf.yaml          ユーザー設定ファイル
```

## 注意事項

- メモリオフセットは対応しているシミュレーターのビルドに依存します。ゲーム更新後は読み取り値が正しくなくなる可能性があります。
- コントローラーはキーボード入力を送信します。力行値やブレーキ値を直接メモリへ書き込むことはありません。
- 最初は控えめな設定で使い、`comfort_control` は少しずつ調整することをおすすめします。

