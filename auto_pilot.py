#!/usr/bin/env python3
"""
auto_play_jre.py - JR East Train Simulator auto-pilot
Usage: python auto_pilot.py conf.yaml
"""

import logging
import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

from app_config import get_log_level, load_config
from auto_worker import AutoPilotWorker, Signals
from game_memory import MemoryReader
from privileges import elevate_self, is_admin
from train_control import ComfortableTrainController
from ui import MainWindow


def main(config_path: str | None = None):
    config_path = config_path or (sys.argv[1] if len(sys.argv) > 1 else "conf.yaml")
    cfg = load_config(config_path)

    logging.basicConfig(
        level=get_log_level(cfg),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    app = QApplication.instance() or QApplication(sys.argv)

    if sys.platform == "win32" and not is_admin():
        msg = (
            "Global hotkeys require administrator privileges.\n\n"
            "Relaunch as administrator, or the hotkeys (, and .) "
            "may not fire when the game is focused.\n\n"
            "Continue without admin rights?"
        )
        choice = QMessageBox.question(
            None, "Admin Required", msg,
            QMessageBox.Yes | QMessageBox.No
        )
        if choice == QMessageBox.No:
            elevate_self()
            return

    mem = MemoryReader()
    ctrl = ComfortableTrainController(cfg)
    signals = Signals()
    worker = AutoPilotWorker(mem, ctrl, cfg, signals)

    window = MainWindow(cfg, mem, ctrl, signals, worker)
    window.show()
    worker.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
