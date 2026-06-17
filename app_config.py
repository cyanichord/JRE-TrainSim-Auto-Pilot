import logging
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "hotkeys": {
        "start": ",",
        "stop":  ".",
    },
    "train_type": "1handle",   # "1handle" | "2handle"
    "control": {
        "target_speed_margin_kmh": 3,    # tolerance band ±3 km/h around limit
        "approach_margin_kmh":     10,   # start braking 10 km/h before limit
        "stop_distance_m":         100,  # distance-to-station brake threshold
        "idle_speed_kmh":          2,    # speed below which we consider stopped
        "loop_hz":                 10,   # OCR + control loop frequency
        "brake_hold_ticks":        3,    # hold a brake step N ticks before changing
        "power_hold_ticks":        3,
    },
    "keys_1handle": {
        "emergency":   "1",
        "brake_more":  "q",
        "neutral":     "s",
        "power_more":  "z",
    },
    "keys_2handle": {
        "emergency":   "/",
        "brake_more":  ",",
        "brake_less":  ".",
        "brake_zero":  "m",
        "power_more":  "z",
        "power_less":  "a",
        "power_zero":  "s",
    },
    "ocr": {
        "lang":          "ja,en",
        "upscale":       3,           # multiply ROI by this before OCR
        "binary_thresh": 200,
        "invert":        True,        # HUD is white text on dark → invert
    },
    "logging": {
        "level": "INFO",
        "file_enabled": False,
        "file_path": "jre.log",
    },
    "comfort_control": {
        "deadband_kmh": 1.0,
        "max_notch_step": 1,
        "key_press_seconds": 0.03,
        "key_settle_seconds": 0.04,
        "key_cooldown_seconds": 0.25,
        "stop_planning_brake": 4,
        "stop_safety": 0.85,
        "power_rules": [
            {"diff_kmh": 1, "gear": "CUT"},
            {"diff_kmh": 3, "gear": "P1"},
            {"diff_kmh": 6, "gear": "P2"},
            {"diff_kmh": 10, "gear": "P3"},
            {"diff_kmh": 15, "gear": "P4"},
            {"diff_kmh": 999, "gear": "P5"},
        ],
        "brake_rules": [
            {"diff_kmh": 1, "gear": "SUPPRESS"},
            {"diff_kmh": 3, "gear": "B1"},
            {"diff_kmh": 6, "gear": "B2"},
            {"diff_kmh": 9, "gear": "B3"},
            {"diff_kmh": 12, "gear": "B4"},
            {"diff_kmh": 15, "gear": "B5"},
            {"diff_kmh": 19, "gear": "B6"},
            {"diff_kmh": 999, "gear": "B7"},
        ],
    },
}


# ────────────────────────────────────────────────────────────────────────────
# Config helper
# ────────────────────────────────────────────────────────────────────────────
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def get_log_level(cfg: dict) -> int:
    level_name = str(cfg.get("logging", {}).get("level", "INFO")).upper()
    return LOG_LEVELS.get(level_name, logging.INFO)


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path: str) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if path and Path(path).exists():
        with open(path, encoding='utf-8') as f:
            user = yaml.safe_load(f) or {}
        cfg = deep_merge(cfg, user)
    return cfg
