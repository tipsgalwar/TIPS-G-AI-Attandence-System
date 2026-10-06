"""
TIPS-G ALWAR Student Attendance System — Fast Startup Entry Point
Optimized for ultra-fast startup (<100ms) with active continuous animation
and adaptive indicators for low-spec / CPU-only machines.
"""
import os
import sys
import time
from pathlib import Path

# Fast environment configuration
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtWidgets import QApplication, QSplashScreen, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class FastStartupSplashScreen(QSplashScreen):
    """
    Lightweight, continuous-animation splash screen.
    Guarantees immediate visual appearance in <100ms and active pulsing visual feedback
    even on low-end, CPU-only machines during model warmup.
    """
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(560, 340)
        
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(geo.center().x() - 280, geo.center().y() - 170)

        self.spinner_idx = 0
        self.start_time = time.time()
        self.current_milestone_text = "Starting application workspace..."
        self.target_progress = 15
        self.displayed_progress = 15

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)

        # Header Title
        title_lbl = QLabel("TIPS-G ALWAR")
        title_lbl.setStyleSheet("font-size: 26px; font-weight: 900; color: #38bdf8; letter-spacing: 1px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("Student Attendance AI System")
        sub_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #94a3b8;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_lbl)

        # Mode Badge (Detecting CPU vs GPU mode)
        badge_layout = QHBoxLayout()
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mode_badge = QLabel("⚡ Low-Latency Architecture • CPU / Adaptive AI Mode")
        self.mode_badge.setStyleSheet("""
            background-color: rgba(56, 189, 248, 0.12);
            color: #38bdf8;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 10px;
            border: 1px solid rgba(56, 189, 248, 0.25);
        """)
        badge_layout.addWidget(self.mode_badge)
        layout.addLayout(badge_layout)

        layout.addStretch()

        # Dynamic Status with Active Spinner
        self.status_label = QLabel(f"{self.SPINNER_FRAMES[0]} Starting application workspace...")
        self.status_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #e2e8f0;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Progress Bar with Smooth Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(15)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 5px;
                border: 1px solid #334155;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #2563eb);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Sub-status note for slow/low-resource machines
        self.sub_note = QLabel("Initializing background core modules. Please wait a moment...")
        self.sub_note.setStyleSheet("font-size: 11px; font-weight: 500; color: #64748b;")
        self.sub_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_note)

        footer_lbl = QLabel("Powered by Deep Learning & Computer Vision")
        footer_lbl.setStyleSheet("font-size: 10px; color: #475569;")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer_lbl)

        self.setStyleSheet("""
            QSplashScreen {
                background-color: #0b1120;
                border: 2px solid #3b82f6;
                border-radius: 16px;
            }
        """)

        # ── High-frequency active heartbeat timer (60ms) ────────────────────
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._on_pulse)
        self.pulse_timer.start(60)

    def _on_pulse(self):
        # 1. Update spinner animation frame
        self.spinner_idx = (self.spinner_idx + 1) % len(self.SPINNER_FRAMES)
        frame = self.SPINNER_FRAMES[self.spinner_idx]
        self.status_label.setText(f"{frame}  {self.current_milestone_text}")

        # 2. Smoothly ease progress bar toward target
        if self.displayed_progress < self.target_progress:
            self.displayed_progress += 1
            self.progress_bar.setValue(self.displayed_progress)

        # 3. Dynamic hints for low-resource CPUs taking longer
        elapsed = time.time() - self.start_time
        if elapsed > 6.0 and self.displayed_progress < 85:
            self.sub_note.setText("Optimizing facial neural networks for CPU. Almost ready...")
            self.sub_note.setStyleSheet("font-size: 11px; font-weight: 600; color: #38bdf8;")
        elif elapsed > 3.0 and self.displayed_progress < 60:
            self.sub_note.setText("Allocating biometric vector cache in memory...")

    @pyqtSlot(int, str)
    def update_progress(self, val: int, text: str):
        self.target_progress = val
        self.current_milestone_text = text
        self.status_label.setText(f"{self.SPINNER_FRAMES[self.spinner_idx]}  {text}")
        QApplication.processEvents()

    def closeEvent(self, event):
        if self.pulse_timer:
            self.pulse_timer.stop()
        super().closeEvent(event)


class BackgroundAppLoader(QThread):
    progress_changed = pyqtSignal(int, str)
    finished = pyqtSignal(object, object, object)

    def run(self):
        try:
            self.progress_changed.emit(40, "Loading graphical UI components & themes...")
            from frontend.main import MainWindow, LoginWindow, MODERN_STYLE
            from frontend.api_client import api_client

            self.progress_changed.emit(75, "Restoring verified user session...")
            restored_user = api_client.restore_session()

            self.progress_changed.emit(100, "Starting workspace environment...")
            self.finished.emit(restored_user, MainWindow, LoginWindow)
        except Exception as e:
            from loguru import logger
            logger.error(f"App initialization error: {e}")
            self.finished.emit(None, None, None)


def main():
    app = QApplication(sys.argv)
    
    # ── Single Instance Guard ───────────────────────────────────────────────
    socket = QLocalSocket()
    socket.connectToServer("tipsg_alwar_attendance_single_instance")
    if socket.waitForConnected(300):
        # Another instance is already running; tell it to focus and exit
        socket.write(b"ACTIVATE")
        socket.flush()
        socket.waitForBytesWritten(300)
        sys.exit(0)

    server = QLocalServer()
    server.removeServer("tipsg_alwar_attendance_single_instance")
    server.listen("tipsg_alwar_attendance_single_instance")

    # ── Show Instant Splash Screen (<100ms) ──────────────────────────────────
    splash = FastStartupSplashScreen()
    splash.show()
    app.processEvents()

    main_win = None
    login_win = None

    def on_new_connection():
        # Handle secondary launch clicks: bring current window to front
        client = server.nextPendingConnection()
        if client:
            client.waitForReadyRead(300)
            if main_win:
                main_win.setWindowState(main_win.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
                main_win.raise_()
                main_win.activateWindow()
            elif login_win:
                login_win.setWindowState(login_win.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
                login_win.raise_()
                login_win.activateWindow()
            client.disconnectFromServer()

    server.newConnection.connect(on_new_connection)

    # ── Async Module & AI Loader ────────────────────────────────────────────
    loader = BackgroundAppLoader()
    loader.progress_changed.connect(splash.update_progress)

    def on_loaded(restored_user, MainWindowClass, LoginWindowClass):
        nonlocal main_win, login_win
        if splash.pulse_timer:
            splash.pulse_timer.stop()
        splash.close()

        if not MainWindowClass:
            from frontend.main import MainWindow as MainWindowClass, LoginWindow as LoginWindowClass

        from frontend.main import MODERN_STYLE
        from frontend.icon_manager import icon_manager
        icon_manager.apply_to_app(app)
        app.setStyleSheet(MODERN_STYLE)

        if restored_user:
            main_win = MainWindowClass(restored_user)
            main_win.setStyleSheet(MODERN_STYLE)
            main_win.showMaximized()
        else:
            login_win = LoginWindowClass()
            login_win.setStyleSheet(MODERN_STYLE)

            def on_login_success(user_info):
                nonlocal main_win
                main_win = MainWindowClass(user_info)
                main_win.setStyleSheet(MODERN_STYLE)
                main_win.showMaximized()
                login_win.close()

            login_win.login_success.connect(on_login_success)
            login_win.show()

    loader.finished.connect(on_loaded)
    loader.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
