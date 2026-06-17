import time
from dataclasses import dataclass

import keyboard as kb

from game_memory import GameState

class TrainController:
    """Translates GameState into key presses."""

    def __init__(self, cfg: dict):
        self.cfg      = cfg
        self.ctrl_cfg = cfg["control"]
        self.t_type   = cfg["train_type"]
        self.keys1    = cfg["keys_1handle"]
        self.keys2    = cfg["keys_2handle"]
        self._hold_counter = 0
        self._last_action  = "none"
        # Physics decel table — tune these per-train if needed
        self.NOTCH_DECEL_MS2 = {
            1: 0.167, 2: 0.333, 3: 0.500, 4: 0.667,
            5: 0.833, 6: 0.972, 7: 1.194, 8: 1.389, 9: 2.222,
        }
        self.STOP_SAFETY = 0.90  # target 90% of physics limit → stops ~slightly before 0

    # ── Low-level key helpers ────────────────────────────────────────────────
    def _press(self, key: str):
        # Send to background window: use keyboard.send which works globally
        kb.send(key)
        time.sleep(0.05)

    def emergency_brake(self):
        key = self.keys1["emergency"] if self.t_type == "1handle" \
              else self.keys2["emergency"]
        self._press(key)
        self._last_action = "EMERGENCY"

    def brake_step(self, steps: int = 1):
        """Apply N brake notch steps."""
        if self.t_type == "1handle":
            for _ in range(steps):
                self._press(self.keys1["brake_more"])
        else:
            for _ in range(steps):
                self._press(self.keys2["brake_more"])
        self._last_action = f"brake+{steps}"

    def release_brake_step(self, steps: int = 1):
        if self.t_type == "1handle":
            for _ in range(steps):
                self._press(self.keys1["power_more"])   # same key on 1-handle
        else:
            for _ in range(steps):
                self._press(self.keys2["brake_less"])
        self._last_action = f"brake-{steps}"

    def set_neutral(self):
        if self.t_type == "1handle":
            self._press(self.keys1["neutral"])
        else:
            self._press(self.keys2["brake_zero"])
            self._press(self.keys2["power_zero"])
        self._last_action = "neutral"

    def _physics_target_speed(self, dist_m: float, notch: int) -> float:
        """Max allowable speed (km/h) to stop within dist_m using notch decel."""
        a = self.NOTCH_DECEL_MS2.get(notch, 1.194)
        v_ms = (2.0 * a * max(dist_m, 0.0)) ** 0.5
        return v_ms * 3.6 * self.STOP_SAFETY

    def _best_brake_notch(self, spd_kmh: float, dist_m: float) -> int:
        """Find the gentlest brake notch that still covers the current speed."""
        spd_ms = spd_kmh / 3.6
        for notch in range(1, 10):
            a = self.NOTCH_DECEL_MS2.get(notch, 1.194)
            v_max = (2.0 * a * max(dist_m, 0.0)) ** 0.5
            if spd_ms <= v_max:
                return notch
        return 9

    def power_step(self, steps: int = 1):
        if self.t_type == "1handle":
            for _ in range(steps):
                self._press(self.keys1["power_more"])
        else:
            for _ in range(steps):
                self._press(self.keys2["power_more"])
        self._last_action = f"power+{steps}"

    def reduce_power_step(self, steps: int = 1):
        if self.t_type == "1handle":
            for _ in range(steps):
                self._press(self.keys1["brake_more"])
        else:
            for _ in range(steps):
                self._press(self.keys2["power_less"])
        self._last_action = f"power-{steps}"

    # ── High-level control logic ─────────────────────────────────────────────
    def decide(self, state: GameState) -> str:
        """Compute and send the best control action. Returns action string."""
        if not state.valid:
            return "ocr_invalid"

        cfg  = self.ctrl_cfg
        spd  = state.speed_kmh
        lim  = min(state.limit_kmh, state.max_speed_kmh)
        dist = state.distance_m
        margin   = cfg["target_speed_margin_kmh"]
        approach = cfg["approach_margin_kmh"]
        stop_d   = cfg["stop_distance_m"]
        idle     = cfg["idle_speed_kmh"]

        # ── Emergency: imminent over-speed ──────────────────────────────────
        if spd > lim + approach * 2:
            self.emergency_brake()
            return "EMERGENCY"

        # ── Final stop approach ─────────────────────────────────────────────
        if dist <= stop_d and not state.is_pass_stop:
            if dist <= 0 and spd < idle:
                if state.brake_notch > 0:
                    self.set_neutral()
                elif state.power_notch == 0:
                    self.power_step(1)
                return f"creep_fwd dist={dist:.1f}m"

            planning_notch = state.brake_notch if state.brake_notch > 0 else 4
            v_target = self._physics_target_speed(dist, planning_notch)

            if spd > v_target:
                needed_notch = self._best_brake_notch(spd, dist)
                delta = needed_notch - state.brake_notch
                if state.brake_notch == 0:
                    self.set_neutral()
                    self.brake_step(needed_notch)
                elif delta > 0:
                    self.brake_step(min(delta, 2))
                elif delta < 0:
                    self.release_brake_step(1)
            else:
                if state.brake_notch > 1:
                    self.release_brake_step(1)
                elif state.brake_notch == 1:
                    self.set_neutral()
            return (f"approach_hold dist={dist:.0f}m "
                    f"tgt={v_target:.1f} spd={spd:.1f}")

        # ── Normal cruise / speed regulation ────────────────────────────────
        over  = spd - (lim - margin)
        under = (lim - approach) - spd

        if over > approach:
            # Significantly over: hard brake
            self.brake_step(2)
            return f"hard_brake spd={spd} lim={lim}"
        elif over > 0:
            # Slightly over: gentle brake
            self.brake_step(1)
            return f"brake spd={spd} lim={lim}"
        elif under > approach:
            # Significantly under: accelerate
            if state.power_notch < 4:
                self.power_step(2)
            else:
                self.power_step(1)
            return f"power++ spd={spd} lim={lim}"
        elif under > 0:
            # Slightly under: gentle power
            if state.brake_notch > 0:
                self.release_brake_step(1)
            elif state.power_notch == 0:
                self.power_step(1)
            return f"power+ spd={spd} lim={lim}"
        else:
            # In cruise band
            if state.brake_notch > 0:
                self.release_brake_step(1)
            elif state.power_notch > 2:
                self.reduce_power_step(1)
            return f"cruise spd={spd} lim={lim}"


