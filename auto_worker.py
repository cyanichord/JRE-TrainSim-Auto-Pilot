import re
import time

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from game_memory import GameState, MemoryReader
from train_control import ComfortableTrainController

class Signals(QObject):
    state_updated  = pyqtSignal(object)   # GameState
    log_message    = pyqtSignal(str)
    running_changed = pyqtSignal(bool)


class AutoPilotWorker(QThread):
    def __init__(self, mem: MemoryReader, ctrl: ComfortableTrainController,
                 cfg: dict, signals: Signals):
        super().__init__()
        self.mem     = mem
        self.ctrl    = ctrl
        self.cfg     = cfg
        self.signals = signals
        self._running = False
        self._paused  = False
        self.is_pass_stop = False

    def _debug_state_message(self, state: GameState, action: str,
                             elapsed: float, sleep_for: float) -> str:
        target_match = re.search(r"tgt_spd=([0-9.]+)", action)
        speed_error = "?"
        if target_match:
            speed_error = f"{float(target_match.group(1)) - state.speed_kmh:.2f}kmh"

        if self.cfg.get("train_type") == "1handle":
            key_info = (
                f"keys brake_more={self.cfg['keys_1handle']['brake_more']} "
                f"neutral={self.cfg['keys_1handle']['neutral']} "
                f"power_more={self.cfg['keys_1handle']['power_more']}"
            )
        else:
            key_info = (
                f"keys brake_more={self.cfg['keys_2handle']['brake_more']} "
                f"brake_less={self.cfg['keys_2handle']['brake_less']} "
                f"brake_zero={self.cfg['keys_2handle']['brake_zero']} "
                f"power_more={self.cfg['keys_2handle']['power_more']} "
                f"power_less={self.cfg['keys_2handle']['power_less']} "
                f"power_zero={self.cfg['keys_2handle']['power_zero']}"
            )

        return (
            f"[DEBUG] [{time.strftime('%H:%M:%S')}] "
            f"valid={state.valid} train={self.cfg.get('train_type')} "
            f"pass_stop={state.is_pass_stop} "
            f"speed={state.speed_kmh:.2f}kmh "
            f"limit={state.limit_kmh:.0f}kmh "
            f"max={state.max_speed_kmh:.0f}kmh "
            f"speed_error={speed_error} "
            f"distance={state.distance_m:.1f}m "
            f"gear={state.gear_raw or '?'} "
            f"power_notch={state.power_notch} "
            f"brake_notch={state.brake_notch} "
            f"action=\"{action}\" "
            f"loop_hz={self.cfg['control']['loop_hz']} "
            f"deadband={self.cfg.get('comfort_control', {}).get('deadband_kmh')} "
            f"max_step={self.cfg.get('comfort_control', {}).get('max_notch_step')} "
            f"tap_s={self.cfg.get('comfort_control', {}).get('key_press_seconds')} "
            f"settle_s={self.cfg.get('comfort_control', {}).get('key_settle_seconds')} "
            f"cooldown_s={self.cfg.get('comfort_control', {}).get('key_cooldown_seconds')} "
            f"elapsed_ms={elapsed * 1000:.1f} "
            f"sleep_ms={sleep_for * 1000:.1f} "
            f"{key_info}"
        )

    def start_pilot(self):
        self._running = True
        self._paused  = False
        if not self.isRunning():
            self.start()
        self.signals.running_changed.emit(True)
        self.signals.log_message.emit("▶  Auto-pilot STARTED")

    def stop_pilot(self):
        self._running = False
        self.signals.running_changed.emit(False)
        self.signals.log_message.emit("■  Auto-pilot STOPPED")

    def run(self):
        hz = self.cfg["control"]["loop_hz"]
        interval = 1.0 / hz
        while True:
            if not self._running:
                time.sleep(0.1)
                continue
            t0 = time.time()
            state = None
            action = None
            try:
                state  = self.mem.read()
                state.is_pass_stop = self.is_pass_stop
                action = self.ctrl.decide(state)
                self.signals.state_updated.emit(state)
            except Exception as exc:
                self.signals.log_message.emit(f"[ERROR] {exc}")
            elapsed = time.time() - t0
            sleep_for = max(0, interval - elapsed)
            if state is not None and action is not None:
                self.signals.log_message.emit(
                    self._debug_state_message(state, action, elapsed, sleep_for)
                )
            time.sleep(sleep_for)
