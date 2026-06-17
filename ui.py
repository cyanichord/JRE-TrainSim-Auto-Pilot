import logging
import re
from pathlib import Path

import keyboard as kb
from PyQt5.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QApplication,
    QDesktopWidget,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app_config import LOG_LEVELS, get_log_level
from auto_worker import AutoPilotWorker, Signals
from game_memory import GameState, MemoryReader
from train_control import ComfortableTrainController

class ScreenSelector(QWidget):
    """Full-screen transparent overlay; user drags to select a region."""

    area_selected = pyqtSignal(QRect)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QDesktopWidget().screenGeometry())
        self.setCursor(Qt.CrossCursor)
        self._origin = QPoint()
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)

    def mousePressEvent(self, e):
        self._origin = e.pos()
        self._rubber.setGeometry(QRect(self._origin, QSize()))
        self._rubber.show()

    def mouseMoveEvent(self, e):
        self._rubber.setGeometry(
            QRect(self._origin, e.pos()).normalized())

    def mouseReleaseEvent(self, e):
        self._rubber.hide()
        rect = QRect(self._origin, e.pos()).normalized()
        self.hide()
        self.area_selected.emit(rect)
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 60))


# ────────────────────────────────────────────────────────────────────────────
# Main window
# ────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, cfg: dict, mem: MemoryReader,
                 ctrl: ComfortableTrainController, signals: Signals,
                 worker: AutoPilotWorker):
        super().__init__()
        self.cfg     = cfg
        self.mem     = mem
        self.ctrl    = ctrl
        self.signals = signals
        self.worker  = worker
        self.log_level = get_log_level(cfg)
        self.log_file_enabled = bool(cfg.get("logging", {}).get("file_enabled", False))
        self.log_file_path = Path(cfg.get("logging", {}).get("file_path", "jre.log"))
        self._running = False
        self.capture_timer = QTimer(self)
        self.capture_timer.timeout.connect(self._analyze_capture_region)
        self.capture_region = None
        self.controls_unlocked = False
        self._setup_ui()
        self._connect_signals()
        self._register_hotkeys()

    # ── UI construction ───────────────────────────────────────────────────
    def _setup_ui(self):
        self.setWindowTitle("JRE TrainSim Auto-Pilot")
        self.setMinimumWidth(560)
        self.setMinimumHeight(340)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        central = QWidget()
        central.setObjectName("glassRoot")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 14)

        # ── Status lights ──
        status_box = QGroupBox("Game State")
        status_layout = QGridLayout(status_box)
        status_layout.setHorizontalSpacing(10)
        status_layout.setVerticalSpacing(10)
        for col in range(3):
            status_layout.setColumnStretch(col, 1)
        self.lbl_speed   = self._make_value_label("Speed", "---", "#007aff")
        self.lbl_limit   = self._make_value_label("Limit", "---", "#ff9500")
        self.lbl_maxspd  = self._make_value_label("Max", "---",  "#34c759")
        self.lbl_dist    = self._make_value_label("Dist", "---",  "#af52de")
        self.lbl_gear    = self._make_value_label("Gear", "---",  "#ff3b30")
        self.lbl_stop_type = self._make_value_label("Type", "STOP", "#34c759")
        for idx, w in enumerate((self.lbl_speed, self.lbl_limit, self.lbl_maxspd,
                                 self.lbl_dist, self.lbl_gear, self.lbl_stop_type)):
            status_layout.addWidget(w, idx // 3, idx % 3)
        root.addWidget(status_box)

        # ── Controls ──
        ctrl_box = QGroupBox("Control")
        ctrl_row = QHBoxLayout(ctrl_box)
        ctrl_row.setSpacing(10)
        self.btn_start = QPushButton("Start  [%s]" %
                                     self.cfg["hotkeys"]["start"].upper())
        self.btn_stop  = QPushButton("Stop   [%s]" %
                                     self.cfg["hotkeys"]["stop"].upper())
        self.btn_start.setObjectName("startButton")
        self.btn_stop.setObjectName("stopButton")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)

        self.btn_capture = QPushButton("Select Stop Region")
        self.btn_capture.setObjectName("captureButton")
        self.btn_capture.clicked.connect(self._on_select_region)

        train_lbl = QLabel("Train type: " +
                           self.cfg.get("train_type","1handle").upper())
        train_lbl.setStyleSheet("color:#6e6e73;font-weight:600;")
        ctrl_row.addWidget(self.btn_capture)
        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_stop)
        ctrl_row.addStretch()
        ctrl_row.addWidget(train_lbl)
        root.addWidget(ctrl_box)

        # ── Status bar ──
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Select a stop region before starting auto-pilot.")

        # Frosted glass palette
        self._apply_frosted_theme()

    def _apply_frosted_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
            }
            QWidget#glassRoot {
                background: rgba(242, 242, 247, 172);
                border: 1px solid rgba(255, 255, 255, 210);
                border-radius: 12px;
                color: #1d1d1f;
            }
            QWidget {
                background: transparent;
                color: #1d1d1f;
                font-family: "SF Pro Text", "Segoe UI", Arial, sans-serif;
                font-size: 12px;
            }
            QGroupBox {
                background: rgba(255, 255, 255, 178);
                border: 1px solid rgba(60, 60, 67, 34);
                border-radius: 8px;
                margin-top: 16px;
                padding: 18px 12px 12px 12px;
                font-weight: 600;
                color: #1d1d1f;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 4px 10px;
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton {
                background: rgba(255, 255, 255, 210);
                border: 1px solid rgba(60, 60, 67, 42);
                border-radius: 8px;
                padding: 7px 16px;
                color: #1d1d1f;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 235);
            }
            QPushButton:disabled {
                background: rgba(242, 242, 247, 118);
                border-color: rgba(60, 60, 67, 24);
                color: rgba(60, 60, 67, 90);
            }
            QPushButton#startButton {
                background: rgba(52, 199, 89, 218);
                border-color: rgba(36, 138, 61, 125);
                color: #ffffff;
            }
            QPushButton#startButton:hover {
                background: rgba(48, 209, 88, 235);
            }
            QPushButton#startButton:disabled {
                background: rgba(242, 242, 247, 118);
                border-color: rgba(60, 60, 67, 24);
                color: rgba(60, 60, 67, 90);
            }
            QPushButton#stopButton {
                background: rgba(255, 59, 48, 220);
                border-color: rgba(184, 32, 25, 130);
                color: #ffffff;
            }
            QPushButton#stopButton:hover {
                background: rgba(255, 69, 58, 238);
            }
            QPushButton#stopButton:disabled {
                background: rgba(242, 242, 247, 118);
                border-color: rgba(60, 60, 67, 24);
                color: rgba(60, 60, 67, 90);
            }
            QPushButton#captureButton {
                background: rgba(0, 122, 255, 224);
                border-color: rgba(0, 83, 179, 145);
                color: #ffffff;
            }
            QPushButton#captureButton:hover {
                background: rgba(10, 132, 255, 240);
            }
            QLabel {
                color: #1d1d1f;
                background: transparent;
            }
            QStatusBar {
                color: #6e6e73;
                background: rgba(255, 255, 255, 132);
                border-top: 1px solid rgba(60, 60, 67, 28);
            }
        """)

    @staticmethod
    def _make_value_label(title: str, value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,210); "
            "border:1px solid rgba(60,60,67,28); border-radius:8px; "
            "padding:6px; }")
        layout = QVBoxLayout(frame)
        layout.setSpacing(3)
        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color:#6e6e73;font-size:10px;font-weight:500;")
        lbl_val = QLabel(value)
        lbl_val.setAlignment(Qt.AlignCenter)
        lbl_val.setStyleSheet(f"color:{color};font-size:18px;font-weight:700;")
        lbl_val.setObjectName("value")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        frame._value_lbl = lbl_val
        return frame

    # ── Signal connections ─────────────────────────────────────────────────
    def _on_select_region(self):
        self.selector = ScreenSelector()
        self.selector.area_selected.connect(self._on_region_selected)
        self.selector.show()

    def _on_region_selected(self, rect: QRect):
        if rect.width() <= 0 or rect.height() <= 0:
            self.status.showMessage("Select a non-empty stop region before starting auto-pilot.")
            return
        self.capture_region = rect
        self.controls_unlocked = True
        self.btn_start.setEnabled(not self._running)
        self.btn_stop.setEnabled(self._running)
        self.capture_timer.start(1000)
        self.status.showMessage("Stop region selected. Auto-pilot controls are ready.")
        self._on_log(f"[INFO] Screen region selected for stop logic: {rect.x()},{rect.y()} {rect.width()}x{rect.height()}")

    def _analyze_capture_region(self):
        if not self.capture_region:
            return
            
        screen = QApplication.primaryScreen()
        if not screen:
            return
            
        pixmap = screen.grabWindow(0, self.capture_region.x(), self.capture_region.y(), 
                                   self.capture_region.width(), self.capture_region.height())
        image = pixmap.toImage()
        
        blue_cnt = 0
        green_cnt = 0
        
        for y in range(image.height()):
            for x in range(image.width()):
                c = image.pixel(x, y)
                r = (c >> 16) & 0xff
                g = (c >> 8) & 0xff
                b = c & 0xff
                
                if r > 150 and g > 150 and b < 100:
                    continue
                    
                if b > r and b > g:
                    blue_cnt += 1
                elif g > r and g > b:
                    green_cnt += 1
                    
        is_pass = (blue_cnt > green_cnt)
        self.worker.is_pass_stop = is_pass
        
        lbl_text = "PASS" if is_pass else "STOP"
        color = "#007aff" if is_pass else "#34c759"
        self.lbl_stop_type._value_lbl.setText(lbl_text)
        self.lbl_stop_type._value_lbl.setStyleSheet(f"color:{color};font-size:18px;font-weight:700;")

    def _connect_signals(self):
        self.signals.state_updated.connect(self._on_state_update)
        self.signals.log_message.connect(self._on_log)
        self.signals.running_changed.connect(self._on_running_changed)

    def _register_hotkeys(self):
        try:
            kb.add_hotkey(
                self.cfg["hotkeys"]["start"],
                lambda: self._on_start(),
                suppress=False)
            kb.add_hotkey(
                self.cfg["hotkeys"]["stop"],
                lambda: self._on_stop(),
                suppress=False)
            self._on_log(
                f"[INFO] Hotkeys registered: "
                f"start={self.cfg['hotkeys']['start']}  "
                f"stop={self.cfg['hotkeys']['stop']}")
        except Exception as e:
            self._on_log(f"[WARN] Could not register hotkeys: {e}")

    # ── Slot handlers ──────────────────────────────────────────────────────
    def _on_start(self):
        if self._running:
            return
        if not self.controls_unlocked:
            self.status.showMessage("Select a stop region before starting auto-pilot.")
            return
        if not self.mem.pm:
            self.mem._connect()
            if not self.mem.pm:
                QMessageBox.warning(self, "Process Error",
                    "Could not hook JREAST_TrainSimulator.exe. Is the game running?")
                return
            
        self._running = True
        self.worker.start_pilot()

    def _on_stop(self):
        if not self._running:
            return
        self._running = False
        self.worker.stop_pilot()

    def _on_state_update(self, state: GameState):
        self.lbl_speed._value_lbl.setText(f"{state.speed_kmh:.1f}")
        self.lbl_limit._value_lbl.setText(f"{state.limit_kmh:.0f}")
        self.lbl_maxspd._value_lbl.setText(f"{state.max_speed_kmh:.0f}")
        self.lbl_dist._value_lbl.setText(f"{state.distance_m:.0f}m")
        self.lbl_gear._value_lbl.setText(state.gear_raw or "?")

    @staticmethod
    def _log_level_for_message(msg: str) -> int:
        match = re.match(r"^\[(DEBUG|INFO|WARN|WARNING|ERROR)\]", msg)
        if not match:
            return logging.INFO
        return LOG_LEVELS.get(match.group(1), logging.INFO)

    def _on_log(self, msg: str):
        if self._log_level_for_message(msg) < self.log_level:
            return
        if not self.log_file_enabled:
            return
        try:
            if self.log_file_path.parent != Path("."):
                self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_file_path.open("a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
        except OSError as exc:
            logging.warning("Could not write UI log to %s: %s",
                            self.log_file_path, exc)

    def _on_running_changed(self, running: bool):
        self._running = running
        self.btn_start.setEnabled(self.controls_unlocked and not running)
        self.btn_stop.setEnabled(self.controls_unlocked and running)
        self.status.showMessage(
            "Auto-pilot running…" if running else "Auto-pilot stopped.")

    def closeEvent(self, e):
        self.worker.stop_pilot()
        kb.unhook_all()
        e.accept()