# ────────────────────────────────────────────────────────────────────────────
# Background worker thread
# ────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class GearCommand:
    system: str
    notch: int
    label: str


class ComfortableTrainController:
    """Passenger-comfort controller that translates target notches into keys."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.ctrl_cfg = cfg["control"]
        self.comfort_cfg = cfg.get("comfort_control", {})
        self.t_type = cfg["train_type"]
        self.keys1 = cfg["keys_1handle"]
        self.keys2 = cfg["keys_2handle"]
        self._neutral_side = "power"
        self._next_key_time = 0.0
        self.NOTCH_DECEL_MS2 = {
            1: 0.167, 2: 0.333, 3: 0.500, 4: 0.667,
            5: 0.833, 6: 0.972, 7: 1.194,
        }

    def _press(self, key: str):
        duration = max(0.01, float(self.comfort_cfg.get("key_press_seconds", 0.03)))
        settle = max(0.0, float(self.comfort_cfg.get("key_settle_seconds", 0.04)))
        cooldown = max(0.0, float(self.comfort_cfg.get("key_cooldown_seconds", 0.25)))
        kb.press(key)
        time.sleep(duration)
        kb.release(key)
        time.sleep(settle)
        self._next_key_time = time.time() + cooldown

    def _max_step(self) -> int:
        return max(1, int(self.comfort_cfg.get("max_notch_step", 1)))

    def brake_step(self, steps: int = 1):
        for _ in range(steps):
            self._press(self.keys1["brake_more"] if self.t_type == "1handle"
                        else self.keys2["brake_more"])
        self._neutral_side = "brake"

    def release_brake_step(self, steps: int = 1):
        key = self.keys1["power_more"] if self.t_type == "1handle" \
              else self.keys2["brake_less"]
        for _ in range(steps):
            self._press(key)
        if steps:
            self._neutral_side = "brake"

    def power_step(self, steps: int = 1):
        for _ in range(steps):
            self._press(self.keys1["power_more"] if self.t_type == "1handle"
                        else self.keys2["power_more"])
        self._neutral_side = "power"

    def reduce_power_step(self, steps: int = 1):
        key = self.keys1["brake_more"] if self.t_type == "1handle" \
              else self.keys2["power_less"]
        for _ in range(steps):
            self._press(key)
        if steps:
            self._neutral_side = "power"

    def set_cut(self):
        if self.t_type == "1handle":
            self._press(self.keys1["neutral"])
        else:
            self._press(self.keys2["power_zero"])
        self._neutral_side = "power"

    def _normalize_gear(self, gear: str) -> str:
        aliases = {
            "\u5207": "CUT",
            "N": "CUT",
            "\u6291": "SUPPRESS",
            "SUP": "SUPPRESS",
            "\u975e\u5e38": "B7",
            "\u975e": "B7",
            "EMG": "B7",
            "EMERGENCY": "B7",
        }
        raw = str(gear).strip()
        return aliases.get(raw, aliases.get(raw.upper(), raw.upper()))

    def _gear_command(self, gear: str) -> GearCommand:
        name = self._normalize_gear(gear)
        if name == "CUT":
            return GearCommand("power", 0, "CUT")
        if name == "SUPPRESS":
            return GearCommand("brake", 0, "SUPPRESS")
        if name.startswith("P"):
            notch = min(max(int(name[1:]), 0), 5)
            return GearCommand("power", notch, f"P{notch}" if notch else "CUT")
        if name.startswith("B"):
            notch = min(max(int(name[1:]), 0), 7)
            return GearCommand("brake", notch, f"B{notch}" if notch else "SUPPRESS")
        return GearCommand("power", 0, "CUT")

    def _rule_gear(self, rules, diff_kmh: float, fallback: str) -> GearCommand:
        for rule in rules:
            if diff_kmh <= float(rule.get("diff_kmh", 999)):
                return self._gear_command(rule.get("gear", fallback))
        return self._gear_command(fallback)

    def _target_gear_for_speed(self, speed_error_kmh: float) -> GearCommand:
        deadband = float(self.comfort_cfg.get("deadband_kmh", 1.0))
        if speed_error_kmh >= 0:
            if speed_error_kmh <= deadband:
                return self._gear_command("CUT")
            return self._rule_gear(
                self.comfort_cfg.get("power_rules", []),
                speed_error_kmh,
                "P1",
            )

        over_kmh = abs(speed_error_kmh)
        if over_kmh <= deadband:
            return self._gear_command("SUPPRESS")
        return self._rule_gear(
            self.comfort_cfg.get("brake_rules", []),
            over_kmh,
            "B1",
        )

    def _physics_target_speed(self, dist_m: float, notch: int) -> float:
        notch = min(max(int(notch), 1), 7)
        a = self.NOTCH_DECEL_MS2.get(notch, self.NOTCH_DECEL_MS2[7])
        safety = float(self.comfort_cfg.get("stop_safety", 0.85))
        return ((2.0 * a * max(dist_m, 0.0)) ** 0.5) * 3.6 * safety

    def _stop_target_gear(self, spd_kmh: float, dist_m: float) -> GearCommand:
        if dist_m <= 0:
            return self._gear_command("SUPPRESS")

        for notch in range(1, 8):
            if spd_kmh <= self._physics_target_speed(dist_m, notch):
                if notch == 1:
                    return self._gear_command("SUPPRESS")
                return self._gear_command(f"B{notch}")

        return self._gear_command("B7")

    def _sync_neutral_side(self, state: GameState):
        if state.brake_notch > 0:
            self._neutral_side = "brake"
        elif state.power_notch > 0:
            self._neutral_side = "power"

    def _move_single_handle_to(self, state: GameState, target: GearCommand) -> str:
        step = self._max_step()
        if target.system == "power":
            if state.brake_notch > 0:
                self.set_cut()
                return f"set CUT before {target.label}"
            if state.power_notch > target.notch:
                self.reduce_power_step(min(step, state.power_notch - target.notch))
                return f"toward {target.label} via power down"
            if state.power_notch < target.notch:
                self.power_step(min(step, target.notch - state.power_notch))
                return f"toward {target.label} via power up"
            if target.notch == 0 and self._neutral_side != "power":
                self.power_step(1)
                return "set CUT"
            return f"hold {target.label}"

        if state.power_notch > 0:
            self.set_cut()
            return f"set CUT before {target.label}"
        if state.brake_notch > target.notch:
            self.release_brake_step(min(step, state.brake_notch - target.notch))
            return f"toward {target.label} via brake release"
        if state.brake_notch < target.notch:
            self.brake_step(min(step, target.notch - state.brake_notch))
            return f"toward {target.label} via brake up"
        if target.notch == 0 and self._neutral_side != "brake":
            self.brake_step(1)
            return "set SUPPRESS"
        return f"hold {target.label}"

    def _move_two_handle_to(self, state: GameState, target: GearCommand) -> str:
        step = self._max_step()
        if target.system == "power":
            if state.power_notch > target.notch:
                self.reduce_power_step(min(step, state.power_notch - target.notch))
                return f"toward {target.label} via power down"
            if state.power_notch < target.notch:
                self.power_step(min(step, target.notch - state.power_notch))
                return f"toward {target.label} via power up"
            return f"hold {target.label}"

        if state.brake_notch > target.notch:
            self.release_brake_step(min(step, state.brake_notch - target.notch))
            return f"toward {target.label} via brake release"
        if state.brake_notch < target.notch:
            self.brake_step(min(step, target.notch - state.brake_notch))
            return f"toward {target.label} via brake up"
        return f"hold {target.label}"

    def _move_to(self, state: GameState, target: GearCommand) -> str:
        self._sync_neutral_side(state)
        wait_s = self._next_key_time - time.time()
        if wait_s > 0:
            return f"wait key_cooldown {wait_s:.2f}s for {target.label}"
        if self.t_type == "1handle":
            return self._move_single_handle_to(state, target)
        return self._move_two_handle_to(state, target)

    def decide(self, state: GameState) -> str:
        if not state.valid:
            return "state_invalid"

        spd = state.speed_kmh
        lim = min(state.limit_kmh, state.max_speed_kmh)
        dist = state.distance_m
        margin = self.ctrl_cfg["target_speed_margin_kmh"]
        stop_d = self.ctrl_cfg["stop_distance_m"]
        idle = self.ctrl_cfg["idle_speed_kmh"]
        target_speed = max(0.0, lim - margin)
        mode = "cruise"

        if dist <= stop_d and not state.is_pass_stop:
            if dist <= 0 and spd < idle:
                target = self._gear_command("SUPPRESS")
                action = self._move_to(state, target)
                return f"stopped target={target.label} {action}"

            target = self._stop_target_gear(spd, dist)
            action = self._move_to(state, target)
            planning_notch = int(self.comfort_cfg.get("stop_planning_brake", 4))
            planned_speed = self._physics_target_speed(dist, planning_notch)
            return (f"approach_stop plan_spd={planned_speed:.1f} "
                    f"spd={spd:.1f} dist={dist:.0f}m "
                    f"target={target.label} {action}")

        target = self._target_gear_for_speed(target_speed - spd)
        action = self._move_to(state, target)
        return (f"{mode} tgt_spd={target_speed:.1f} spd={spd:.1f} "
                f"target={target.label} {action}")

