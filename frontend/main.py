import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
import sys
import tempfile
from datetime import datetime, date
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize, QTimer, QUrl, QDate, QRect, QPoint
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, 
    QHeaderView, QFileDialog, QComboBox, QTextEdit, QDialog, QFormLayout, 
    QMessageBox, QFrame, QSizePolicy, QProgressBar, QInputDialog, QStyle, QSplashScreen,
    QDateEdit, QGridLayout, QSystemTrayIcon
)

from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QColor, QDesktopServices, QPainter, QPen, QBrush
from loguru import logger
import cv2
import websocket
from frontend.utils.wifi_checker import (
    is_university_wifi,
    get_current_bssid
)
from frontend.icon_manager import icon_manager
from frontend.ui_effects import (
    AnimatedStackedWidget,
    AnimatedStatLabel,
    BiometricScanOverlay,
    NotificationToast,
    AsyncModelWarmupWorker,
    AmbientWaveBackground
)
import numpy as np

# Safe import API Client
try:
    from frontend.api_client import api_client
    from frontend.onnx_face_service import onnx_face_service
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from frontend.api_client import api_client
    from frontend.onnx_face_service import onnx_face_service

def format_12hr_time(val) -> str:
    if not val:
        return "-"
    raw_str = str(val).strip()
    if raw_str in ["-", "None", ""]:
        return "-"
    try:
        parts = raw_str.split(".")[0]
        if parts.count(":") == 2:
            time_obj = datetime.strptime(parts, "%H:%M:%S").time()
        elif parts.count(":") == 1:
            time_obj = datetime.strptime(parts, "%H:%M").time()
        else:
            return raw_str
        return time_obj.strftime("%I:%M %p")
    except Exception:
        return raw_str

# TIPS-G ALWAR Modern Neumorphism (Soft UI) Theme
MODERN_STYLE = """
/* ========================================================================== */
/* TIPS-G ALWAR - NEUMORPHIC (SOFT UI) DESIGN SYSTEM                          */
/* ========================================================================== */

QMainWindow {
    background-color: #e8edf5;
}

QWidget {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    color: #1e293b;
    font-size: 13px;
}

/* --- SIDEBAR NAVIGATION --- */
QFrame#Sidebar {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
    min-width: 250px;
    max-width: 250px;
}

QLabel#SidebarTitle {
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 1.5px;
    color: #ffffff;
    padding: 24px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    text-transform: uppercase;
    background-color: #0b1120;
}

QPushButton.SidebarBtn {
    background-color: transparent;
    border: none;
    color: #94a3b8;
    text-align: left;
    padding: 13px 18px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 10px;
    margin: 4px 12px;
}

QPushButton.SidebarBtn:hover {
    background-color: rgba(255, 255, 255, 0.07);
    color: #f8fafc;
}

QPushButton.SidebarBtn:checked {
    background: #1e293b;
    border-left: 4px solid #3b82f6;
    color: #60a5fa;
    font-weight: 700;
}

/* --- TOPBAR --- */
QFrame#Topbar {
    background-color: #e8edf5;
    border: 1.5px solid #ffffff;
    border-bottom: 2px solid #cbd5e1;
    border-right: 2px solid #cbd5e1;
    border-radius: 14px;
    margin: 14px 28px 6px 28px;
    min-height: 64px;
    max-height: 64px;
}

QLabel#PageTitle {
    font-size: 18px;
    font-weight: 800;
    color: #1e3a8a;
    letter-spacing: -0.3px;
}

/* --- NEUMORPHIC CARDS --- */
QFrame.Card, QFrame.NoticeCard, QFrame.ProfileCard {
    background-color: #e8edf5;
    border: 1.5px solid #ffffff;
    border-bottom: 2px solid #cbd5e1;
    border-right: 2px solid #cbd5e1;
    border-radius: 16px;
    padding: 20px;
}

QFrame.Card:hover, QFrame.NoticeCard:hover {
    background-color: #edf2f9;
    border: 1.5px solid #ffffff;
    border-bottom: 2px solid #b8c7dc;
    border-right: 2px solid #b8c7dc;
}

QLabel.CardValue {
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -1px;
    color: #1e3a8a;
}

QLabel.CardLabel {
    font-size: 11px;
    font-weight: 700;
    color: #3b82f6;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-top: 4px;
}

/* --- INSET DEBOSSED INPUTS --- */
QLineEdit, QComboBox, QTextEdit, QDateEdit {
    background-color: #dde4ee;
    border: 1px solid #c4d0e0;
    border-top: 2px solid #b2c2d6;
    border-left: 2px solid #b2c2d6;
    border-radius: 10px;
    padding: 10px 14px;
    color: #1e293b;
    selection-background-color: #3b82f6;
    font-size: 13px;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QDateEdit:focus {
    border: 2px solid #2563eb;
    background-color: #edf2f9;
}

QComboBox::drop-down {
    border: none;
    padding-right: 12px;
}

/* --- TACTILE BUTTONS --- */
QPushButton.PrimaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-bottom: 3px solid #1e40af;
    border-radius: 10px;
    padding: 11px 22px;
    font-weight: 700;
    font-size: 13px;
}

QPushButton.PrimaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
}

QPushButton.PrimaryBtn:pressed {
    border-top: 3px solid #1e3a8a;
    border-bottom: 1px solid #3b82f6;
    background-color: #1d4ed8;
}

QPushButton.SecondaryBtn {
    background-color: #e8edf5;
    color: #1e3a8a;
    border: 1px solid #ffffff;
    border-bottom: 2px solid #cbd5e1;
    border-right: 2px solid #cbd5e1;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton.SecondaryBtn:hover {
    background-color: #f1f5fa;
    color: #2563eb;
    border-color: #ffffff;
}

QPushButton.SecondaryBtn:pressed {
    border-top: 2px solid #b8c7dc;
    border-left: 2px solid #b8c7dc;
    border-bottom: 1px solid #ffffff;
    border-right: 1px solid #ffffff;
    background-color: #dde4ee;
}

QPushButton.DangerBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ef4444, stop:1 #dc2626);
    color: #ffffff;
    border: 1px solid #f87171;
    border-bottom: 2px solid #b91c1c;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 700;
    font-size: 12px;
}

QPushButton.DangerBtn:hover {
    background: #dc2626;
}

QPushButton.DangerBtn:pressed {
    border-top: 2px solid #991b1b;
    background: #b91c1c;
}

/* --- NEUMORPHIC TABLES --- */
QTableWidget {
    background-color: #ffffff;
    border: 1.5px solid #d9e2ec;
    gridline-color: #edf2f7;
    border-radius: 12px;
    outline: none;
    alternate-background-color: #f8fafc;
}

QTableWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #edf2f7;
    color: #1e293b;
}

QTableWidget::item:selected {
    background-color: #dbeafe;
    color: #1e3a8a;
    font-weight: 600;
}

QTableWidget::alternate-item {
    background-color: #f8fafc;
}

QHeaderView::section {
    background-color: #1e3a8a;
    color: #ffffff;
    padding: 12px 10px;
    border: none;
    font-weight: 700;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
}

/* --- LOGIN & DIALOG CARDS --- */
QFrame#LoginCard {
    background-color: #e8edf5;
    border: 2px solid #ffffff;
    border-bottom: 3px solid #cbd5e1;
    border-right: 3px solid #cbd5e1;
    border-radius: 20px;
    padding: 40px;
}

QDialog {
    background-color: #e8edf5;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

/* --- NOTICEBOARD & BADGES --- */
QLabel.NoticeTitle {
    font-size: 16px;
    font-weight: 700;
    color: #1e3a8a;
}

QLabel.NoticeDate {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
}

QLabel.NoticeDescription {
    font-size: 13px;
    color: #334155;
    line-height: 20px;
}

QLabel.VerifiedBadge {
    background-color: #ecfdf5;
    color: #047857;
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 4px 10px;
    font-weight: 700;
    font-size: 11px;
}
"""

class CameraThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self._run_flag = True

    def run(self):
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if sys.platform.startswith('win') else cv2.VideoCapture(0)
        while self._run_flag:
            ret, cv_img = cap.read()
            if ret:
                self.change_pixmap_signal.emit(cv_img)
            self.msleep(30)
        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()

def capture_registration_photo(parent: QWidget) -> bytes:
    """Capture one high-quality registration photo from the camera using Space with live box outline."""
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(0)
    if not camera.isOpened():
        QMessageBox.warning(parent, "Camera unavailable", "Could not open the current camera.")
        return b""

    window_name = "Capture Profile Photo - Press [SPACE] to capture | [ESC] to cancel"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 720, 540)
    captured_bytes = b""

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                QMessageBox.warning(parent, "Camera error", "Could not read an image from the camera.")
                break

            preview = frame.copy()
            h, w, _ = preview.shape
            cy, cx = h // 2, w // 2
            bx, by, bw, bh = cx - 110, cy - 140, 220, 280

            # Navy Blue tracking box (in BGR: (138, 58, 30))
            cv2.rectangle(preview, (bx, by), (bx + bw, by + bh), (138, 58, 30), 2)

            # Corner accents
            corner_len = 22
            corner_color = (176, 104, 66)
            # Top-Left
            cv2.line(preview, (bx, by), (bx + corner_len, by), corner_color, 3)
            cv2.line(preview, (bx, by), (bx, by + corner_len), corner_color, 3)
            # Top-Right
            cv2.line(preview, (bx + bw, by), (bx + bw - corner_len, by), corner_color, 3)
            cv2.line(preview, (bx + bw, by), (bx + bw, by + corner_len), corner_color, 3)
            # Bottom-Left
            cv2.line(preview, (bx, by + bh), (bx + corner_len, by + bh), corner_color, 3)
            cv2.line(preview, (bx, by + bh), (bx, by + bh - corner_len), corner_color, 3)
            # Bottom-Right
            cv2.line(preview, (bx + bw, by + bh), (bx + bw - corner_len, by + bh), corner_color, 3)
            cv2.line(preview, (bx + bw, by + bh), (bx + bw, by + bh - corner_len), corner_color, 3)

            # Modern HUD bottom instruction bar
            overlay = preview.copy()
            cv2.rectangle(overlay, (0, h - 46), (w, h), (15, 23, 42), -1)
            cv2.addWeighted(overlay, 0.8, preview, 0.2, 0, preview)

            cv2.putText(
                preview,
                "Align Face Inside Box  |  [SPACE] Capture Photo  |  [ESC] Cancel",
                (w // 2 - 250, h - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

            cv2.imshow(window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # SPACE key
                ret, buf = cv2.imencode('.jpg', frame)
                if ret:
                    captured_bytes = buf.tobytes()
                else:
                    QMessageBox.warning(parent, "Capture failed", "Could not encode the camera photo.")
                break
            elif key == 27:  # ESC key
                break
    finally:
        camera.release()
        cv2.destroyWindow(window_name)

    return captured_bytes

class LoginWindow(QWidget):
    login_success = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TIPS-G ALWAR - Student Attendance System")
        self.resize(520, 680)
        self.setMinimumSize(480, 620)
        icon_manager.apply_to_window(self)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

        card = QFrame()
        card.setObjectName("LoginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        logo = QLabel(
            "<div style='text-align: center; line-height: 125%;'>"
            "<span style='font-size: 26px; font-weight: 800; color: #1e3a8a; letter-spacing: -0.5px;'>TIPS-G ALWAR</span><br>"
            "<span style='font-size: 20px; font-weight: 700; color: #2563eb;'>AI Attendance System</span>"
            "</div>"
        )
        logo.setStyleSheet("margin-bottom: 12px; padding: 4px 0;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(logo)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username / Registration ID")
        self.username_input.setMinimumWidth(320)
        self.username_input.setMinimumHeight(42)
        
        lbl_user = QLabel("Username / Registration ID")
        lbl_user.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        card_layout.addWidget(lbl_user)
        card_layout.addWidget(self.username_input)

        lbl_pwd = QLabel("Password")
        lbl_pwd.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        card_layout.addWidget(lbl_pwd)

        pwd_container = QWidget()
        pwd_layout = QHBoxLayout(pwd_container)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(6)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(42)

        self.toggle_pwd_btn = QPushButton("👁️")
        self.toggle_pwd_btn.setMinimumSize(42, 42)
        self.toggle_pwd_btn.setMaximumSize(42, 42)
        self.toggle_pwd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_pwd_btn.setToolTip("Show / Hide Password")
        self.toggle_pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
            }
        """)
        self.toggle_pwd_btn.clicked.connect(self.toggle_password_visibility)

        pwd_layout.addWidget(self.password_input)
        pwd_layout.addWidget(self.toggle_pwd_btn)
        card_layout.addWidget(pwd_container)

        self.login_btn = QPushButton("Log In to Dashboard")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setObjectName("LoginButton")
        self.login_btn.setProperty("class", "PrimaryBtn")
        self.login_btn.setStyleSheet("QPushButton.PrimaryBtn { font-size: 14px; padding: 14px; }")
        self.login_btn.clicked.connect(self.handle_login)
        card_layout.addWidget(self.login_btn)

        self.register_btn = QPushButton("Create Student Account")
        self.register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_btn.setObjectName("RegisterButton")
        self.register_btn.setStyleSheet("background-color: #f0f4ff; color: #1e3a8a; border: 1px solid #cbd5e1; font-weight: 700; padding: 12px; border-radius: 8px; font-size: 13px;")
        self.register_btn.clicked.connect(self.open_register_student_dialog)
        card_layout.addWidget(self.register_btn)

        self.forgot_pwd_btn = QPushButton("Forgot Password?")
        self.forgot_pwd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forgot_pwd_btn.setStyleSheet("background-color: transparent; color: #3b82f6; font-weight: 600; text-decoration: underline;")
        self.forgot_pwd_btn.clicked.connect(self.handle_forgot_password)
        card_layout.addWidget(self.forgot_pwd_btn)

        # Standalone Desktop Shortcut Creator Link
        self.shortcut_btn = QPushButton("📌 Place TIPS-G Shortcut on Desktop")
        self.shortcut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shortcut_btn.setToolTip("Create a desktop shortcut with official TIPS-G icon")
        self.shortcut_btn.setStyleSheet("background-color: transparent; color: #64748b; font-size: 11px; font-weight: 600; text-decoration: underline; padding: 4px;")
        self.shortcut_btn.clicked.connect(self.handle_create_shortcut)
        card_layout.addWidget(self.shortcut_btn)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #dc2626; font-weight: bold;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.error_label)

        layout.addWidget(card)

    def handle_create_shortcut(self):
        success, msg, paths = icon_manager.create_desktop_shortcut()
        if success:
            QMessageBox.information(
                self,
                "Desktop Shortcut Created",
                f"✅ TIPS-G Attendance System shortcut created!\n\n"
                f"Location:\n{paths[0] if paths else 'Desktop'}\n\n"
                f"You can now launch the application directly from your Desktop with the TIPS-G icon."
            )
        else:
            QMessageBox.warning(
                self,
                "Shortcut Status",
                f"Could not create desktop shortcut:\n{msg}"
            )


    def toggle_password_visibility(self):
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_pwd_btn.setText("🙈")
            self.toggle_pwd_btn.setToolTip("Hide Password")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_pwd_btn.setText("👁️")
            self.toggle_pwd_btn.setToolTip("Show Password")

    def handle_login(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text()
        
        if not user or not pwd:
            self.error_label.setText("Please fill in all fields.")
            return

        # --- Loading indicator ---
        self.login_btn.setText("⏳  Verifying credentials...")
        self.login_btn.setEnabled(False)
        self.register_btn.setEnabled(False)
        self.forgot_pwd_btn.setEnabled(False)
        self.error_label.setText("")
        QApplication.processEvents()

        res = api_client.login(user, pwd)

        # Restore button
        self.login_btn.setText("Log In to Dashboard")
        self.login_btn.setEnabled(True)
        self.register_btn.setEnabled(True)
        self.forgot_pwd_btn.setEnabled(True)

        if res["status"] == "success":
            self.login_success.emit(res["user"])
        else:
            self.error_label.setText(res.get("error", "Login validation failed."))

    def handle_forgot_password(self):
        # ── Step 1: get username ──────────────────────────────────────────────
        username, ok = QInputDialog.getText(
            self, "Forgot Password – Step 1",
            "Enter your Username or Registration ID:"
        )
        if not ok or not username.strip():
            return

        # ── Step 2: request OTP (retry sending if needed) ────────────────────
        def _request_otp() -> bool:
            """Send OTP. Returns True on success, False on failure."""
            try:
                api_client.request_password_reset(username.strip())
                return True
            except Exception as exc:
                logger.error(f"OTP request failed: {exc}")
                return False

        if not _request_otp():
            QMessageBox.critical(
                self, "Could Not Send OTP",
                "We could not send an OTP to this account.\n"
                "Please check your username and try again later."
            )
            return

        QMessageBox.information(
            self, "OTP Sent",
            "A 6-digit OTP has been sent to your registered email address."
        )

        # ── Step 3: verify OTP (loop with retry / resend options) ────────────
        while True:
            otp, ok_otp = QInputDialog.getText(
                self, "Forgot Password – Step 2",
                "Enter the 6-digit OTP sent to your email:",
                QLineEdit.EchoMode.Normal
            )
            if not ok_otp:
                return  # User cancelled the whole flow

            if not otp.strip():
                continue  # Empty input — re-prompt

            # Probe the OTP without a real password first by using a dummy
            # verify call.  We pass a placeholder new_password; the backend
            # will reject an invalid OTP before it ever touches the password.
            try:
                # We don't have the new password yet, so we just check the OTP
                # by calling the endpoint.  A wrong OTP raises an exception
                # before anything is changed in the DB.
                api_client.verify_otp_only(username.strip(), otp.strip())
                # OTP accepted — break out to collect the new password
                break
            except Exception as exc:
                logger.error(f"OTP check failed: {exc}")

                # ── show friendly dialog — never expose the raw HTTP error ──
                choice = QMessageBox.warning(
                    self,
                    "Incorrect OTP",
                    "The OTP you entered is incorrect or has expired.",
                    QMessageBox.StandardButton.Retry
                    | QMessageBox.StandardButton.Reset
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Retry
                )

                if choice == QMessageBox.StandardButton.Retry:
                    # Re-enter the same OTP
                    continue
                elif choice == QMessageBox.StandardButton.Reset:
                    # Send a brand-new OTP and restart the verify loop
                    if _request_otp():
                        QMessageBox.information(
                            self, "New OTP Sent",
                            "A new OTP has been sent to your registered email."
                        )
                        continue
                    else:
                        QMessageBox.critical(
                            self, "Could Not Resend OTP",
                            "Failed to send a new OTP. Please try again later."
                        )
                        return
                else:
                    return  # User cancelled

        # ── Step 4: collect new password (only reached after valid OTP) ──────
        new_password, ok_pwd = QInputDialog.getText(
            self, "Forgot Password – Step 3",
            "Enter your new password:",
            QLineEdit.EchoMode.Password
        )
        if not ok_pwd or not new_password.strip():
            return

        if len(new_password.strip()) < 6:
            QMessageBox.warning(
                self, "Password Too Short",
                "Your new password must be at least 6 characters long."
            )
            return

        confirm_password, ok_confirm = QInputDialog.getText(
            self, "Forgot Password – Step 4",
            "Confirm your new password:",
            QLineEdit.EchoMode.Password
        )
        if not ok_confirm:
            return
        if confirm_password != new_password:
            QMessageBox.warning(self, "Password Mismatch", "The passwords do not match.")
            return

        # ── Step 5: final reset with the verified OTP + new password ─────────
        try:
            res = api_client.verify_password_reset(
                username.strip(), otp.strip(), new_password.strip()
            )
            logger.info(f"Password reset response: {res}")
            QMessageBox.information(
                self, "Password Reset Successful",
                "Your password has been reset successfully.\nYou can now log in with your new password."
            )
        except Exception as exc:
            logger.error(f"Final password reset failed: {exc}")
            # Even here, don't expose the raw error — it should only fail for
            # race-condition/server reasons at this point (OTP was valid).
            QMessageBox.critical(
                self, "Reset Failed",
                "Something went wrong while saving your new password.\n"
                "Please restart the process or contact the administrator."
            )

    def open_register_student_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Register New Student")
        dialog.setMinimumWidth(440)
        form_layout = QFormLayout(dialog)
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(20)

        reg_input = QLineEdit()
        reg_input.setPlaceholderText("Choose a username")
        username_layout = QHBoxLayout()
        username_layout.setContentsMargins(0, 0, 0, 0)
        username_suffix = QLabel("-tipsg")
        username_suffix.setStyleSheet("font-weight:700; color:#1e3a8a; padding: 0 8px;")
        username_layout.addWidget(reg_input)
        username_layout.addWidget(username_suffix)
        name_input = QLineEdit()
        course_combo = QComboBox()
        course_combo.addItems(["Data Science", "Cyber security", "AI/ML Engineer", "Software Developer", "Digital Market"])
        parent_name_input = QLineEdit()
        parent_phone_input = QLineEdit()
        
        # Student Email with OTP Verification
        student_email_input = QLineEdit()
        student_email_input.setPlaceholderText("student@gmail.com")
        verify_email_btn = QPushButton("Verify Gmail")
        verify_email_btn.setProperty("class", "SecondaryBtn")
        verify_email_btn.setStyleSheet("padding: 6px 12px; font-weight: 600;")
        verify_email_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        student_email_layout = QHBoxLayout()
        student_email_layout.setContentsMargins(0, 0, 0, 0)
        student_email_layout.addWidget(student_email_input)
        student_email_layout.addWidget(verify_email_btn)

        email_verified = False
        verified_email_address = ""

        def handle_verify_email():
            nonlocal email_verified, verified_email_address
            em = student_email_input.text().strip()
            uname = reg_input.text().strip()
            if not em or "@" not in em:
                QMessageBox.warning(dialog, "Invalid Email", "Please enter a valid Gmail address.")
                return
            if not uname:
                QMessageBox.warning(dialog, "Username Required", "Please enter your chosen username before verifying your Gmail.")
                return
            
            verify_email_btn.setEnabled(False)
            verify_email_btn.setText("Sending OTP...")
            QApplication.processEvents()

            try:
                api_client.send_email_verification_otp(
                    email=em,
                    username=f"{uname}-tipsg",
                    full_name=name_input.text().strip()
                )
                verify_email_btn.setText("Enter OTP")
                verify_email_btn.setEnabled(True)

                otp, ok = QInputDialog.getText(
                    dialog,
                    "Gmail OTP Verification",
                    f"A 6-digit OTP has been sent to:\n{em}\n\nEnter the OTP code below:"
                )
                if ok and otp.strip():
                    res = api_client.verify_email_otp(
                        email=em,
                        otp=otp.strip(),
                        username=f"{uname}-tipsg"
                    )
                    if res.get("verified"):
                        email_verified = True
                        verified_email_address = em
                        verify_email_btn.setText("✓ Verified")
                        verify_email_btn.setEnabled(False)
                        verify_email_btn.setStyleSheet("background-color: #16a34a; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 6px 12px;")
                        student_email_input.setReadOnly(True)
                        QMessageBox.information(dialog, "Verified", "Gmail address successfully verified!")
                else:
                    verify_email_btn.setText("Verify Gmail")
                    verify_email_btn.setEnabled(True)
            except Exception as err:
                verify_email_btn.setText("Verify Gmail")
                verify_email_btn.setEnabled(True)
                QMessageBox.critical(dialog, "Verification Failed", f"Could not verify Gmail: {err}")

        verify_email_btn.clicked.connect(handle_verify_email)

        def on_email_text_changed():
            nonlocal email_verified, verified_email_address
            if student_email_input.text().strip() != verified_email_address:
                email_verified = False
                verify_email_btn.setText("Verify Gmail")
                verify_email_btn.setEnabled(True)
                verify_email_btn.setStyleSheet("padding: 6px 12px; font-weight: 600;")
                student_email_input.setReadOnly(False)

        student_email_input.textChanged.connect(on_email_text_changed)

        parent_email_input = QLineEdit()
        parent_email_input.setPlaceholderText("parent@example.com")
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_password_input = QLineEdit()
        confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        photo_layout = QHBoxLayout()
        photo_label = QLineEdit()
        photo_label.setReadOnly(True)
        photo_label.setPlaceholderText("Select Profile Image or capture live")
        captured_photo_bytes = None
        photo_btn = QPushButton("Browse")
        photo_btn.setProperty("class", "SecondaryBtn")
        photo_btn.setStyleSheet("QPushButton.SecondaryBtn { padding: 8px 14px; }")
        photo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        def choose_photo():
            nonlocal captured_photo_bytes
            file_path, _ = QFileDialog.getOpenFileName(dialog, "Select Profile Image", "", "Image Files (*.jpg *.jpeg *.png)")
            if file_path:
                captured_photo_bytes = None
                photo_label.setText(file_path)
        capture_btn = QPushButton("Take Photo")
        capture_btn.setProperty("class", "SecondaryBtn")
        capture_btn.setStyleSheet("QPushButton.SecondaryBtn { padding: 8px 14px; }")
        capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def take_photo():
            nonlocal captured_photo_bytes
            cb = capture_registration_photo(dialog)
            if cb:
                captured_photo_bytes = cb
                photo_label.setText("✓ Photo captured successfully")

        photo_btn.clicked.connect(choose_photo)
        capture_btn.clicked.connect(take_photo)
        photo_layout.addWidget(photo_label)
        photo_layout.addWidget(photo_btn)
        photo_layout.addWidget(capture_btn)

        form_layout.addRow("Student Username:", username_layout)
        form_layout.addRow("Full Name:", name_input)
        form_layout.addRow("Course:", course_combo)
        form_layout.addRow("Parent Name:", parent_name_input)
        form_layout.addRow("Parent Phone:", parent_phone_input)
        form_layout.addRow("Student Email:", student_email_layout)
        form_layout.addRow("Parent Email:", parent_email_input)
        form_layout.addRow("Password:", password_input)
        form_layout.addRow("Confirm Password:", confirm_password_input)
        form_layout.addRow("Face Image Photo:", photo_layout)

        submit_btn = QPushButton("Complete Registration")
        submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        submit_btn.setProperty("class", "PrimaryBtn")
        submit_btn.setStyleSheet("QPushButton.PrimaryBtn")

        def handle_submit():
            if not all([reg_input.text(), name_input.text(), parent_name_input.text(), parent_phone_input.text(), student_email_input.text(), parent_email_input.text(), password_input.text(), confirm_password_input.text(), photo_label.text()]):
                QMessageBox.warning(dialog, "Warning", "Please fill all required fields (including both emails) and select a profile photo.")
                return
            if not email_verified or student_email_input.text().strip() != verified_email_address:
                reply = QMessageBox.question(
                    dialog,
                    "Verify Gmail",
                    "Please verify your Gmail address with OTP before submitting registration. Would you like to verify it now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    handle_verify_email()
                    if not email_verified:
                        return
                else:
                    return
            if password_input.text() != confirm_password_input.text():
                QMessageBox.warning(dialog, "Warning", "Passwords do not match.")
                return
            if len(password_input.text()) < 6:
                QMessageBox.warning(dialog, "Warning", "Password must be at least 6 characters.")
                return


            submit_btn.setEnabled(False)
            submit_btn.setText("Extracting Framework Embeddings...")
            QApplication.processEvents()

            try:
                from frontend.onnx_face_service import onnx_face_service
                import json
                import math
                
                # Extract single sharp frontal embedding
                if captured_photo_bytes:
                    embedding_vector = onnx_face_service.extract_embedding(captured_photo_bytes)
                else:
                    embedding_vector = onnx_face_service.extract_embedding(photo_label.text())
                embedding_json = json.dumps(embedding_vector)

                # Anti-Duplicate Face Security Guard (Client & DB)
                try:
                    from src.database.connection import SessionLocal
                    from src.database.models import Student, FaceEmbedding
                    db_session = SessionLocal()
                    active_students = db_session.query(Student).filter(Student.is_active == True).all()
                    cand_norm = math.sqrt(sum(v * v for v in embedding_vector))
                    is_duplicate = False
                    matched_student_name = ""
                    matched_student_reg = ""
                    for st in active_students:
                        stored_rec = db_session.query(FaceEmbedding).filter(FaceEmbedding.student_id == st.id).first()
                        if not stored_rec or not stored_rec.embedding:
                            continue
                        stored_vec = stored_rec.embedding
                        if isinstance(stored_vec, str):
                            stored_vec = json.loads(stored_vec)
                        st_norm = math.sqrt(sum(v * v for v in stored_vec))
                        if st_norm > 0 and cand_norm > 0 and len(stored_vec) == len(embedding_vector):
                            sim = sum(a * b for a, b in zip(embedding_vector, stored_vec)) / (cand_norm * st_norm)
                            dist = max(0.0, min(2.0, 1.0 - sim))
                            if dist <= 0.49:
                                is_duplicate = True
                                matched_student_name = st.full_name
                                matched_student_reg = st.registration_number
                                break
                    db_session.close()
                    if is_duplicate:
                        QMessageBox.warning(
                            dialog,
                            "Duplicate Face Detected",
                            f"❌ Registration Blocked:\n\nThis face is already registered to student:\n'{matched_student_name}' ({matched_student_reg})\n\nEach student must register with their own unique face."
                        )
                        submit_btn.setEnabled(True)
                        submit_btn.setText("Complete Registration")
                        return
                except Exception as dup_err:
                    logger.debug(f"Anti-duplicate check skipped: {dup_err}")

            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed local face feature extraction: {e}")
                submit_btn.setEnabled(True)
                submit_btn.setText("Complete Registration")
                return

            data = {
                "registration_number": reg_input.text().strip(),
                "full_name": name_input.text().strip(),
                "class_name": course_combo.currentText(),
                "parent_name": parent_name_input.text().strip(),
                "parent_phone": parent_phone_input.text().strip(),
                "email": student_email_input.text().strip(),
                "parent_email": parent_email_input.text().strip(),
                "password": password_input.text().strip(),
                "embedding": embedding_json
            }
            photo_path = photo_label.text() if captured_photo_bytes is None else None
            try:
                result = api_client.register_student(data, photo_path=photo_path)
                QMessageBox.information(dialog, "Success", f"Student registered as: {result['registration_number']}")
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to register student architecture: {e}")
                submit_btn.setEnabled(True)
                submit_btn.setText("Complete Registration")

        submit_btn.clicked.connect(handle_submit)
        form_layout.addRow(submit_btn)
        dialog.exec()

class NotificationSocketWorker(QThread):
    notification_received = pyqtSignal(dict)

    def __init__(self, token: str, base_url: str):
        super().__init__()
        self.token = token
        self.base_url = base_url
        self._running = True
        self._socket = None

    def run(self):
        websocket_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        websocket_url = f"{websocket_url}/notifications/ws?token={self.token}"
        while self._running:
            try:
                self._socket = websocket.create_connection(websocket_url, timeout=30)
                while self._running:
                    payload = self._socket.recv()
                    if payload:
                        import json
                        self.notification_received.emit(json.loads(payload))
            except Exception as error:
                err_str = str(error)
                if "401" in err_str or "403" in err_str or "Handshake status 403" in err_str:
                    logger.debug(f"Live notification connection ended (session closed: {error})")
                    self._running = False
                    break
                if self._running:
                    logger.debug(f"Live notification connection reconnecting: {error}")
                    self.msleep(5000)
            finally:
                if self._socket:
                    try:
                        self._socket.close()
                    except Exception:
                        pass
                    self._socket = None

    def stop(self):
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        self.wait(2000)

class PageDataLoader(QThread):
    data_loaded = pyqtSignal(int, object)
    error = pyqtSignal(int, str)

    def __init__(self, page_index: int, user_info: dict = None):
        super().__init__()
        self.page_index = page_index
        self.user_info = user_info or api_client.user_info or {}
        self.user_role = str(self.user_info.get("role", "student")).lower()

    def run(self):
        try:
            if self.page_index == 0:
                summary = api_client.get_summary()
                records = api_client.get_daily_attendance()
                if not summary or not records:
                    try:
                        from src.database.connection import SessionLocal
                        from src.database.models import Student, Attendance
                        from datetime import date
                        db = SessionLocal()
                        today = date.today()
                        total_students = db.query(Student).filter(Student.is_active == True).count()
                        
                        if self.user_role == "student" and self.user_info.get("id"):
                            student_id = self.user_info["id"]
                            daily_recs = db.query(Attendance).filter(Attendance.date == today, Attendance.student_id == student_id).all()
                        else:
                            daily_recs = db.query(Attendance).filter(Attendance.date == today).all()
                        
                        if not records and daily_recs:
                            records = []
                            for r in daily_recs:
                                st = r.student
                                records.append({
                                    "id": r.id,
                                    "student_id": r.student_id,
                                    "student_name": st.full_name if st else "Unknown",
                                    "registration_number": st.registration_number if st else "Unknown",
                                    "date": str(r.date),
                                    "check_in": str(r.check_in) if r.check_in else None,
                                    "check_out": str(r.check_out) if r.check_out else None,
                                    "status": r.status,
                                    "confidence_score": r.confidence_score,
                                    "verification_method": r.verification_method
                                })

                        if not summary:
                            all_today = db.query(Attendance).filter(Attendance.date == today).all()
                            present = sum(1 for r in all_today if r.status and r.status.lower() == "present")
                            absent = sum(1 for r in all_today if r.status and r.status.lower() == "absent")
                            late = sum(1 for r in all_today if r.status and r.status.lower() == "late")
                            leave = sum(1 for r in all_today if r.status and r.status.lower() == "leave")
                            holiday = sum(1 for r in all_today if r.status and r.status.lower() == "holiday")
                            summary = {
                                "total_students": total_students,
                                "present": present,
                                "absent": max(0, total_students - present - late - leave - holiday),
                                "late": late,
                                "leave": leave,
                                "holiday": holiday
                            }
                        db.close()
                    except Exception as db_err:
                        logger.debug(f"Direct DB summary calculation: {db_err}")
                self.data_loaded.emit(self.page_index, {"summary": summary or {}, "records": records or []})
            elif self.page_index == 2:
                holidays = api_client.get_noticeboard_holidays()
                self.data_loaded.emit(self.page_index, {"holidays": holidays})
            elif self.page_index == 3:
                students = api_client.get_students()
                self.data_loaded.emit(self.page_index, {"students": students})
            elif self.page_index == 4:
                leaves = api_client.get_pending_leaves()
                self.data_loaded.emit(self.page_index, {"leaves": leaves})
            elif self.page_index == 5:
                holidays = api_client.get_holidays()
                self.data_loaded.emit(self.page_index, {"holidays": holidays})
            elif self.page_index == 6:
                archives = api_client.get_monthly_report_archives()
                self.data_loaded.emit(self.page_index, {"archives": archives})
            elif self.page_index == 7:
                profile = {}
                role = str(self.user_role).lower()
                user_id = self.user_info.get("id")
                username = self.user_info.get("username") or self.user_info.get("registration_number", "")

                # Fast direct DB lookup by Student ID or Username (50ms)
                try:
                    from src.database.connection import SessionLocal
                    from src.database.models import Student, Teacher, Admin
                    db = SessionLocal()
                    if role == "student":
                        s = None
                        if user_id:
                            s = db.query(Student).filter(Student.id == user_id).first()
                        if not s and username:
                            s = db.query(Student).filter(Student.registration_number == username).first()
                            if not s and username.endswith("-tipsg"):
                                s = db.query(Student).filter(Student.registration_number == username[:-6]).first()
                            if not s and not username.endswith("-tipsg"):
                                s = db.query(Student).filter(Student.registration_number == f"{username}-tipsg").first()
                        if s:
                            profile = {
                                "id": s.id,
                                "registration_number": s.registration_number,
                                "full_name": s.full_name,
                                "email": s.email or "—",
                                "phone": s.phone or "—",
                                "parent_name": s.parent_name or "—",
                                "parent_phone": s.parent_phone or "—",
                                "parent_email": s.parent_email or "—",
                                "class_name": s.class_name or "—",
                                "photo_path": s.photo_path,
                            }
                    elif role in ["teacher", "manager", "hr"]:
                        t = None
                        if user_id:
                            t = db.query(Teacher).filter(Teacher.id == user_id).first()
                        if not t and username:
                            t = db.query(Teacher).filter(Teacher.username == username).first()
                        if t:
                            profile = {
                                "id": t.id,
                                "username": t.username,
                                "full_name": t.full_name,
                                "email": t.email or "—",
                                "phone": t.phone or "—",
                                "department": t.department or "—",
                                "role": t.role,
                            }
                    else:
                        a = None
                        if user_id:
                            a = db.query(Admin).filter(Admin.id == user_id).first()
                        if not a and username:
                            a = db.query(Admin).filter(Admin.username == username).first()
                        if a:
                            profile = {
                                "id": a.id,
                                "username": a.username,
                                "full_name": a.full_name,
                                "email": a.email or "—",
                                "role": "admin",
                            }
                    db.close()
                except Exception as db_err:
                    logger.warning(f"Database direct profile lookup: {db_err}")

                # Secondary API fallback if direct DB lookup produced no record
                if not profile and role == "student":
                    try:
                        profile = api_client.get_my_profile()
                    except Exception as e:
                        logger.debug(f"Profile API query fallback ({e})")

                if not profile:
                    profile = self.user_info
                self.data_loaded.emit(self.page_index, {"profile": profile})
        except Exception as exc:
            self.error.emit(self.page_index, str(exc))

class MainWindow(QMainWindow):
    def __init__(self, user_info: dict):
        super().__init__()
        self.user_info = user_info
        self.setWindowTitle("TIPS-G ALWAR - Student Attendance AI System")
        self.resize(1366, 868)
        self.setMinimumSize(1150, 720)
        self.camera_thread = None
        self.last_frame_bytes = None
        self.notification_socket = None
        
        # Apply TIPS-G ALWAR icon
        icon_manager.apply_to_window(self)
        
        logger.info(f"MainWindow initialized for: {user_info.get('full_name')}")
        
        # 🚀 Launch non-blocking background AI facial model warmup
        self.warmup_worker = AsyncModelWarmupWorker()
        self.warmup_worker.start()
        
        # Biometric HUD overlay & In-app toast notification engine
        self.biometric_hud = BiometricScanOverlay()
        self.toast = NotificationToast(self)
        
        self.my_embedding = None
        if self.user_info.get("role") == "student":
            try:
                res = api_client.get_my_embedding()
                self.my_embedding = res.get("embedding") if isinstance(res, dict) else None
                if not self.my_embedding and self.user_info.get("id"):
                    try:
                        from src.database.connection import SessionLocal
                        from src.database.models import FaceEmbedding
                        import json
                        db = SessionLocal()
                        emb_rec = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == self.user_info["id"]).first()
                        if emb_rec and emb_rec.embedding:
                            raw_emb = emb_rec.embedding
                            if isinstance(raw_emb, str):
                                self.my_embedding = json.loads(raw_emb)
                            elif isinstance(raw_emb, list):
                                self.my_embedding = raw_emb
                        db.close()
                    except Exception as db_err:
                        logger.debug(f"Direct DB embedding fallback: {db_err}")
                if self.my_embedding:
                    logger.info("Successfully fetched student face embedding for local verification.")
                else:
                    logger.info("No face embedding registered yet for this student.")
            except Exception as e:
                logger.debug(f"Fetch face embedding fallback: {e}")
                self.my_embedding = None
        
        self.init_ui()
        self.init_system_tray()
        self.start_notification_socket()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh_dashboard)
        self.refresh_timer.start(10000)

    def init_system_tray(self):
        """Initializes the Windows system tray icon for background toast notifications."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return
        self.tray_icon = QSystemTrayIcon(self)
        try:
            icon = self.windowIcon()
            if icon and not icon.isNull():
                self.tray_icon.setIcon(icon)
            else:
                self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        except Exception:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("TIPS-G ALWAR Attendance System")
        self.tray_icon.show()

    def update_leave_badge(self, pending_count: int):
        """Updates the Leave Approvals sidebar button with a sleek compact badge and pending count."""
        if not hasattr(self, "leaves_nav_btn") or not self.leaves_nav_btn:
            return
        base_text = getattr(self, "leaves_base_text", "Leave Approvals")
        if self.user_info.get("role") != "student":
            if pending_count > 0:
                self.leaves_nav_btn.setText(f"{base_text}  • ({pending_count})")
            else:
                self.leaves_nav_btn.setText(base_text)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 🌌 Ambient soft animated background waves
        self.ambient_bg = AmbientWaveBackground(central_widget)
        self.ambient_bg.lower()

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Nav Shell
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(2)

        title = QLabel("TIPS-G Core AI")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title)

        self.nav_group = []
        role = self.user_info.get("role", "student")
        nav_items = [
            ("Dashboard", 0),
            ("Face Attendance", 1),
            ("Notice Board", 2),
        ]
        
        if role == "student":
            nav_items.append(("My Profile", 7))
        else:
            nav_items.append(("Student Directory", 3))
            nav_items.append(("Monthly Reports", 6))
            nav_items.append(("System Overrides", 7))
            if role in ["admin", "hr"]:
                nav_items.append(("Holidays Schedule", 5))

        leaves_btn_text = "Leave Applications" if role == "student" else "Leave Approvals"
        self.leaves_base_text = leaves_btn_text
        nav_items.append((leaves_btn_text, 4))

        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setObjectName(f"NavBtn_{text.replace(' ', '')}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("index", index)
            btn.clicked.connect(self.change_page)
            btn.setMinimumHeight(48)
            btn.setProperty("class", "SidebarBtn")
            btn.setStyleSheet("QPushButton.SidebarBtn")
            if index == 4:
                self.leaves_nav_btn = btn
            sidebar_layout.addWidget(btn)
            self.nav_group.append(btn)

        self.nav_group[0].setChecked(True)
        sidebar_layout.addStretch()

        sidebar_actions_box = QVBoxLayout()
        sidebar_actions_box.setContentsMargins(12, 10, 12, 16)
        sidebar_actions_box.setSpacing(8)

        style = self.style()

        # Refresh System Button (QStyle Standard Icon)
        refresh_btn = QPushButton(" Refresh System")
        refresh_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        refresh_btn.setIconSize(QSize(18, 18))
        refresh_btn.setMinimumHeight(40)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setToolTip("Reload fresh data for all pages and tables from backend")
        refresh_btn.setStyleSheet("""
            QPushButton {
                color: #e2e8f0; 
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                padding: 0 10px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.25);
                color: #ffffff;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_all_pages)
        sidebar_actions_box.addWidget(refresh_btn)

        # Create Desktop Shortcut Button
        shortcut_btn = QPushButton(" Desktop Shortcut")
        shortcut_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
        shortcut_btn.setIconSize(QSize(18, 18))
        shortcut_btn.setMinimumHeight(40)
        shortcut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        shortcut_btn.setToolTip("Place a TIPS-G launcher shortcut with official icon on your Desktop")
        shortcut_btn.setStyleSheet("""
            QPushButton {
                color: #e2e8f0; 
                background-color: rgba(59, 130, 246, 0.16);
                border: 1px solid rgba(59, 130, 246, 0.35);
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                padding: 0 10px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(59, 130, 246, 0.35);
                color: #ffffff;
            }
        """)
        shortcut_btn.clicked.connect(self.handle_create_desktop_shortcut)
        sidebar_actions_box.addWidget(shortcut_btn)

        # Sign Out Button
        logout_btn = QPushButton(" Sign Out")
        logout_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        logout_btn.setIconSize(QSize(18, 18))
        logout_btn.setMinimumHeight(40)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet("""
            QPushButton {
                color: #fca5a5; 
                background-color: rgba(239, 68, 68, 0.14);
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 8px;
                font-weight: 700;
                font-size: 12px;
                padding: 0 10px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
                border: 1px solid #dc2626;
            }
        """)
        logout_btn.clicked.connect(self.handle_logout)
        sidebar_actions_box.addWidget(logout_btn)

        sidebar_layout.addLayout(sidebar_actions_box)

        main_layout.addWidget(sidebar)

        # 2. Workspace Viewports
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("Topbar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(20, 10, 20, 10)

        self.page_title = QLabel("Dashboard Platform Matrix")
        self.page_title.setObjectName("PageTitle")
        topbar_layout.addWidget(self.page_title)
        topbar_layout.addStretch()

        self.notification_button = QPushButton("Notifications")
        self.notification_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notification_button.setStyleSheet("background-color: #fef3c7; color: #92400e; border: 1px solid #f59e0b; padding: 8px 12px; border-radius: 8px; font-weight: 700;")
        self.notification_button.clicked.connect(self.show_notifications)
        topbar_layout.addWidget(self.notification_button)

        user_label = QLabel(f"Logged In: {self.user_info['full_name']} [{self.user_info['role'].upper()}]")
        user_label.setStyleSheet("color: #ffffff; font-weight: 700; font-size: 12px; background-color: #3b82f6; padding: 8px 14px; border-radius: 8px; border: 1px solid #2563eb;")
        topbar_layout.addWidget(user_label)

        content_layout.addWidget(topbar)

        # 🎬 Hardware-accelerated AnimatedStackedWidget with smooth 60 FPS transitions
        self.stacked_pages = AnimatedStackedWidget(self, duration=220)
        content_layout.addWidget(self.stacked_pages)

        # Instantiate Layout Generators
        self.create_dashboard_page()      
        self.create_face_attendance_page() 
        self.create_noticeboard_page()     
        self.create_students_page()       
        self.create_leaves_page()         
        self.create_holidays_page()       
        self.create_reports_page()        
        self.create_profile_page()

        # Real-time Auto-Attendance Engine State
        self._student_own_embedding = None
        self.auto_attendance_marked = False
        self.auto_mark_in_progress = False
        self.consecutive_face_matches = 0
        self.auto_scan_frame_counter = 0

        self.page_loader_threads = []
        main_layout.addLayout(content_layout)
        self.load_page_content(0)

    def change_page(self):
        sender = self.sender()
        index = sender.property("index")
        self.stacked_pages.setCurrentIndex(index)
        self.page_title.setText(f"{sender.text()} System Workspace")
        
        if index == 1:
            self.start_camera()
            self.verify_indicator.setText("Align your face inside the tracking box and click 'Mark My Attendance'.")
            self.verify_indicator.setStyleSheet(
                "font-size: 14px; font-weight: 600; color: #1e3a8a; padding: 12px; "
                "background-color: #f0f4ff; border-radius: 8px; border: 1px solid #cbd5e1;"
            )
            # Refresh admin student list whenever the face attendance page is opened
            if hasattr(self, "_admin_refresh_students"):
                self._admin_refresh_students()
        else:
            self.stop_camera()

        if index == 0:
            self.load_page_content(0)
        elif index == 2:
            self.load_page_content(2)
        elif index == 3:
            self.load_page_content(3)
        elif index == 4:
            self.load_page_content(4)
        elif index == 5:
            self.load_page_content(5)
        elif index == 6:
            self.load_page_content(6)
        elif index == 7:
            if hasattr(self, "populate_profile_view"):
                self.populate_profile_view(self.user_info or {})
            self.load_page_content(7)

    def start_notification_socket(self):
        if not api_client.token:
            return
        if self.notification_socket and self.notification_socket.isRunning():
            return
        self.notification_socket = NotificationSocketWorker(api_client.token, api_client.base_url)
        self.notification_socket.notification_received.connect(self.show_live_notification)
        self.notification_socket.start()

    def _remove_page_loader_thread(self, thread: QThread):
        try:
            if thread in self.page_loader_threads:
                self.page_loader_threads.remove(thread)
        except Exception:
            pass

    def load_page_content(self, index: int):
        thread = PageDataLoader(index, self.user_info)
        thread.data_loaded.connect(self.on_page_data_loaded)
        thread.error.connect(self.on_page_data_load_error)
        thread.finished.connect(lambda th=thread: self._remove_page_loader_thread(th))
        thread.finished.connect(thread.deleteLater)
        self.page_loader_threads.append(thread)
        thread.start()

    @pyqtSlot(int, object)
    def on_page_data_loaded(self, index: int, payload: object):
        if index == 0:
            summary = payload.get("summary", {})
            records = payload.get("records", [])
            self.cards["total_students"].set_animated_value(summary.get("total_students", 0))
            self.cards["present"].set_animated_value(summary.get("present", 0))
            self.cards["absent"].set_animated_value(summary.get("absent", 0))
            self.cards["late"].set_animated_value(summary.get("late", 0))
            self.cards["leave"].set_animated_value(summary.get("leave", 0))
            self.cards["holiday"].set_animated_value(summary.get("holiday", 0))

            self.dashboard_table.setRowCount(0)
            records_sorted = sorted(records, key=lambda x: x.get("check_in") or "", reverse=True)
            for idx, r in enumerate(records_sorted[:15]):
                self.dashboard_table.insertRow(idx)
                self.dashboard_table.setItem(idx, 0, QTableWidgetItem(r.get("registration_number", "-")))
                self.dashboard_table.setItem(idx, 1, QTableWidgetItem(r.get("student_name", "-")))
                self.dashboard_table.setItem(idx, 2, QTableWidgetItem(format_12hr_time(r.get("check_in"))))
                self.dashboard_table.setItem(idx, 3, QTableWidgetItem(r.get("status", "-")))
                self.dashboard_table.setItem(idx, 4, QTableWidgetItem(r.get("verification_method", "-")))
        elif index == 2:
            while self.notice_layout.count():
                item = self.notice_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for holiday in payload.get("holidays", []):
                card = QFrame()
                card.setProperty("class", "NoticeCard")
                card_layout = QVBoxLayout(card)
                card_layout.setSpacing(8)

                title = QLabel(f"📢  {holiday.get('name', '')}")
                title.setProperty("class", "NoticeTitle")

                date_lbl = QLabel(f"Effective Date Vector: {holiday.get('date', '')}")
                date_lbl.setProperty("class", "NoticeDate")

                desc = QLabel(holiday.get("description", ""))
                desc.setWordWrap(True)
                desc.setProperty("class", "NoticeDescription")

                card_layout.addWidget(title)
                card_layout.addWidget(date_lbl)
                card_layout.addWidget(desc)
                self.notice_layout.addWidget(card)
            self.notice_layout.addStretch()
        elif index == 3:
            self._populate_students_table(payload.get("students", []))
        elif index == 4:
            self.populate_leaves_table(payload.get("leaves", []))
        elif index == 5:
            self.holidays_table.setRowCount(0)
            for idx, h in enumerate(payload.get("holidays", [])):
                self.holidays_table.insertRow(idx)
                self.holidays_table.setItem(idx, 0, QTableWidgetItem(h.get("date", "-")))
                self.holidays_table.setItem(idx, 1, QTableWidgetItem(h.get("name", "-")))
                self.holidays_table.setItem(idx, 2, QTableWidgetItem(h.get("description", "")))
        elif index == 6:
            archives = payload.get("archives", [])
            self.populate_monthly_report_archives_table(archives)
        elif index == 7:
            profile = payload.get("profile", {})
            self.populate_profile_view(profile)

    @pyqtSlot(int, str)
    def on_page_data_load_error(self, index: int, error_message: str):
        logger.error(f"Failed to load page {index} data asynchronously: {error_message}")
        if index == 2:
            while self.notice_layout.count():
                item = self.notice_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.notice_layout.addWidget(QLabel("Unable to load noticeboard data."))
        elif index == 3:
            self.students_table.setRowCount(0)
        elif index == 4:
            self.leaves_table.setRowCount(0)
        elif index == 5:
            self.holidays_table.setRowCount(0)
        elif index == 6:
            if hasattr(self, "archived_reports_table"):
                self.archived_reports_table.setRowCount(0)
        elif index == 0:
            self.dashboard_table.setRowCount(0)
        elif index == 7:
            if hasattr(self, "profile_status_label"):
                self.profile_status_label.setText(f"Unable to load profile data: {error_message}")

    def refresh_all_pages(self):
        """Refreshes all data across active pages and tables from backend."""
        try:
            curr_idx = self.stacked_pages.currentIndex()
            self.load_page_content(curr_idx)

            if hasattr(self, "refresh_leaves"):
                self.refresh_leaves()

            QMessageBox.information(self, "Refreshed", "All pages and data reloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to refresh pages: {e}")
            QMessageBox.critical(self, "Error", f"Failed to refresh data: {e}")

    def show_live_notification(self, notification: dict):
        ntype = notification.get("type") or notification.get("notification_type")
        title = notification.get("title", "TIPS-G Notification")
        message = notification.get("message", "")

        # 1. Pop native Windows desktop system tray toast notification
        if hasattr(self, "tray_icon") and self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 6000)

        # 2. In-App slide-down animated toast banner
        if hasattr(self, "toast") and self.toast:
            self.toast.show_message(f"{title}: {message}", icon="🔔", is_success=True)

        # 3. Reload data and refresh badges
        if ntype in ["leave_request", "leave_status_update"]:
            if hasattr(self, "refresh_leaves"):
                self.refresh_leaves()
            if self.stacked_pages.currentIndex() == 0:
                self.load_page_content(0)

    def handle_logout(self):
        self.stop_camera()
        if self.notification_socket:
            self.notification_socket.stop()
        if self.refresh_timer:
            self.refresh_timer.stop()
        api_client.logout()
        self.login_window = LoginWindow()
        self.login_window.setStyleSheet(MODERN_STYLE)
        self.login_window.login_success.connect(self.on_relogin)
        self.login_window.show()
        self.close()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "ambient_bg") and self.ambient_bg:
            self.ambient_bg.resize(self.size())

    def closeEvent(self, event):
        self.stop_camera()
        if self.notification_socket:
            self.notification_socket.stop()
        if self.refresh_timer:
            self.refresh_timer.stop()
        super().closeEvent(event)

    def on_relogin(self, user_info):
        self.main_window = MainWindow(user_info)
        self.main_window.setStyleSheet(MODERN_STYLE)
        self.main_window.showMaximized()
        self.login_window.close()

    def handle_create_desktop_shortcut(self):
        """Creates a desktop shortcut with the official TIPS-G icon."""
        try:
            success, message, paths = icon_manager.create_desktop_shortcut("TIPS-G Attendance AI")
            if success:
                QMessageBox.information(self, "Desktop Shortcut Created", message)
            else:
                QMessageBox.warning(self, "Shortcut Creation Note", message)
        except Exception as e:
            logger.error(f"Error creating desktop shortcut: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create desktop shortcut: {e}")

    # --- Page 0: Dashboard Metrics Architecture ---
    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 30)
        layout.setSpacing(25)

        hdr_layout = QHBoxLayout()
        hdr_label = QLabel("Daily Telemetry & Operational Metrics")
        hdr_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;")
        hdr_layout.addWidget(hdr_label)
        hdr_layout.addStretch()
        
        trigger_scan_btn = QPushButton("🔍  Scan Absences & Email Parents")
        trigger_scan_btn.setObjectName("TriggerScanBtn")
        trigger_scan_btn.setProperty("class", "SecondaryBtn")
        trigger_scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        trigger_scan_btn.setStyleSheet("""
            QPushButton.SecondaryBtn { 
                color: #1e3a8a; 
                font-weight: 700; 
                background-color: #dbeafe; 
                border: 1px solid #bfdbfe;
                padding: 8px 14px;
                border-radius: 8px;
            }
            QPushButton.SecondaryBtn:hover {
                background-color: #bfdbfe;
            }
        """)
        trigger_scan_btn.clicked.connect(self.trigger_daily_scan)
        if self.user_info.get("role") in ["admin", "teacher", "manager", "hr"]:
            hdr_layout.addWidget(trigger_scan_btn)
        layout.addLayout(hdr_layout)

        cards_grid = QHBoxLayout()
        cards_grid.setSpacing(16)

        self.cards = {}
        metrics = [
            ("Total Registry", "total_students", "#10b981"),
            ("Present Status", "present", "#34d399"),
            ("Absent Logs", "absent", "#f87171"),
            ("Late Arrivals", "late", "#fbbf24"),
            ("Active Leave", "leave", "#a7f3d0"),
            ("Holiday Event", "holiday", "#94a3b8")
        ]

        for title, key, color in metrics:
            card = QFrame()
            card.setProperty("class", "Card")
            card.setStyleSheet(f"QFrame.Card {{ border-top: 3px solid {color}; }}")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)
            
            val = AnimatedStatLabel("0")
            val.setProperty("class", "CardValue")
            val.setStyleSheet(f"color: {color};")
            
            lbl = QLabel(title)
            lbl.setProperty("class", "CardLabel")
            
            card_layout.addWidget(val)
            card_layout.addWidget(lbl)
            cards_grid.addWidget(card)
            self.cards[key] = val

        layout.addLayout(cards_grid)

        lbl_section = QLabel("Real-Time Infrastructure Streams & Transaction Logs")
        lbl_section.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e3a8a;")
        layout.addWidget(lbl_section)
        
        self.dashboard_table = QTableWidget()
        self.dashboard_table.setColumnCount(5)
        self.dashboard_table.setHorizontalHeaderLabels(["Reg Domain", "Identity Descriptor", "Timestamp", "State Status", "Verification Core"])
        self.dashboard_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dashboard_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.dashboard_table)

        self.stacked_pages.addWidget(page)

    def refresh_dashboard(self, show_errors=True):
        try:
            summary = api_client.get_summary()
            self.cards["total_students"].set_animated_value(summary.get("total_students", 0))
            self.cards["present"].set_animated_value(summary.get("present", 0))
            self.cards["absent"].set_animated_value(summary.get("absent", 0))
            self.cards["late"].set_animated_value(summary.get("late", 0))
            self.cards["leave"].set_animated_value(summary.get("leave", 0))
            self.cards["holiday"].set_animated_value(summary.get("holiday", 0))

            if summary.get("is_holiday"):
                self.cards["holiday"].setStyleSheet("color: #ef4444; font-weight: bold; font-size:32px;")
            else:
                self.cards["holiday"].setStyleSheet("color: #94a3b8; font-size:32px;")

            records = api_client.get_daily_attendance()
            self.dashboard_table.setRowCount(0)
            records_sorted = sorted(records, key=lambda x: x.get("check_in") or "", reverse=True)

            for idx, r in enumerate(records_sorted[:15]):
                self.dashboard_table.insertRow(idx)
                self.dashboard_table.setItem(idx, 0, QTableWidgetItem(r["registration_number"]))
                self.dashboard_table.setItem(idx, 1, QTableWidgetItem(r["student_name"]))
                self.dashboard_table.setItem(idx, 2, QTableWidgetItem(r["check_in"] or "-"))
                self.dashboard_table.setItem(idx, 3, QTableWidgetItem(r["status"]))
                self.dashboard_table.setItem(idx, 4, QTableWidgetItem(r["verification_method"]))
        except Exception as e:
            logger.error(f"Dashboard telemetry read error: {e}")
            if show_errors:
                QMessageBox.warning(self, "Pipeline Error", f"Could not sync with local database: {str(e)}")

    def show_notifications(self):
        try:
            notifications = api_client.get_notifications()
        except Exception as error:
            QMessageBox.warning(self, "Notifications", f"Could not load notifications: {error}")
            return
        if not notifications:
            QMessageBox.information(self, "Notifications", "No notifications yet.")
            return
        message = "\n\n".join(
            f"{item['title']}\n{item['message']}\n{item['created_at']}"
            for item in notifications[:20]
        )
        QMessageBox.information(self, "Notifications", message)
    def auto_refresh_dashboard(self):
        if self.stacked_pages.currentIndex() == 0:
            self.load_page_content(0)

    # --- Page 1: Biometric Verification Core ---
    def create_face_attendance_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(30)

        left_layout = QVBoxLayout()
        self.camera_feed = QLabel("Initializing Capture Device Pipeline...")
        self.camera_feed.setObjectName("CameraFeedLabel")
        self.camera_feed.setStyleSheet("background-color: #ffffff; border: 2px dashed #cbd5e1; border-radius: 12px;")
        self.camera_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_feed.setMinimumSize(640, 480)
        left_layout.addWidget(self.camera_feed)

        self.verify_indicator = QLabel("Target face alignment tracking interface offline.")
        self.verify_indicator.setStyleSheet("font-size: 14px; font-weight: 600; color: #475569; padding: 12px; background-color: #f0f4ff; border-radius: 8px; border: 1px solid #cbd5e1;")
        self.verify_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.verify_indicator)
        layout.addLayout(left_layout, stretch=2)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(16)

        self.face_verify_btn = QPushButton("▶  Mark My Attendance")
        self.face_verify_btn.setObjectName("SimulateFaceBtn")
        self.face_verify_btn.setProperty("class", "PrimaryBtn")
        self.face_verify_btn.setStyleSheet("QPushButton.PrimaryBtn")
        self.face_verify_btn.clicked.connect(self.simulate_face_match)
        # Students always see their own verify button; hide it for admin/teacher
        if self.user_info.get("role") != "student":
            self.face_verify_btn.setVisible(False)
        right_layout.addWidget(self.face_verify_btn)

        # ── Admin-only: Verify a student's face on their behalf ──────────────
        if self.user_info.get("role") in ("admin", "teacher", "hr"):
            admin_frame = QFrame()
            admin_frame.setStyleSheet(
                "QFrame { background: #f0f9ff; border: 2px solid #0ea5e9; border-radius: 12px; padding: 4px; }"
            )
            admin_fl = QVBoxLayout(admin_frame)
            admin_fl.setSpacing(10)

            admin_title = QLabel("🛡  Admin: Verify Student Face")
            admin_title.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: #0c4a6e; "
                "background: transparent; border: none; padding: 4px 0;"
            )
            admin_fl.addWidget(admin_title)

            admin_info = QLabel("Use when a student's own camera is unavailable.\nSelect student → load embedding → verify face.")
            admin_info.setStyleSheet("font-size: 11px; color: #475569; background: transparent; border: none;")
            admin_info.setWordWrap(True)
            admin_fl.addWidget(admin_info)

            # Student selector dropdown
            self.admin_student_combo = QComboBox()
            self.admin_student_combo.setPlaceholderText("— Select student —")
            self.admin_student_combo.setMinimumHeight(36)
            self.admin_student_combo.setStyleSheet(
                "QComboBox { border: 1px solid #7dd3fc; border-radius: 6px; padding: 6px 10px; background: white; }"
                "QComboBox::drop-down { border: none; }"
            )
            admin_fl.addWidget(self.admin_student_combo)

            self._admin_students_map = {}   # display name → student dict

            load_emb_btn = QPushButton("📥  Load Student Embedding")
            load_emb_btn.setMinimumHeight(34)
            load_emb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            load_emb_btn.setStyleSheet(
                "QPushButton { background: #0ea5e9; color: white; border-radius: 6px; "
                "font-weight: 700; font-size: 12px; }"
                "QPushButton:hover { background: #0284c7; }"
                "QPushButton:disabled { background: #94a3b8; }"
            )
            admin_fl.addWidget(load_emb_btn)

            self.admin_emb_status = QLabel("")
            self.admin_emb_status.setStyleSheet("font-size: 11px; color: #0c4a6e; background: transparent; border: none;")
            self.admin_emb_status.setWordWrap(True)
            admin_fl.addWidget(self.admin_emb_status)

            self.admin_verify_btn = QPushButton("✅  Verify Face & Mark Attendance")
            self.admin_verify_btn.setMinimumHeight(38)
            self.admin_verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.admin_verify_btn.setEnabled(False)
            self.admin_verify_btn.setStyleSheet(
                "QPushButton { background: #16a34a; color: white; border-radius: 8px; "
                "font-weight: 800; font-size: 13px; }"
                "QPushButton:hover { background: #15803d; }"
                "QPushButton:disabled { background: #94a3b8; }"
            )
            admin_fl.addWidget(self.admin_verify_btn)

            self.admin_result_label = QLabel("")
            self.admin_result_label.setStyleSheet(
                "font-size: 12px; font-weight: 600; color: #0c4a6e; "
                "background: transparent; border: none; padding: 4px 0;"
            )
            self.admin_result_label.setWordWrap(True)
            self.admin_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            admin_fl.addWidget(self.admin_result_label)

            right_layout.addWidget(admin_frame)

            # ── wire up the load & verify buttons ────────────────────────────
            self._admin_target_embedding = None

            def _refresh_student_list():
                self.admin_student_combo.clear()
                self._admin_students_map.clear()
                self.admin_emb_status.setText("Loading student list...")
                QApplication.processEvents()
                try:
                    students = api_client.get_students()
                    for s in students:
                        label = f"{s['full_name']}  ({s['registration_number']})"
                        self._admin_students_map[label] = s
                        self.admin_student_combo.addItem(label)
                    self.admin_emb_status.setText(f"✔ {len(students)} students loaded.")
                except Exception as exc:
                    self.admin_emb_status.setText(f"⚠ Failed to load students: {exc}")

            def _load_embedding():
                label = self.admin_student_combo.currentText()
                student = self._admin_students_map.get(label)
                if not student:
                    self.admin_emb_status.setText("⚠ Please select a student first.")
                    return
                load_emb_btn.setEnabled(False)
                load_emb_btn.setText("⏳  Loading...")
                self.admin_emb_status.setText(f"Fetching embedding for {student['full_name']}...")
                self._admin_target_embedding = None
                self.admin_verify_btn.setEnabled(False)
                QApplication.processEvents()
                try:
                    res = api_client.get_student_embedding(student["id"])
                    emb = res.get("embedding")
                    if emb:
                        self._admin_target_embedding = emb
                        self.admin_emb_status.setText(
                            f"✅  Embedding loaded for {student['full_name']}.\n"
                            "Ask the student to stand in front of the camera and click Verify."
                        )
                        self.admin_verify_btn.setEnabled(True)
                    else:
                        self.admin_emb_status.setText(
                            f"❌  No face embedding registered for {student['full_name']}.\n"
                            "Please register their photo first."
                        )
                except Exception as exc:
                    self.admin_emb_status.setText(f"⚠ Error: {exc}")
                finally:
                    load_emb_btn.setEnabled(True)
                    load_emb_btn.setText("📥  Load Student Embedding")

            def _admin_verify():
                label = self.admin_student_combo.currentText()
                student = self._admin_students_map.get(label)
                if not student or not self._admin_target_embedding:
                    self.admin_result_label.setText("⚠ Load a student embedding first.")
                    return

                if not self.last_frame_bytes:
                    self.admin_result_label.setText("⚠ Camera not ready. Is the camera on?")
                    return

                self.admin_verify_btn.setEnabled(False)
                self.admin_verify_btn.setText("⏳  Verifying...")
                self.admin_result_label.setText("🔍  Running face match against stored profile...")
                QApplication.processEvents()

                try:
                    from frontend.onnx_face_service import onnx_face_service
                    from frontend.utils.wifi_checker import get_current_bssid

                    import time as _pytime
                    frames_to_check = [self.last_frame_bytes]
                    for _ in range(2):
                        _pytime.sleep(0.08)
                        QApplication.processEvents()
                        if self.last_frame_bytes and self.last_frame_bytes not in frames_to_check:
                            frames_to_check.append(self.last_frame_bytes)

                    verify_res = onnx_face_service.verify_face_burst(frames_to_check, self._admin_target_embedding)

                    if not verify_res.get("verified"):
                        self.admin_result_label.setStyleSheet(
                            "font-size: 12px; font-weight: 700; color: #dc2626; "
                            "background: #fff1f2; border: 1px solid #fecaca; border-radius: 8px; padding: 8px;"
                        )
                        self.admin_result_label.setText(
                            f"❌  Face not matched.\n{verify_res.get('error', 'Verification failed.')}"
                        )
                        self.session_log_text.append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] ADMIN-VERIFY REJECT: "
                            f"{student['full_name']} — {verify_res.get('error', 'no match')}"
                        )
                        return

                    confidence = verify_res.get("confidence", 0.0)
                    candidate_embedding = verify_res.get("candidate_embedding", [])
                    bssid = get_current_bssid()

                    res = api_client.submit_admin_face_attendance(
                        student_id=student["id"],
                        confidence=confidence,
                        bssid=bssid,
                        candidate_embedding=candidate_embedding
                    )

                    if res.get("status") == "success":
                        self.admin_result_label.setStyleSheet(
                            "font-size: 12px; font-weight: 700; color: #15803d; "
                            "background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 8px;"
                        )
                        self.admin_result_label.setText(res.get("message", "Attendance marked."))
                        self.session_log_text.append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] ADMIN-VERIFY PASS: "
                            f"{student['full_name']} ({confidence:.1f}% confidence)"
                        )
                    else:
                        self.admin_result_label.setStyleSheet(
                            "font-size: 12px; font-weight: 700; color: #dc2626; "
                            "background: #fff1f2; border: 1px solid #fecaca; border-radius: 8px; padding: 8px;"
                        )
                        self.admin_result_label.setText(f"❌  {res.get('error', 'Attendance failed.')}")
                        self.session_log_text.append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] ADMIN-VERIFY FAIL: {res.get('error')}"
                        )

                except Exception as exc:
                    self.admin_result_label.setStyleSheet(
                        "font-size: 12px; font-weight: 700; color: #dc2626; background: transparent; border: none;"
                    )
                    self.admin_result_label.setText(f"⚠  Error: {exc}")
                    logger.error(f"Admin face verify error: {exc}", exc_info=True)
                finally:
                    self.admin_verify_btn.setEnabled(True)
                    self.admin_verify_btn.setText("✅  Verify Face & Mark Attendance")

            # Refresh students when the page is first shown and on combo click
            load_emb_btn.clicked.connect(_load_embedding)
            self.admin_verify_btn.clicked.connect(_admin_verify)

            # Store refresh callable so change_page can call it
            self._admin_refresh_students = _refresh_student_list

        right_layout.addWidget(QLabel("Live System Logs"))
        self.session_log_text = QTextEdit()
        self.session_log_text.setReadOnly(True)
        self.session_log_text.setStyleSheet("background-color: #f8f9ff; border: 1px solid #cbd5e1; font-family: Consolas, monospace; font-size:12px; color:#1e3a8a; border-radius: 8px;")
        right_layout.addWidget(self.session_log_text)
        layout.addLayout(right_layout, stretch=1)

        self.stacked_pages.addWidget(page)

    def start_camera(self):
        if not self.camera_thread:
            self.camera_thread = CameraThread()
            self.camera_thread.change_pixmap_signal.connect(self.update_camera_frame)
            self.camera_thread.start()
            self.session_log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] Core Pipeline initialization verified.")

    def stop_camera(self):
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
            self.camera_feed.setText("Device framework paused.")
            self.session_log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] Core Video IO pipeline severed safely.")

    @pyqtSlot(np.ndarray)
    def update_camera_frame(self, cv_img):
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape

        # Save clean frame for face model verification
        ret, jpeg = cv2.imencode('.jpg', cv_img)
        if ret:
            self.last_frame_bytes = jpeg.tobytes()

        # 🔍 Auto-detect student face in camera frame anywhere
        detected_box = onnx_face_service.detect_face_box(cv_img)
        has_face = detected_box is not None

        # Build QPixmap
        bytes_per_line = ch * w
        q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(q_img)

        # 📸 Draw clean target frame ONLY after face is detected
        if has_face:
            bx, by, bw, bh = detected_box
            pad_x = int(bw * 0.08)
            pad_y = int(bh * 0.08)
            bx = max(0, bx - pad_x)
            by = max(0, by - pad_y)
            bw = min(w - bx, bw + 2 * pad_x)
            bh = min(h - by, bh + 2 * pad_y)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            is_verified = getattr(self, "auto_attendance_marked", False)
            frame_color = QColor(16, 185, 129) if is_verified else QColor(56, 189, 248)

            # 1. Sleek face frame
            pen = QPen(frame_color, 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(bx, by, bw, bh, 6, 6)

            # 2. Corner brackets
            corner_len = min(22, bw // 4, bh // 4)
            bracket_pen = QPen(frame_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(bracket_pen)
            # Top-Left
            painter.drawLine(bx, by, bx + corner_len, by)
            painter.drawLine(bx, by, bx, by + corner_len)
            # Top-Right
            painter.drawLine(bx + bw, by, bx + bw - corner_len, by)
            painter.drawLine(bx + bw, by, bx + bw, by + corner_len)
            # Bottom-Left
            painter.drawLine(bx, by + bh, bx + corner_len, by + bh)
            painter.drawLine(bx, by + bh, bx, by + bh - corner_len)
            # Bottom-Right
            painter.drawLine(bx + bw, by + bh, bx + bw - corner_len, by + bh)
            painter.drawLine(bx + bw, by + bh, bx + bw, by + corner_len)

            # 3. Label tag above face
            label_text = "✓ VERIFIED" if is_verified else "✓ FACE DETECTED"
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            tag_rect = QRect(bx, max(0, by - 26), bw, 22)
            painter.fillRect(tag_rect, QColor(15, 23, 42, 210))
            painter.setPen(frame_color)
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, label_text)

            painter.end()

        # Dynamically update the indicator label below the camera
        if hasattr(self, "verify_indicator") and not getattr(self, "auto_mark_in_progress", False) and not getattr(self, "auto_attendance_marked", False):
            if has_face:
                self.verify_indicator.setText("✓ Face Detected! Ready to mark attendance.")
                self.verify_indicator.setStyleSheet(
                    "font-size: 14px; font-weight: 700; color: #065f46; padding: 12px; "
                    "background-color: #d1fae5; border-radius: 8px; border: 1.5px solid #34d399;"
                )
            else:
                self.verify_indicator.setText("🔍 Position face in front of the camera...")
                self.verify_indicator.setStyleSheet(
                    "font-size: 14px; font-weight: 600; color: #1e3a8a; padding: 12px; "
                    "background-color: #f0f4ff; border-radius: 8px; border: 1px solid #cbd5e1;"
                )

        self.camera_feed.setPixmap(pixmap.scaled(self.camera_feed.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def simulate_face_match(self):
        if not is_university_wifi():
            QMessageBox.warning(
                self,
                "University WiFi Required",
                "Please connect to the University WiFi before marking attendance."
            )
            return

        if not self.last_frame_bytes:
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            ret, jpeg = cv2.imencode('.jpg', img)
            self.last_frame_bytes = jpeg.tobytes()

        # --- Loading indicator: disable button and show spinner text ---
        self.face_verify_btn.setEnabled(False)
        self.face_verify_btn.setText("⏳  Processing face model...")
        self.verify_indicator.setStyleSheet("font-size: 14px; font-weight: 600; color: #1e3a8a; padding: 12px; background-color: #e0e7ff; border-radius: 8px; border: 1px solid #a5b4fc;")
        self.verify_indicator.setText("🔍  Running face alignment & liveness check, please hold still...")
        QApplication.processEvents()

        try:
            # Always fetch fresh embedding from backend/DB for the logged-in student
            try:
                res_emb = api_client.get_my_embedding()
                self.my_embedding = res_emb.get("embedding")
            except Exception as e:
                logger.warning(f"API load student embedding ({e}), querying database directly...")
                self.my_embedding = None

            if not self.my_embedding:
                try:
                    from src.database.connection import SessionLocal
                    from src.database.models import Student, FaceEmbedding
                    import json
                    db = SessionLocal()
                    uname = self.user_info.get("username", "")
                    s = db.query(Student).filter(Student.registration_number == uname).first()
                    if not s and uname.endswith("-tipsg"):
                        s = db.query(Student).filter(Student.registration_number == uname[:-6]).first()
                    if not s and not uname.endswith("-tipsg"):
                        s = db.query(Student).filter(Student.registration_number == f"{uname}-tipsg").first()
                    if s:
                        emb_rec = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == s.id).first()
                        if emb_rec and emb_rec.embedding:
                            self.my_embedding = json.loads(emb_rec.embedding) if isinstance(emb_rec.embedding, str) else emb_rec.embedding
                    db.close()
                except Exception as db_err:
                    logger.debug(f"DB load embedding error: {db_err}")

            if not self.my_embedding:
                raise ValueError("No registered face embedding found for your account. Please ask admin to register your photo.")

            from datetime import datetime, date, time, timezone, timedelta
            _IST = timezone(timedelta(hours=5, minutes=30))
            student_name = self.user_info.get("full_name", "Unknown")
            logger.info(f"Starting 1-to-1 face verification for student: {student_name}")

            # Perform local face verification with burst evaluation (3 continuous frames)
            from frontend.onnx_face_service import onnx_face_service
            import time as _pytime
            frames_to_check = [self.last_frame_bytes]
            for _ in range(2):
                _pytime.sleep(0.08)
                QApplication.processEvents()
                if self.last_frame_bytes and self.last_frame_bytes not in frames_to_check:
                    frames_to_check.append(self.last_frame_bytes)

            verify_res = onnx_face_service.verify_face_burst(frames_to_check, self.my_embedding)
            
            if not verify_res.get("verified"):
                self.verify_indicator.setStyleSheet("color: #ffffff; font-weight: bold; background-color: #ef4444; border-radius: 12px; border: 1px solid #dc2626; padding: 12px;")
                self.verify_indicator.setText(verify_res.get("error", "Face verification failed."))
                self.session_log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] REJECT: {verify_res.get('error', 'Face Unrecognized')}")
                return

            if verify_res.get("adaptive_updated") and verify_res.get("updated_embedding"):
                self.my_embedding = verify_res["updated_embedding"]
                logger.info("Local student embedding adapted seamlessly.")

            confidence = verify_res.get("confidence", 0.0)
            candidate_embedding = verify_res.get("candidate_embedding", [])
            current_bssid = get_current_bssid()

            
            # Submit verification score, candidate embedding, and BSSID to backend to record attendance
            res = api_client.submit_verified_attendance(
                confidence=confidence,
                bssid=current_bssid,
                candidate_embedding=candidate_embedding
            )
            
            if res.get("status") == "success":
                self.verify_indicator.setStyleSheet("color: #ffffff; font-weight: bold; background-color: #16a34a; border-radius: 12px; border: 1px solid #15803d; padding: 12px;")
                self.verify_indicator.setText(f"✅  {res['message']} (Confidence: {confidence:.1f}%)")
                self.session_log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] PASS: {res.get('student_name', self.user_info.get('full_name', 'Student'))} ({confidence:.1f}% Confidence)")
                if hasattr(self, "toast") and self.toast:
                    self.toast.show_message(f"Attendance Recorded! ({confidence:.1f}% Match)", icon="✨", is_success=True)
            else:
                recorded_via_db = False
                try:
                    from src.database.connection import SessionLocal
                    from src.database.models import Student, Attendance, Holiday
                    today = datetime.now(_IST).date()
                    now_time = datetime.now(_IST).time()
                    
                    db = SessionLocal()
                    student_id = self.user_info.get("id")
                    st = db.query(Student).filter(Student.id == student_id).first() if student_id else None
                    if st:
                        is_holiday = db.query(Holiday).filter(Holiday.date == today).first() is not None
                        if is_holiday:
                            err_msg = "Today is a holiday. No attendance registration required."
                        else:
                            existing = db.query(Attendance).filter(Attendance.student_id == st.id, Attendance.date == today).first()
                            if existing:
                                existing.check_out = now_time
                                db.commit()
                                msg = f"Goodbye {st.full_name}! Check-out registered."
                            else:
                                start_time_obj = time(9, 0, 0)
                                late_limit = time(9, 15, 0)
                                att_status = "Present" if now_time <= late_limit else "Late"
                                rec = Attendance(
                                    student_id=st.id,
                                    date=today,
                                    check_in=now_time,
                                    status=att_status,
                                    confidence_score=confidence,
                                    verification_method="Face"
                                )
                                db.add(rec)
                                db.commit()
                                msg = f"Welcome {st.full_name}! Attendance marked as {att_status}."
                            
                            recorded_via_db = True
                            self.verify_indicator.setStyleSheet("color: #ffffff; font-weight: bold; background-color: #16a34a; border-radius: 12px; border: 1px solid #15803d; padding: 12px;")
                            self.verify_indicator.setText(f"✅  {msg} (Confidence: {confidence:.1f}%)")
                            self.session_log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] PASS: {st.full_name} ({confidence:.1f}% Confidence)")
                    db.close()
                except Exception as db_err:
                    logger.debug(f"Direct DB attendance fallback error: {db_err}")

                if not recorded_via_db:
                    self.verify_indicator.setStyleSheet("color: #ffffff; font-weight: bold; background-color: #ef4444; border-radius: 12px; border: 1px solid #dc2626; padding: 12px;")
                    self.verify_indicator.setText(res.get("error", "Attendance registration failed."))
                    self.session_log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] REJECT: {res.get('error', 'Attendance failed')}")
        except Exception as e:
            import traceback
            print("\n========== ATTENDANCE ERROR ==========")
            print("Error:", str(e))
            traceback.print_exc()
            print("=====================================\n")
            self.verify_indicator.setStyleSheet("color: #ef4444; font-weight: bold; background-color: #fff1f2; border-radius: 8px; border: 1px solid #fecaca; padding: 12px;")
            self.verify_indicator.setText(f"⚠  ERROR: {str(e)}")
            QMessageBox.critical(self, "Attendance Error", str(e))
        finally:
            # Always restore the button regardless of success or failure
            self.face_verify_btn.setEnabled(True)
            self.face_verify_btn.setText("▶  Mark My Attendance")

    # --- Page 2: Broadcast Notice Board ---
    def create_noticeboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        self.notice_layout = QVBoxLayout(container)
        self.notice_layout.setSpacing(15)
        self.notice_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self.stacked_pages.addWidget(page)

    def load_noticeboard(self):
        while self.notice_layout.count():
            item = self.notice_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        try:
            holidays = api_client.get_noticeboard_holidays()
            for holiday in holidays:
                card = QFrame()
                card.setProperty("class", "NoticeCard")
                card_layout = QVBoxLayout(card)
                card_layout.setSpacing(8)

                title = QLabel(f"📢  {holiday['name']}")
                title.setProperty("class", "NoticeTitle")

                date_lbl = QLabel(f"Effective Date Vector: {holiday['date']}")
                date_lbl.setProperty("class", "NoticeDate")

                desc = QLabel(holiday["description"])
                desc.setWordWrap(True)
                desc.setProperty("class", "NoticeDescription")

                card_layout.addWidget(title)
                card_layout.addWidget(date_lbl)
                card_layout.addWidget(desc)
                self.notice_layout.addWidget(card)
            self.notice_layout.addStretch()
        except Exception as e:
            error = QLabel(f"Notice Board Database Layer Drop Event:\n{e}")
            self.notice_layout.addWidget(error)

    def trigger_daily_scan(self):
        try:
            res = api_client.trigger_absence_scan()
            msg = (
                f"Daily Absence Scan Executed!\n\n"
                f"• Students Marked Absent: {res.get('marked_absent_count', 0)}\n"
                f"• Parent Emails & Alerts Dispatched: {res.get('triggered_alerts_count', 0)}\n\n"
                f"Parent notification emails have been dispatched to absent students' parents."
            )
            QMessageBox.information(self, "Absence Scan & Parent Emails Dispatched", msg)
            if hasattr(self, "refresh_all_pages"):
                self.refresh_all_pages()
        except Exception as e:
            logger.error(f"Failed daily absence scan: {e}")
            QMessageBox.critical(self, "Error", f"Failed to execute absence scan: {e}")

    # --- Page 3: Student Directory Layout ---
    def create_students_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        lbl = QLabel("Student Framework Vector Directory")
        lbl.setStyleSheet("font-size:16px; font-weight:800; color:#1e3a8a;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        add_btn = QPushButton("+ Register New Student")
        add_btn.setObjectName("AddStudentBtn")
        add_btn.setProperty("class", "PrimaryBtn")
        add_btn.setStyleSheet("QPushButton.PrimaryBtn { padding: 10px 18px; }")
        add_btn.clicked.connect(self.open_register_student_dialog)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        # Search Bar Filter
        search_card = QFrame()
        search_card.setProperty("class", "Card")
        search_card.setStyleSheet("QFrame.Card { padding: 10px 16px; }")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 14px;")
        self.student_search_input = QLineEdit()
        self.student_search_input.setPlaceholderText("Search students by name, registration number, course, email, parent phone...")
        self.student_search_input.setClearButtonEnabled(True)
        self.student_search_input.textChanged.connect(self.filter_students_table)

        search_layout.addWidget(search_icon)
        search_layout.addWidget(self.student_search_input)
        layout.addWidget(search_card)

        # Table Widget with Neumorphic Styling & Fixed Actions Column Width
        self.students_table = QTableWidget()
        self.students_table.setColumnCount(8)
        self.students_table.setHorizontalHeaderLabels([
            "Reg. Number", "Full Name", "Course",
            "Student Email", "Parent Name", "Parent Phone", "Parent Email",
            "Actions"
        ])
        
        header = self.students_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.students_table.setColumnWidth(7, 130)

        self.students_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.students_table.setAlternatingRowColors(True)
        self.students_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.students_table)

        self.stacked_pages.addWidget(page)

    def _populate_students_table(self, students: list):
        self._cached_students_list = students
        self.students_table.setRowCount(0)
        is_admin = self.user_info.get("role") == "admin"
        
        for idx, s in enumerate(students):
            self.students_table.insertRow(idx)
            self.students_table.setItem(idx, 0, QTableWidgetItem(s.get("registration_number", "-")))
            self.students_table.setItem(idx, 1, QTableWidgetItem(s.get("full_name", "-")))
            self.students_table.setItem(idx, 2, QTableWidgetItem(s.get("class_name", "-")))

            student_email = s.get("email") or ""
            email_item = QTableWidgetItem(student_email if student_email else "No email")
            if not student_email or "@" not in student_email:
                email_item.setForeground(QColor("#9ca3af"))
                email_item.setToolTip("No student email registered")
            self.students_table.setItem(idx, 3, email_item)

            self.students_table.setItem(idx, 4, QTableWidgetItem(s.get("parent_name", "-")))
            self.students_table.setItem(idx, 5, QTableWidgetItem(s.get("parent_phone", "-")))

            parent_email = s.get("parent_email") or ""
            pemail_item = QTableWidgetItem(parent_email if parent_email else "No email")
            if not parent_email or "@" not in parent_email:
                pemail_item.setForeground(QColor("#9ca3af"))
                pemail_item.setToolTip("No parent email registered")
            self.students_table.setItem(idx, 6, pemail_item)

            self.students_table.setRowHeight(idx, 46)
            if is_admin:
                del_btn = QPushButton("🗑️ Remove")
                del_btn.setFixedSize(100, 32)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ef4444, stop:1 #dc2626);
                        color: #ffffff;
                        border: 1px solid #f87171;
                        border-bottom: 2px solid #b91c1c;
                        border-radius: 7px;
                        font-weight: 700;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #dc2626;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #991b1b;
                        background: #b91c1c;
                    }
                """)
                del_btn.clicked.connect(lambda checked=False, sid=s.get("id"): self.handle_delete_student(sid))

                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                btn_layout.addWidget(del_btn)
                self.students_table.setCellWidget(idx, 7, btn_widget)
            else:
                self.students_table.setItem(idx, 7, QTableWidgetItem("-"))

    def filter_students_table(self, query: str):
        q = query.strip().lower()
        for row in range(self.students_table.rowCount()):
            match = False
            for col in range(7):
                item = self.students_table.item(row, col)
                if item and q in item.text().lower():
                    match = True
                    break
            self.students_table.setRowHidden(row, not match)

    def refresh_students(self):
        try:
            students = api_client.get_students()
            self._populate_students_table(students)
        except Exception as e:
            logger.error(f"Failed to load student directory: {e}")

    def handle_delete_student(self, sid):
        reply = QMessageBox.question(self, 'Confirm Deletion', 
                                     'Are you sure you want to remove this student? This action is permanent.',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                api_client.delete_student(sid)
                QMessageBox.information(self, "Success", "Student has been removed.")
                self.refresh_students()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete student: {e}")

    def open_register_student_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Register Student Face Vector Node")
        dialog.setMinimumWidth(440)
        form_layout = QFormLayout(dialog)
        form_layout.setVerticalSpacing(12)

        reg_input = QLineEdit()
        reg_input.setPlaceholderText("Choose a username")
        username_layout = QHBoxLayout()
        username_layout.setContentsMargins(0, 0, 0, 0)
        username_suffix = QLabel("-tipsg")
        username_suffix.setStyleSheet("font-weight:700; color:#1e3a8a; padding: 0 8px;")
        username_layout.addWidget(reg_input)
        username_layout.addWidget(username_suffix)
        name_input = QLineEdit()
        course_combo = QComboBox()
        course_combo.addItems(["Data Science", "Cyber security", "AI/ML Engineer", "Software Developer", "Digital Market"])
        student_email_input = QLineEdit()
        student_email_input.setPlaceholderText("student@example.com")
        parent_name_input = QLineEdit()
        parent_phone_input = QLineEdit()
        parent_email_input = QLineEdit()
        
        photo_layout = QHBoxLayout()
        photo_label = QLineEdit()
        photo_label.setReadOnly(True)
        photo_label.setPlaceholderText("Select profile image file or capture live")
        captured_photo_bytes = None
        photo_btn = QPushButton("Browse")
        photo_btn.setProperty("class", "SecondaryBtn")
        photo_btn.setStyleSheet("QPushButton.SecondaryBtn { padding: 8px 14px; }")
        
        def choose_photo():
            nonlocal captured_photo_bytes
            file_path, _ = QFileDialog.getOpenFileName(dialog, "Select Profile Image", "", "Image Files (*.jpg *.jpeg *.png)")
            if file_path:
                captured_photo_bytes = None
                photo_label.setText(file_path)

        capture_btn = QPushButton("Take Photo")
        capture_btn.setProperty("class", "SecondaryBtn")
        capture_btn.setStyleSheet("QPushButton.SecondaryBtn { padding: 8px 14px; }")
        capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def take_photo():
            nonlocal captured_photo_bytes
            cb = capture_registration_photo(dialog)
            if cb:
                captured_photo_bytes = cb
                photo_label.setText("✓ Photo captured successfully")

        photo_btn.clicked.connect(choose_photo)
        capture_btn.clicked.connect(take_photo)
        photo_layout.addWidget(photo_label)
        photo_layout.addWidget(photo_btn)
        photo_layout.addWidget(capture_btn)

        form_layout.addRow("Student Username:", username_layout)
        form_layout.addRow("Full Name:", name_input)
        form_layout.addRow("Course:", course_combo)
        form_layout.addRow("Student Email:", student_email_input)
        form_layout.addRow("Parent Name:", parent_name_input)
        form_layout.addRow("Parent Phone:", parent_phone_input)
        form_layout.addRow("Parent Email:", parent_email_input)

        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Access Token Password:", password_input)

        confirm_password_input = QLineEdit()
        confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Confirm Verification Password:", confirm_password_input)
        form_layout.addRow("Biometric Source Image:", photo_layout)

        submit_btn = QPushButton("Extract Features & Commit Node")
        submit_btn.setProperty("class", "PrimaryBtn")
        submit_btn.setStyleSheet("QPushButton.PrimaryBtn")
        
        def handle_submit():
            if not all([reg_input.text(), name_input.text(), student_email_input.text(), parent_name_input.text(), parent_phone_input.text(), parent_email_input.text(), photo_label.text(), password_input.text(), confirm_password_input.text()]):
                QMessageBox.warning(dialog, "Warning", "Please completely resolve form requirements.")
                return
            if password_input.text() != confirm_password_input.text():
                QMessageBox.warning(dialog, "Warning", "Credential validation fail: Password mismatch.")
                return

            submit_btn.setEnabled(False)
            submit_btn.setText("Computing ArcFace Weight Mappings...")
            QApplication.processEvents()

            try:
                from frontend.onnx_face_service import onnx_face_service
                import json
                import math
                
                # Extract single sharp frontal embedding
                if captured_photo_bytes:
                    embedding_vector = onnx_face_service.extract_embedding(captured_photo_bytes)
                else:
                    embedding_vector = onnx_face_service.extract_embedding(photo_label.text())
                embedding_json = json.dumps(embedding_vector)

                # Anti-Duplicate Face Security Guard (Client & DB)
                try:
                    from src.database.connection import SessionLocal
                    from src.database.models import Student, FaceEmbedding
                    db_session = SessionLocal()
                    active_students = db_session.query(Student).filter(Student.is_active == True).all()
                    cand_norm = math.sqrt(sum(v * v for v in embedding_vector))
                    is_duplicate = False
                    matched_student_name = ""
                    matched_student_reg = ""
                    for st in active_students:
                        stored_rec = db_session.query(FaceEmbedding).filter(FaceEmbedding.student_id == st.id).first()
                        if not stored_rec or not stored_rec.embedding:
                            continue
                        stored_vec = stored_rec.embedding
                        if isinstance(stored_vec, str):
                            stored_vec = json.loads(stored_vec)
                        st_norm = math.sqrt(sum(v * v for v in stored_vec))
                        if st_norm > 0 and cand_norm > 0 and len(stored_vec) == len(embedding_vector):
                            sim = sum(a * b for a, b in zip(embedding_vector, stored_vec)) / (cand_norm * st_norm)
                            dist = max(0.0, min(2.0, 1.0 - sim))
                            if dist <= 0.49:
                                is_duplicate = True
                                matched_student_name = st.full_name
                                matched_student_reg = st.registration_number
                                break
                    db_session.close()
                    if is_duplicate:
                        QMessageBox.warning(
                            dialog,
                            "Duplicate Face Detected",
                            f"❌ Registration Blocked:\n\nThis face is already registered to student:\n'{matched_student_name}' ({matched_student_reg})\n\nEach student must register with their own unique face."
                        )
                        submit_btn.setEnabled(True)
                        submit_btn.setText("Extract Features & Commit Node")
                        return
                except Exception as dup_err:
                    logger.debug(f"Anti-duplicate check skipped: {dup_err}")

            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed local face feature extraction: {e}")
                submit_btn.setEnabled(True)
                submit_btn.setText("Extract Features & Commit Node")
                return

            data = {
                "registration_number": reg_input.text().strip(),
                "full_name": name_input.text().strip(),
                "class_name": course_combo.currentText(),
                "email": student_email_input.text().strip(),
                "parent_name": parent_name_input.text().strip(),
                "parent_phone": parent_phone_input.text().strip(),
                "parent_email": parent_email_input.text().strip() or "",
                "password": password_input.text().strip(),
                "embedding": embedding_json
            }
            photo_path = photo_label.text() if captured_photo_bytes is None else None
            
            try:
                result = api_client.register_student(data, photo_path=photo_path)
                QMessageBox.information(dialog, "Success", f"Student registered as: {result['registration_number']}")
                dialog.accept()
                self.refresh_students()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed face node extraction build: {e}")
                submit_btn.setEnabled(True)
                submit_btn.setText("Extract Features & Commit Node")

        submit_btn.clicked.connect(handle_submit)
        form_layout.addRow(submit_btn)
        dialog.exec()

    # --- Page 4: Scheduling Leaves Matrix ---
    def create_leaves_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        hdr = QHBoxLayout()
        role = self.user_info.get("role", "student")
        page_title = "My Leave Applications" if role == "student" else "Leave Management & Approvals"
        lbl = QLabel(page_title)
        lbl.setStyleSheet("font-size:16px; font-weight:700; color:#1e3a8a;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        student_btn_title = "+ Apply for Leave" if role == "student" else "+ Student Leave Request"
        student_leave_btn = QPushButton(student_btn_title)
        student_leave_btn.setObjectName("AddStudentLeaveBtn")
        student_leave_btn.setProperty("class", "PrimaryBtn")
        student_leave_btn.setStyleSheet("QPushButton.PrimaryBtn { font-weight: 700; padding: 10px 20px; font-size: 13px; }")
        student_leave_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        student_leave_btn.clicked.connect(self.open_student_leave_dialog)
        hdr.addWidget(student_leave_btn)

        if role != "student":
            staff_leave_btn = QPushButton("+ Staff Leave Request")
            staff_leave_btn.setObjectName("AddStaffLeaveBtn")
            staff_leave_btn.setProperty("class", "SecondaryBtn")
            staff_leave_btn.setStyleSheet("QPushButton.SecondaryBtn { padding: 10px 18px; font-size: 13px; }")
            staff_leave_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            staff_leave_btn.clicked.connect(self.open_staff_leave_dialog)
            hdr.addWidget(staff_leave_btn)
        layout.addLayout(hdr)

        self.leaves_table = QTableWidget()
        self.leaves_table.setColumnCount(9)
        self.leaves_table.setHorizontalHeaderLabels([
            "ID", "Applicant Type", "Applicant Name", "Leave Period", 
            "Leave Type", "Reason for Leave", "Supporting Doc", "Status", "Actions"
        ])
        
        header = self.leaves_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Applicant Type
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)      # Applicant Name
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)      # Leave Period
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Leave Type
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)          # Reason for Leave
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) # Supporting Doc
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents) # Status
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Interactive)      # Actions
        
        self.leaves_table.setColumnWidth(0, 50)
        self.leaves_table.setColumnWidth(1, 120)
        self.leaves_table.setColumnWidth(2, 170)
        self.leaves_table.setColumnWidth(3, 190)
        self.leaves_table.setColumnWidth(4, 110)
        self.leaves_table.setColumnWidth(6, 120)
        self.leaves_table.setColumnWidth(7, 110)
        self.leaves_table.setColumnWidth(8, 250)
        
        self.leaves_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.leaves_table.doubleClicked.connect(self.handle_table_row_double_click)
        layout.addWidget(self.leaves_table)

        self.stacked_pages.addWidget(page)

    def refresh_leaves(self):
        try:
            reqs = api_client.get_pending_leaves()
            self.populate_leaves_table(reqs)
        except Exception as e:
            logger.error(f"Exception framework synchronization fail: {e}")

    def populate_leaves_table(self, leaves_data):
        self.leaves_table.setRowCount(0)
        self.leaves_data_map = {lr.get("id"): lr for lr in leaves_data}
        
        # Calculate pending leave count and update the sidebar badge dot
        pending_count = sum(1 for lr in leaves_data if lr.get("status") in ["Pending", "FacultyApproved", "ManagerApproved"])
        self.update_leave_badge(pending_count)
        
        for idx, lr in enumerate(leaves_data):
            self.leaves_table.insertRow(idx)
            self.leaves_table.setItem(idx, 0, QTableWidgetItem(str(lr.get("id", "-"))))
            self.leaves_table.setItem(idx, 1, QTableWidgetItem(lr.get("applicant_type", "-").upper()))
            
            name = lr.get("student_name") if lr.get("applicant_type") == "student" else lr.get("teacher_name")
            self.leaves_table.setItem(idx, 2, QTableWidgetItem(name or "-"))
            
            dates = f"{lr.get('start_date', '-')} to {lr.get('end_date', '-')}"
            self.leaves_table.setItem(idx, 3, QTableWidgetItem(dates))
            self.leaves_table.setItem(idx, 4, QTableWidgetItem(lr.get("leave_type", "-")))
            
            # Col 5: Reason for Leave with Tooltip & Full Text Visibility
            reason_text = lr.get("reason", "-")
            reason_item = QTableWidgetItem(reason_text)
            reason_item.setToolTip(f"Full Reason for Leave:\n{reason_text}\n\n(Tip: Click 'Details' or double-click row for full view)")
            self.leaves_table.setItem(idx, 5, reason_item)
            
            # Supporting document column (Col 6)
            doc_path = lr.get("supporting_document")
            if doc_path:
                doc_btn = QPushButton("📄 Doc")
                doc_btn.setMinimumHeight(28)
                doc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                doc_btn.setStyleSheet("background-color: #2563eb; color: white; border-radius: 6px; font-weight:700; font-size:11px; padding: 3px 10px;")
                lid = lr.get("id")
                doc_btn.clicked.connect(lambda checked=False, leave_id=lid: self.handle_view_document(leave_id))
                doc_widget = QWidget()
                doc_layout = QHBoxLayout(doc_widget)
                doc_layout.setContentsMargins(2, 2, 2, 2)
                doc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                doc_layout.addWidget(doc_btn)
                self.leaves_table.setCellWidget(idx, 6, doc_widget)
            else:
                self.leaves_table.setItem(idx, 6, QTableWidgetItem("-"))
            
            # Verification State (Status) (Col 7)
            status_str = lr.get("status", "-")
            status_item = QTableWidgetItem(status_str)
            if status_str == "Approved":
                status_item.setForeground(QColor("#16a34a"))
            elif status_str == "Rejected":
                status_item.setForeground(QColor("#dc2626"))
            elif "Approved" in status_str:
                status_item.setForeground(QColor("#2563eb"))
            else:
                status_item.setForeground(QColor("#d97706"))
            self.leaves_table.setItem(idx, 7, status_item)
            self.leaves_table.setRowHeight(idx, 50)
            
            # Actions (Col 8)
            lid = lr.get("id")
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 4, 4, 4)
            btn_layout.setSpacing(6)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Details button
            details_btn = QPushButton("Details")
            details_btn.setMinimumHeight(30)
            details_btn.setMinimumWidth(64)
            details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            details_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155; 
                    color: #ffffff; 
                    border-radius: 6px; 
                    font-weight: 700; 
                    font-size: 11px; 
                    padding: 4px 8px;
                }
                QPushButton:hover { background-color: #1e293b; }
            """)
            details_btn.clicked.connect(lambda checked=False, leave_id=lid: self.show_leave_details_dialog(leave_id))
            btn_layout.addWidget(details_btn)

            if self.user_info.get("role") != "student":
                approve_btn = QPushButton("Approve")
                approve_btn.setMinimumHeight(30)
                approve_btn.setMinimumWidth(66)
                approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                approve_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #059669; 
                        color: #ffffff; 
                        border-radius: 6px; 
                        font-weight: 700; 
                        font-size: 11px; 
                        padding: 4px 8px;
                    }
                    QPushButton:hover { background-color: #047857; }
                """)
                approve_btn.clicked.connect(lambda checked=False, leave_id=lid: self.handle_approve_leave(leave_id))
                
                reject_btn = QPushButton("Reject")
                reject_btn.setMinimumHeight(30)
                reject_btn.setMinimumWidth(64)
                reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                reject_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dc2626; 
                        color: #ffffff; 
                        border-radius: 6px; 
                        font-weight: 700; 
                        font-size: 11px; 
                        padding: 4px 8px;
                    }
                    QPushButton:hover { background-color: #b91c1c; }
                """)
                reject_btn.clicked.connect(lambda checked=False, leave_id=lid: self.handle_reject_leave(leave_id))

                btn_layout.addWidget(approve_btn)
                btn_layout.addWidget(reject_btn)

            self.leaves_table.setCellWidget(idx, 8, btn_widget)

    def handle_table_row_double_click(self, index):
        row = index.row()
        item = self.leaves_table.item(row, 0)
        if item:
            try:
                lid = int(item.text())
                self.show_leave_details_dialog(lid)
            except ValueError:
                pass

    def show_leave_details_dialog(self, leave_id):
        lr = getattr(self, "leaves_data_map", {}).get(leave_id)
        if not lr:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Leave Application Details - Request #{leave_id}")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        
        # Header Info
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #f8fafc; border-radius: 8px; padding: 12px;")
        h_layout = QFormLayout(header_box)
        h_layout.setSpacing(8)
        
        name = lr.get("student_name") if lr.get("applicant_type") == "student" else lr.get("teacher_name")
        h_layout.addRow("Applicant Name:", QLabel(f"<b>{name or '-'}</b>"))
        h_layout.addRow("Applicant Type:", QLabel(lr.get("applicant_type", "-").upper()))
        h_layout.addRow("Leave Type:", QLabel(lr.get("leave_type", "-")))
        h_layout.addRow("Leave Period:", QLabel(f"{lr.get('start_date', '-')} to {lr.get('end_date', '-')}"))
        h_layout.addRow("Current Status:", QLabel(f"<b>{lr.get('status', '-')}</b>"))
        
        layout.addWidget(header_box)
        
        # Reason Box
        reason_label = QLabel("Student Reason for Leave:")
        reason_label.setStyleSheet("font-weight: 700; color: #1e293b;")
        layout.addWidget(reason_label)
        
        reason_view = QTextEdit()
        reason_view.setReadOnly(True)
        reason_view.setPlainText(lr.get("reason", "No reason specified."))
        reason_view.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; font-size: 13px;")
        reason_view.setMinimumHeight(100)
        layout.addWidget(reason_view)
        
        # Document preview section
        if lr.get("supporting_document"):
            doc_btn = QPushButton("📄 View Supported Document")
            doc_btn.setMinimumHeight(32)
            doc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            doc_btn.setStyleSheet("background-color: #3b82f6; color: white; font-weight: 700; border-radius: 6px;")
            doc_btn.clicked.connect(lambda: self.handle_view_document(leave_id))
            layout.addWidget(doc_btn)
        else:
            no_doc_lbl = QLabel("No supported document attached.")
            no_doc_lbl.setStyleSheet("color: #64748b; font-style: italic;")
            layout.addWidget(no_doc_lbl)
            
        # Decision Action buttons
        if self.user_info.get("role") != "student":
            actions_box = QHBoxLayout()
            actions_box.setSpacing(12)
            actions_box.setContentsMargins(0, 8, 0, 0)
            
            approve_btn = QPushButton("Approve Request")
            approve_btn.setMinimumHeight(38)
            approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            approve_btn.setStyleSheet("background-color: #059669; color: white; font-weight: 700; font-size: 13px; border-radius: 8px; padding: 8px 16px;")
            def on_approve():
                dialog.accept()
                self.handle_approve_leave(leave_id)
            approve_btn.clicked.connect(on_approve)
            
            reject_btn = QPushButton("Reject Request")
            reject_btn.setMinimumHeight(38)
            reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reject_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: 700; font-size: 13px; border-radius: 8px; padding: 8px 16px;")
            def on_reject():
                dialog.accept()
                self.handle_reject_leave(leave_id)
            reject_btn.clicked.connect(on_reject)
            
            actions_box.addWidget(approve_btn)
            actions_box.addWidget(reject_btn)
            layout.addLayout(actions_box)
            
        dialog.exec()

    def handle_view_document(self, lid):
        try:
            content, filename = api_client.get_leave_document(lid)
            temp_dir = tempfile.gettempdir()
            safe_filename = f"leave_doc_{lid}_{Path(filename).name}"
            temp_path = Path(temp_dir) / safe_filename
            with open(temp_path, "wb") as f:
                f.write(content)
            
            url = QUrl.fromLocalFile(str(temp_path))
            opened = QDesktopServices.openUrl(url)
            if not opened:
                os.startfile(str(temp_path))
        except Exception as e:
            logger.warning(f"Leave document view result for ID {lid}: {e}")
            msg = str(e)
            if "No supporting document" in msg or "404" in msg:
                QMessageBox.information(self, "Document Status", "No supporting document is attached to this request or it was already permanently deleted after review.")
            else:
                QMessageBox.critical(self, "Error", f"Could not open supported document: {e}")

    def handle_approve_leave(self, lid):
        try:
            api_client.approve_leave(lid)
            QMessageBox.information(self, "Success", "Leave request has been approved successfully.")
            self.refresh_leaves()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to approve leave: {e}")

    def handle_reject_leave(self, lid):
        try:
            api_client.reject_leave(lid)
            QMessageBox.warning(self, "Leave Rejected", "Leave request has been marked as rejected.")
            self.refresh_leaves()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reject leave: {e}")

    def open_student_leave_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Apply for Student Leave")
        dialog.setMinimumWidth(460)
        form = QFormLayout(dialog)
        form.setVerticalSpacing(14)

        role = self.user_info.get("role", "student")
        student_id = None

        if role == "student":
            student_label = QLabel(self.user_info.get("full_name", "-"))
            student_label.setStyleSheet("font-weight: 700; color: #1e3a8a; font-size: 13px;")
            form.addRow("Student Name:", student_label)
            student_id = self.user_info.get("id")
        else:
            student_combo = QComboBox()
            student_combo.setMinimumHeight(38)
            try:
                students = api_client.get_students()
                for s in students:
                    student_combo.addItem(f"{s['full_name']} ({s['registration_number']})", s["id"])
            except Exception:
                pass
            form.addRow("Select Student:", student_combo)

        start_input = QLineEdit(date.today().strftime("%Y-%m-%d"))
        start_input.setMinimumHeight(38)
        end_input = QLineEdit(date.today().strftime("%Y-%m-%d"))
        end_input.setMinimumHeight(38)
        reason_input = QTextEdit()
        reason_input.setPlaceholderText("Please specify the reason for leave...")
        reason_input.setMinimumHeight(90)

        doc_layout = QHBoxLayout()
        doc_label = QLineEdit()
        doc_label.setPlaceholderText("Optional attachment path")
        doc_label.setReadOnly(True)
        doc_label.setMinimumHeight(38)
        doc_btn = QPushButton("Browse")
        doc_btn.setProperty("class", "SecondaryBtn")
        doc_btn.setStyleSheet("QPushButton.SecondaryBtn { padding: 8px 16px; font-weight: 600; }")
        doc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        def choose_doc():
            f_path, _ = QFileDialog.getOpenFileName(dialog, "Select Supporting Document", "", "Documents (*.pdf *.png *.jpg *.jpeg *.doc *.docx);;All Files (*)")
            if f_path:
                doc_label.setText(f_path)
        
        doc_btn.clicked.connect(choose_doc)
        doc_layout.addWidget(doc_label)
        doc_layout.addWidget(doc_btn)

        form.addRow("Start Date (YYYY-MM-DD):", start_input)
        form.addRow("End Date (YYYY-MM-DD):", end_input)
        form.addRow("Reason for Leave:", reason_input)
        form.addRow("Supporting Document:", doc_layout)

        submit = QPushButton("Submit Leave Application")
        submit.setProperty("class", "PrimaryBtn")
        submit.setMinimumHeight(42)
        submit.setStyleSheet("QPushButton.PrimaryBtn { font-weight: 700; font-size: 13px; margin-top: 8px; }")
        submit.setCursor(Qt.CursorShape.PointingHandCursor)

        def on_submit():
            nonlocal student_id
            if role != "student":
                student_id = student_combo.currentData()
            if not student_id:
                QMessageBox.warning(dialog, "Warning", "Please select a student.")
                return

            if not reason_input.toPlainText().strip():
                QMessageBox.warning(dialog, "Warning", "Please provide a reason for the leave.")
                return

            try:
                api_client.submit_student_leave(
                    student_id, start_input.text().strip(), end_input.text().strip(), 
                    reason_input.toPlainText().strip(), doc_label.text().strip() or None
                )
                QMessageBox.information(dialog, "Success", "Leave request submitted successfully.")
                dialog.accept()
                self.refresh_leaves()
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, "response") and e.response is not None:
                    try:
                        err_msg = e.response.json().get("detail", err_msg)
                    except Exception:
                        pass
                QMessageBox.critical(dialog, "Leave Request Failed", f"{err_msg}")

        submit.clicked.connect(on_submit)
        form.addRow(submit)
        dialog.exec()

    def open_staff_leave_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Staff Leave Request")
        form = QFormLayout(dialog)
        form.setVerticalSpacing(12)

        t_id = 1 

        type_combo = QComboBox()
        type_combo.addItems(["Casual Leave Frame", "Sick Infrastructure Frame", "Half Frame Intermission"])
        
        start_input = QLineEdit(date.today().strftime("%Y-%m-%d"))
        end_input = QLineEdit(date.today().strftime("%Y-%m-%d"))
        reason_input = QTextEdit()

        form.addRow("Leave Array Class Tag:", type_combo)
        form.addRow("Start Boundary:", start_input)
        form.addRow("End Boundary:", end_input)
        form.addRow("Context Justification:", reason_input)

        submit = QPushButton("Deploy Application Package")
        submit.setProperty("class", "PrimaryBtn")
        submit.setStyleSheet("QPushButton.PrimaryBtn")

        def on_submit():
            try:
                api_client.submit_staff_leave(
                    t_id, type_combo.currentText(), start_input.text(), end_input.text(), reason_input.toPlainText()
                )
                QMessageBox.information(dialog, "Success", "Staff exception array committed.")
                dialog.accept()
                self.refresh_leaves()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Execution halt error: {e}")

        submit.clicked.connect(on_submit)
        form.addRow(submit)
        dialog.exec()

    # --- Page 5: Holidays Scheduler ---
    def create_holidays_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        hdr = QHBoxLayout()
        lbl = QLabel("Broadcast Invalidation & Global Closure Schedule")
        lbl.setStyleSheet("font-size:14px; font-weight:700; color:#94a3b8;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        add_btn = QPushButton("+ Inject Macro Holiday Parameter")
        add_btn.setObjectName("DeclareHolidayBtn")
        add_btn.setProperty("class", "PrimaryBtn")
        add_btn.setStyleSheet("QPushButton.PrimaryBtn")
        add_btn.clicked.connect(self.open_declare_holiday_dialog)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        self.holidays_table = QTableWidget()
        self.holidays_table.setColumnCount(3)
        self.holidays_table.setHorizontalHeaderLabels(["Global Date Target", "Event Label Descriptor", "Detailed Structural Purpose"])
        self.holidays_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.holidays_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.holidays_table)

        self.stacked_pages.addWidget(page)

    def refresh_holidays(self):
        try:
            hols = api_client.get_holidays()
            self.holidays_table.setRowCount(0)
            for idx, h in enumerate(hols):
                self.holidays_table.insertRow(idx)
                self.holidays_table.setItem(idx, 0, QTableWidgetItem(h["date"]))
                self.holidays_table.setItem(idx, 1, QTableWidgetItem(h["name"]))
                self.holidays_table.setItem(idx, 2, QTableWidgetItem(h["description"] or ""))
        except Exception as e:
            logger.error(f"Global scheduler map error: {e}")

    def open_declare_holiday_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Declare Institute Holiday & Push Email Alerts")
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)
        form.setVerticalSpacing(14)

        date_input = QDateEdit()
        date_input.setDate(QDate.currentDate())
        date_input.setCalendarPopup(True)
        date_input.setDisplayFormat("yyyy-MM-dd")

        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g. Independence Day, Diwali, Republic Day")
        desc_input = QTextEdit()
        desc_input.setPlaceholderText("Optional notes or instructions for students...")
        desc_input.setMaximumHeight(80)

        form.addRow("Holiday Date (YYYY-MM-DD):", date_input)
        form.addRow("Holiday / Event Name:", name_input)
        form.addRow("Notes / Description:", desc_input)

        info_lbl = QLabel("ℹ️ Declaring a holiday will automatically automark attendance and send SMTP announcement emails to all active students.")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("font-size:12px; color:#64748b; margin-top:4px;")
        form.addRow(info_lbl)

        submit = QPushButton("📢 Declare Holiday & Push Emails")
        submit.setProperty("class", "PrimaryBtn")
        submit.setStyleSheet("QPushButton.PrimaryBtn")

        def on_submit():
            holiday_date_str = date_input.date().toString("yyyy-MM-dd")
            if not name_input.text().strip():
                QMessageBox.warning(dialog, "Missing Information", "Please enter the Holiday Name.")
                return

            submit.setEnabled(False)
            submit.setText("Broadcasting Holiday Emails to Students...")
            QApplication.processEvents()

            try:
                api_client.create_holiday(name_input.text().strip(), holiday_date_str, desc_input.toPlainText().strip())
                QMessageBox.information(dialog, "Success", "Holiday declared successfully!\n\nAnnouncement emails and notifications have been triggered for all active students.")
                dialog.accept()
                self.refresh_holidays()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to declare holiday: {e}")
                submit.setEnabled(True)
                submit.setText("📢 Declare Holiday & Push Emails")

        submit.clicked.connect(on_submit)
        form.addRow(submit)
        dialog.exec()



    # --- Page 6: Monthly Reports & Exporter ---
    def create_reports_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        lbl = QLabel("Export & Download Monthly Attendance Reports")
        lbl.setStyleSheet("font-size:20px; font-weight:700; color:#0f172a;")
        layout.addWidget(lbl)

        sub_lbl = QLabel("Generate custom monthly reports or download automatically archived monthly attendance sheets.")
        sub_lbl.setStyleSheet("font-size:13px; color:#475569;")
        layout.addWidget(sub_lbl)

        form = QFormLayout()
        form.setVerticalSpacing(14)
        
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems([
            "Student Monthly Attendance Report",
            "Staff Operational Metrics Report"
        ])
        form.addRow("Report Type:", self.report_type_combo)

        self.year_combo = QComboBox()
        self.year_combo.addItems([str(y) for y in range(2025, 2031)])
        self.year_combo.setCurrentText(str(datetime.now().year))
        form.addRow("Year:", self.year_combo)

        self.month_combo = QComboBox()
        self.month_combo.addItems([
            "01 - January", "02 - February", "03 - March", "04 - April",
            "05 - May", "06 - June", "07 - July", "08 - August",
            "09 - September", "10 - October", "11 - November", "12 - December"
        ])
        self.month_combo.setCurrentIndex(max(0, datetime.now().month - 1))
        form.addRow("Month:", self.month_combo)

        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Excel Spreadsheet (.xlsx)",
            "PDF Document (.pdf)"
        ])
        form.addRow("Format:", self.format_combo)

        layout.addLayout(form)

        export_btn = QPushButton("📥 Download Selected Monthly Report")
        export_btn.setObjectName("DownloadReportBtn")
        export_btn.setMinimumHeight(46)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet("""
            QPushButton#DownloadReportBtn {
                background-color: #2563eb;
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                border-radius: 8px;
                padding: 10px 24px;
                border: none;
            }
            QPushButton#DownloadReportBtn:hover {
                background-color: #1d4ed8;
            }
        """)
        export_btn.clicked.connect(self.download_report_file)
        layout.addWidget(export_btn)

        # Archive section for available download files
        archive_heading = QLabel("Available Saved Monthly Reports Archive")
        archive_heading.setStyleSheet("font-size:17px; font-weight:700; color:#0f172a; margin-top:24px;")
        layout.addWidget(archive_heading)

        archive_desc = QLabel("Select any saved monthly report file from the table below and click 'Download' to save it to your device.")
        archive_desc.setStyleSheet("font-size:13px; color:#475569;")
        layout.addWidget(archive_desc)

        self.archived_reports_table = QTableWidget(0, 6)
        self.archived_reports_table.setHorizontalHeaderLabels([
            "Month / Period", "Available File", "Generated Date", "Rows Archived", "Download File", "Actions"
        ])
        self.archived_reports_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.archived_reports_table.verticalHeader().setVisible(False)
        self.archived_reports_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.archived_reports_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                color: #0f172a;
                gridline-color: #cbd5e1;
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #0f172a;
                font-weight: 700;
                font-size: 13px;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #cbd5e1;
                border-right: 1px solid #e2e8f0;
            }
            QTableWidget::item {
                color: #0f172a;
                padding: 8px;
            }
        """)
        layout.addWidget(self.archived_reports_table)

        refresh_archives_btn = QPushButton("🔄 Refresh Saved Monthly Reports")
        refresh_archives_btn.setMinimumHeight(40)
        refresh_archives_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_archives_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                font-size: 13px;
                font-weight: 600;
                border-radius: 8px;
                padding: 8px 18px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        refresh_archives_btn.clicked.connect(self.load_monthly_report_archives)
        layout.addWidget(refresh_archives_btn)

        if self.user_info.get("role") in ["admin", "teacher", "hr", "manager"]:
            self.load_monthly_report_archives()
        
        layout.addStretch()
        self.stacked_pages.addWidget(page)

    def download_report_file(self):
        target = "student" if "Student" in self.report_type_combo.currentText() else "staff"
        year = int(self.year_combo.currentText())
        month_raw = self.month_combo.currentText()
        month = int(month_raw.split(" - ")[0]) if " - " in month_raw else int(month_raw)
        fmt = "excel" if "Excel" in self.format_combo.currentText() else "pdf"

        ext = ".xlsx" if fmt == "excel" else ".pdf"
        default_name = f"{target}_monthly_{year}_{month:02d}{ext}"
        
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Monthly Report", default_name, f"Files (*{ext})")
        if not save_path:
            return

        try:
            content = api_client.download_report(target, year, month, fmt)
            with open(save_path, "wb") as f:
                f.write(content)
            QMessageBox.information(self, "Success", f"Monthly report saved successfully to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to download report: {e}")

    def load_monthly_report_archives(self):
        """Populate the report archives list with available download files."""
        if not hasattr(self, "archived_reports_table"):
            return
        if self.user_info.get("role") not in ["admin", "teacher", "hr", "manager"]:
            return
        try:
            reports = api_client.get_monthly_report_archives()
            self.populate_monthly_report_archives_table(reports)
        except Exception as e:
            logger.debug(f"Could not load monthly report archives: {e}")

    def populate_monthly_report_archives_table(self, reports: list):
        if not hasattr(self, "archived_reports_table"):
            return
        self.archived_reports_table.setRowCount(len(reports))
        is_admin = self.user_info.get("role") == "admin"

        for row, report in enumerate(reports):
            self.archived_reports_table.setRowHeight(row, 60)
            year = report["year"]
            month = report["month"]
            month_name = datetime(year, month, 1).strftime("%B %Y")
            filename = f"student_monthly_{year}_{month:02d}.xlsx"
            created_at = report["created_at"].replace("T", " ")[:19]
            rows_archived = str(report["attendance_rows_archived"])

            item_month = QTableWidgetItem(month_name)
            item_month.setForeground(QColor("#0f172a"))
            self.archived_reports_table.setItem(row, 0, item_month)

            item_file = QTableWidgetItem(filename)
            item_file.setForeground(QColor("#0f172a"))
            self.archived_reports_table.setItem(row, 1, item_file)

            item_created = QTableWidgetItem(created_at)
            item_created.setForeground(QColor("#0f172a"))
            self.archived_reports_table.setItem(row, 2, item_created)

            item_rows = QTableWidgetItem(rows_archived)
            item_rows.setForeground(QColor("#0f172a"))
            self.archived_reports_table.setItem(row, 3, item_rows)

            # Download Button Container (Column 4)
            download_btn = QPushButton("📥 Download Excel")
            download_btn.setFixedHeight(36)
            download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            download_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: 700;
                    border-radius: 6px;
                    padding: 4px 14px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
            download_btn.clicked.connect(
                lambda checked=False, archive_id=report["id"], label=month_name:
                self.download_monthly_report_archive(archive_id, label)
            )

            dl_widget = QWidget()
            dl_layout = QHBoxLayout(dl_widget)
            dl_layout.setContentsMargins(4, 4, 4, 4)
            dl_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dl_layout.addWidget(download_btn)
            self.archived_reports_table.setCellWidget(row, 4, dl_widget)

            # Actions / Remove Button (Column 5)
            if is_admin:
                remove_btn = QPushButton("🗑️ Remove")
                remove_btn.setFixedHeight(36)
                remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                remove_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ef4444;
                        color: #ffffff;
                        font-size: 13px;
                        font-weight: 700;
                        border-radius: 6px;
                        padding: 4px 14px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #dc2626;
                    }
                """)
                remove_btn.clicked.connect(
                    lambda checked=False, archive_id=report["id"], label=month_name:
                    self.remove_monthly_report_archive(archive_id, label)
                )

                rm_widget = QWidget()
                rm_layout = QHBoxLayout(rm_widget)
                rm_layout.setContentsMargins(4, 4, 4, 4)
                rm_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                rm_layout.addWidget(remove_btn)
                self.archived_reports_table.setCellWidget(row, 5, rm_widget)
            else:
                item_dash = QTableWidgetItem("-")
                item_dash.setForeground(QColor("#0f172a"))
                self.archived_reports_table.setItem(row, 5, item_dash)

    def download_monthly_report_archive(self, archive_id: int, month_name: str):
        default_name = f"student_monthly_{month_name.replace(' ', '_')}.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Monthly Attendance Report", default_name, "Excel Files (*.xlsx)"
        )
        if not save_path:
            return
        try:
            with open(save_path, "wb") as report_file:
                report_file.write(api_client.download_monthly_report_archive(archive_id))
            QMessageBox.information(self, "Saved", f"{month_name} report saved to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not download archived report: {e}")

    def remove_monthly_report_archive(self, archive_id: int, month_name: str):
        reply = QMessageBox.question(
            self, "Remove Saved Report",
            f"Remove the saved {month_name} report from the server?\n\nThis cannot restore the attendance rows already archived.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            api_client.delete_monthly_report_archive(archive_id)
            self.load_monthly_report_archives()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not remove archived report: {e}")

    # --- Page 7: Override & Application Settings Interface ---
    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 1. Icon & Desktop Shortcut System Card
        icon_card = QFrame()
        icon_card.setObjectName("IconToolsCard")
        icon_card.setStyleSheet("""
            QFrame#IconToolsCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        icon_card_layout = QVBoxLayout(icon_card)
        icon_card_layout.setSpacing(14)

        icon_hdr = QLabel("🎨 Application Icon & Desktop Shortcut Manager")
        icon_hdr.setStyleSheet("font-size: 16px; font-weight: 700; color: #1e3a8a;")
        icon_card_layout.addWidget(icon_hdr)

        icon_row = QHBoxLayout()
        icon_row.setSpacing(16)

        # Live icon pixmap preview
        icon_preview_lbl = QLabel()
        icon_pixmap = icon_manager.get_icon_pixmap(64)
        if not icon_pixmap.isNull():
            icon_preview_lbl.setPixmap(icon_pixmap)
        icon_preview_lbl.setFixedSize(64, 64)
        icon_preview_lbl.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 4px;")
        icon_row.addWidget(icon_preview_lbl)

        icon_info_layout = QVBoxLayout()
        icon_status_dict = icon_manager.verify_icon_status()
        self.icon_status_label = QLabel(
            f"<b>Icon File:</b> {icon_status_dict['filename']} "
            f"({'✓ Verified & Active' if icon_status_dict['found'] and icon_status_dict['is_valid'] else '⚠️ Missing'})<br>"
            f"<span style='color:#64748b; font-size:11px;'>Path: {icon_status_dict['path']}</span>"
        )
        self.icon_status_label.setStyleSheet("font-size: 13px; color: #334155;")
        icon_info_layout.addWidget(self.icon_status_label)

        icon_btn_row = QHBoxLayout()
        icon_btn_row.setSpacing(10)

        create_sc_btn = QPushButton("📌 Create Desktop Shortcut")
        create_sc_btn.setProperty("class", "PrimaryBtn")
        create_sc_btn.setStyleSheet("QPushButton.PrimaryBtn { font-size: 12px; padding: 8px 16px; }")
        create_sc_btn.clicked.connect(self.handle_create_desktop_shortcut)
        icon_btn_row.addWidget(create_sc_btn)

        check_icon_btn = QPushButton("🔍 Check Icon Integrity")
        check_icon_btn.setStyleSheet("background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; font-weight: 600; padding: 8px 14px; border-radius: 8px; font-size: 12px;")
        check_icon_btn.clicked.connect(self.handle_verify_icon_status)
        icon_btn_row.addWidget(check_icon_btn)
        icon_btn_row.addStretch()

        icon_info_layout.addLayout(icon_btn_row)
        icon_row.addLayout(icon_info_layout)
        icon_card_layout.addLayout(icon_row)
        layout.addWidget(icon_card)

        # 2. Manual State Override Section
        override_card = QFrame()
        override_card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        override_card_layout = QVBoxLayout(override_card)
        override_card_layout.setSpacing(14)

        lbl = QLabel("Manual State Override Interventions Control Panel")
        lbl.setStyleSheet("font-size:16px; font-weight:700; color:#1e3a8a;")
        override_card_layout.addWidget(lbl)

        form = QFormLayout()
        form.setVerticalSpacing(14)

        self.override_student_combo = QComboBox()
        if self.user_info.get("role") != "student":
            try:
                students = api_client.get_students()
                for s in students:
                    self.override_student_combo.addItem(f"{s['full_name']} ({s['registration_number']})", s["id"])
            except:
                pass
        form.addRow("Select Target Student:", self.override_student_combo)

        self.override_date = QLineEdit(date.today().strftime("%Y-%m-%d"))
        form.addRow("Target Attendance Date:", self.override_date)

        self.override_status = QComboBox()
        self.override_status.addItems(["Present", "Late", "Absent", "Leave", "Holiday"])
        form.addRow("New Attendance Status:", self.override_status)

        override_card_layout.addLayout(form)

        submit_btn = QPushButton("Save Attendance Override")
        submit_btn.setObjectName("OverrideSubmitBtn")
        submit_btn.setProperty("class", "PrimaryBtn")
        submit_btn.setStyleSheet("QPushButton.PrimaryBtn")
        submit_btn.clicked.connect(self.submit_manual_override)
        override_card_layout.addWidget(submit_btn)

        layout.addWidget(override_card)
        layout.addStretch()
        self.stacked_pages.addWidget(page)

    def handle_create_desktop_shortcut(self):
        success, msg, paths = icon_manager.create_desktop_shortcut()
        if success:
            QMessageBox.information(
                self,
                "Desktop Shortcut Created",
                f"✅ TIPS-G Attendance System shortcut created successfully!\n\n"
                f"Location:\n{paths[0] if paths else 'Desktop'}\n\n"
                f"You can now double-click the TIPS-G icon on your desktop to launch the app directly."
            )
        else:
            QMessageBox.warning(
                self,
                "Shortcut Creation",
                f"Could not create desktop shortcut:\n{msg}"
            )

    def handle_verify_icon_status(self):
        status = icon_manager.verify_icon_status()
        if status["found"] and status["is_valid"]:
            QMessageBox.information(
                self,
                "Icon Verification",
                f"✅ TIPS-G Application Icon is valid and active!\n\n"
                f"• File: {status['filename']}\n"
                f"• Path: {status['path']}\n"
                f"• Size: {status['size_bytes']:,} bytes\n"
                f"• Status: Loaded in Windows Shell & Qt Taskbar"
            )
        else:
            QMessageBox.warning(
                self,
                "Icon Verification",
                f"⚠️ Icon file not found or invalid at:\n{status['path']}\n\nPlease ensure TIPS-G-ALWAR.ico is present in the storage folder."
            )


    # --- Page 8: My Profile Layout & Edit Modal ---
    def create_profile_page(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 24, 30, 30)
        layout.setSpacing(20)

        # 1. Profile Header Neumorphic Card
        header_card = QFrame()
        header_card.setProperty("class", "Card")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(20)

        # Avatar Initial Icon
        self.profile_avatar = QLabel("ST")
        self.profile_avatar.setFixedSize(70, 70)
        self.profile_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_avatar.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #dbeafe, stop:1 #bfdbfe);
                color: #1e3a8a;
                font-size: 24px;
                font-weight: 800;
                border-radius: 35px;
                border: 2px solid #ffffff;
            }
        """)
        header_layout.addWidget(self.profile_avatar)

        # Name, Reg No & Verification Tag
        name_box = QVBoxLayout()
        name_box.setSpacing(4)

        self.profile_display_name = QLabel(self.user_info.get("full_name", "Student Name"))
        self.profile_display_name.setStyleSheet("font-size: 22px; font-weight: 800; color: #1e3a8a; letter-spacing: -0.5px;")

        meta_box = QHBoxLayout()
        meta_box.setSpacing(10)

        self.profile_display_username = QLabel(f"@{self.user_info.get('username', 'username')}")
        self.profile_display_username.setStyleSheet("font-size: 13px; font-weight: 700; color: #64748b;")

        self.profile_display_badge = QLabel("✓ Verified Student Account")
        self.profile_display_badge.setProperty("class", "VerifiedBadge")

        meta_box.addWidget(self.profile_display_username)
        meta_box.addWidget(self.profile_display_badge)
        meta_box.addStretch()

        name_box.addWidget(self.profile_display_name)
        name_box.addLayout(meta_box)
        header_layout.addLayout(name_box)
        header_layout.addStretch()

        # Edit Profile Action Button
        edit_profile_btn = QPushButton("✏️  Edit Profile")
        edit_profile_btn.setProperty("class", "PrimaryBtn")
        edit_profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_profile_btn.setStyleSheet("QPushButton.PrimaryBtn { padding: 12px 22px; font-size: 13px; }")
        edit_profile_btn.clicked.connect(self.open_edit_profile_dialog)
        header_layout.addWidget(edit_profile_btn)

        layout.addWidget(header_card)

        # 2. Key Information Grid Card
        info_grid_card = QFrame()
        info_grid_card.setProperty("class", "Card")
        info_grid_layout = QVBoxLayout(info_grid_card)
        info_grid_layout.setContentsMargins(24, 22, 24, 22)
        info_grid_layout.setSpacing(18)

        sec_lbl1 = QLabel("Academic & Contact Information")
        sec_lbl1.setStyleSheet("font-size: 15px; font-weight: 800; color: #1e3a8a; border-bottom: 1.5px solid #cbd5e1; padding-bottom: 8px;")
        info_grid_layout.addWidget(sec_lbl1)

        grid1 = QGridLayout()
        grid1.setHorizontalSpacing(24)
        grid1.setVerticalSpacing(14)

        def make_field_widget(label_text: str):
            c = QWidget()
            v = QVBoxLayout(c)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(4)
            l = QLabel(label_text)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;")
            val = QLabel("—")
            val.setStyleSheet("font-size: 14px; font-weight: 600; color: #1e293b; background: #dde4ee; border: 1px solid #c4d0e0; border-radius: 8px; padding: 8px 12px;")
            v.addWidget(l)
            v.addWidget(val)
            return c, val

        f_name_w, self.profile_view_fullname = make_field_widget("👤 Full Name")
        f_reg_w, self.profile_view_regno = make_field_widget("🆔 Registration Number / ID")
        f_course_w, self.profile_view_course = make_field_widget("🎓 Enrolled Course")
        f_email_w, self.profile_view_email = make_field_widget("📧 Student Email")
        f_phone_w, self.profile_view_phone = make_field_widget("📱 Student Phone")

        grid1.addWidget(f_name_w, 0, 0)
        grid1.addWidget(f_reg_w, 0, 1)
        grid1.addWidget(f_course_w, 1, 0)
        grid1.addWidget(f_email_w, 1, 1)
        grid1.addWidget(f_phone_w, 2, 0)

        info_grid_layout.addLayout(grid1)

        # Parent / Guardian Section
        sec_lbl2 = QLabel("Parent / Guardian Contact Information")
        sec_lbl2.setStyleSheet("font-size: 15px; font-weight: 800; color: #1e3a8a; border-bottom: 1.5px solid #cbd5e1; padding-bottom: 8px; margin-top: 10px;")
        info_grid_layout.addWidget(sec_lbl2)

        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(24)
        grid2.setVerticalSpacing(14)

        f_pname_w, self.profile_view_parent_name = make_field_widget("👨‍👩‍👧 Parent / Guardian Name")
        f_pphone_w, self.profile_view_parent_phone = make_field_widget("📞 Parent Phone Number")
        f_pemail_w, self.profile_view_parent_email = make_field_widget("✉️ Parent Email Address")
        f_sec_w, self.profile_view_security = make_field_widget("🔒 Biometric & Credentials")
        self.profile_view_security.setText("•••••••• (Encrypted & Active)")

        grid2.addWidget(f_pname_w, 0, 0)
        grid2.addWidget(f_pphone_w, 0, 1)
        grid2.addWidget(f_pemail_w, 1, 0)
        grid2.addWidget(f_sec_w, 1, 1)

        info_grid_layout.addLayout(grid2)
        layout.addWidget(info_grid_card)

        self.profile_status_label = QLabel("")
        self.profile_status_label.setWordWrap(True)
        self.profile_status_label.setStyleSheet("color: #064e3b; font-weight: 700; font-size: 13px;")
        layout.addWidget(self.profile_status_label)

        layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        self.stacked_pages.addWidget(page)

    def populate_profile_view(self, profile: dict):
        self._cached_profile = profile
        name = profile.get("full_name") or self.user_info.get("full_name") or "Student User"
        regno = profile.get("registration_number") or self.user_info.get("username") or ""
        email = profile.get("email") or self.user_info.get("email") or "—"
        phone = profile.get("phone") or "—"
        course = profile.get("class_name") or "—"
        pname = profile.get("parent_name") or "—"
        pphone = profile.get("parent_phone") or "—"
        pemail = profile.get("parent_email") or "—"

        self.profile_display_name.setText(name)
        self.profile_display_username.setText(f"@{regno}")

        words = name.strip().split()
        initials = (words[0][0] + words[-1][0]).upper() if len(words) > 1 else (name[:2].upper() if len(name) >= 2 else "ST")
        self.profile_avatar.setText(initials)

        self.profile_view_fullname.setText(name)
        self.profile_view_regno.setText(regno)
        self.profile_view_course.setText(course)
        self.profile_view_email.setText(email)
        self.profile_view_phone.setText(phone)
        self.profile_view_parent_name.setText(pname)
        self.profile_view_parent_phone.setText(pphone)
        self.profile_view_parent_email.setText(pemail)

    def open_edit_profile_dialog(self):
        profile = getattr(self, "_cached_profile", {}) or {}
        dialog = QDialog(self)
        dialog.setWindowTitle("✏️ Edit Profile Information")
        dialog.setMinimumWidth(500)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(24, 24, 24, 24)
        dialog_layout.setSpacing(16)

        title = QLabel("Edit Your Profile")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #1e3a8a;")
        dialog_layout.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        initial_email = (profile.get("email") or self.user_info.get("email") or "").strip().lower()
        full_name_in = QLineEdit(profile.get("full_name") or self.user_info.get("full_name") or "")
        email_in = QLineEdit(profile.get("email") or self.user_info.get("email") or "")
        phone_in = QLineEdit(profile.get("phone") or "")

        course_in = QComboBox()
        course_in.addItems(["Data Science", "Cyber security", "AI/ML Engineer", "Software Developer", "Digital Market"])
        curr_course = profile.get("class_name") or ""
        idx = course_in.findText(curr_course)
        if idx >= 0:
            course_in.setCurrentIndex(idx)
        elif curr_course:
            course_in.addItem(curr_course)
            course_in.setCurrentText(curr_course)

        pname_in = QLineEdit(profile.get("parent_name") or "")
        pphone_in = QLineEdit(profile.get("parent_phone") or "")
        pemail_in = QLineEdit(profile.get("parent_email") or "")

        pwd_in = QLineEdit()
        pwd_in.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_in.setPlaceholderText("Leave blank to keep current password")

        confirm_pwd_in = QLineEdit()
        confirm_pwd_in.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_pwd_in.setPlaceholderText("Confirm new password")

        photo_layout = QHBoxLayout()
        photo_label = QLineEdit()
        photo_label.setReadOnly(True)
        photo_label.setPlaceholderText("Keep current photo or select new")
        captured_bytes = None
        photo_path = None

        def choose_photo():
            nonlocal photo_path, captured_bytes
            fp, _ = QFileDialog.getOpenFileName(dialog, "Select Profile Image", "", "Image Files (*.jpg *.jpeg *.png)")
            if fp:
                photo_path = fp
                captured_bytes = None
                photo_label.setText(fp)

        def take_photo():
            nonlocal captured_bytes, photo_path
            cb = capture_registration_photo(dialog)
            if cb:
                captured_bytes = cb
                photo_path = None
                photo_label.setText("✓ Photo captured successfully")

        photo_btn = QPushButton("Browse")
        photo_btn.setProperty("class", "SecondaryBtn")
        photo_btn.clicked.connect(choose_photo)

        cam_btn = QPushButton("Capture")
        cam_btn.setProperty("class", "SecondaryBtn")
        cam_btn.clicked.connect(take_photo)

        photo_layout.addWidget(photo_label)
        photo_layout.addWidget(photo_btn)
        photo_layout.addWidget(cam_btn)

        form.addRow("Full Name:", full_name_in)
        form.addRow("Student Email:", email_in)
        form.addRow("Student Phone:", phone_in)
        form.addRow("Course / Branch:", course_in)
        form.addRow("Parent Name:", pname_in)
        form.addRow("Parent Phone:", pphone_in)
        form.addRow("Parent Email:", pemail_in)
        form.addRow("New Password:", pwd_in)
        form.addRow("Confirm Password:", confirm_pwd_in)
        form.addRow("Face Image:", photo_layout)

        dialog_layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "SecondaryBtn")
        cancel_btn.clicked.connect(dialog.reject)

        save_btn = QPushButton("💾  Save Changes")
        save_btn.setProperty("class", "PrimaryBtn")

        def handle_save():
            if pwd_in.text() and pwd_in.text() != confirm_pwd_in.text():
                QMessageBox.warning(dialog, "Validation Error", "Passwords do not match.")
                return
            if pwd_in.text() and len(pwd_in.text()) < 6:
                QMessageBox.warning(dialog, "Validation Error", "Password must be at least 6 characters.")
                return

            entered_email = email_in.text().strip().lower()
            target_email = entered_email or initial_email
            if not target_email or "@" not in target_email or "." not in target_email:
                QMessageBox.warning(dialog, "Email Required", "Please enter a valid email address for security verification.")
                return

            uname = (api_client.user_info or {}).get("username", "")

            # ── Step 1: Send Security Verification OTP ──
            save_btn.setEnabled(False)
            save_btn.setText("Sending Security OTP...")
            QApplication.processEvents()

            try:
                api_client.send_email_verification_otp(
                    email=target_email,
                    username=uname,
                    full_name=full_name_in.text().strip() or "Student"
                )
            except Exception as e:
                save_btn.setEnabled(True)
                save_btn.setText("💾  Save Changes")
                err_text = str(e)
                if "already registered" in err_text.lower():
                    QMessageBox.critical(dialog, "Email In Use", "This email address is already in use by another account.")
                else:
                    QMessageBox.critical(dialog, "OTP Failed", f"Could not send security verification OTP: {e}")
                return

            save_btn.setText("💾  Save Changes")
            save_btn.setEnabled(True)

            # ── Step 2: Prompt Student for OTP Code ──
            otp, ok = QInputDialog.getText(
                dialog,
                "Security Verification OTP",
                f"A 6-digit OTP has been sent to:\n{target_email}\n\nEnter the OTP code below to confirm and save your profile changes:"
            )
            if not ok or not otp.strip():
                QMessageBox.warning(dialog, "Update Cancelled", "Profile update was cancelled because OTP verification was not completed.")
                return

            # ── Step 3: Verify OTP ──
            try:
                res = api_client.verify_email_otp(email=target_email, otp=otp.strip(), username=uname)
                if not res.get("verified"):
                    QMessageBox.critical(dialog, "Verification Failed", "Invalid or expired OTP code.")
                    return
            except Exception as e:
                QMessageBox.critical(dialog, "Verification Failed", f"Invalid or expired OTP code: {e}")
                return

            data = {
                "full_name": full_name_in.text().strip(),
                "email": entered_email,
                "phone": phone_in.text().strip(),
                "parent_name": pname_in.text().strip(),
                "parent_phone": pphone_in.text().strip(),
                "parent_email": pemail_in.text().strip(),
                "class_name": course_in.currentText().strip(),
            }
            if pwd_in.text().strip():
                data["password"] = pwd_in.text().strip()

            save_btn.setEnabled(False)
            save_btn.setText("Saving Changes...")
            QApplication.processEvents()

            if captured_bytes or photo_path:
                try:
                    from frontend.onnx_face_service import onnx_face_service
                    import json
                    if captured_bytes:
                        emb = onnx_face_service.extract_embedding(captured_bytes)
                    else:
                        emb = onnx_face_service.extract_embedding(photo_path)
                    data["embedding"] = json.dumps(emb)
                except Exception as e:
                    QMessageBox.critical(dialog, "Embedding Error", f"Failed to extract face embedding: {e}")
                    save_btn.setEnabled(True)
                    save_btn.setText("💾  Save Changes")
                    return

            try:
                updated = api_client.update_my_profile(data, photo_path=photo_path, photo_bytes=captured_bytes)
                QMessageBox.information(dialog, "Success", "Profile updated successfully!")
                dialog.accept()
                self.load_page_content(7)
            except Exception as e:
                logger.warning(f"API update profile failed ({e}), attempting direct database commit...")
                try:
                    from src.database.connection import SessionLocal
                    from src.database.models import Student, FaceEmbedding
                    from src.backend.services.auth_service import get_password_hash
                    db = SessionLocal()
                    username = (api_client.user_info or {}).get("username", "")
                    s = db.query(Student).filter(Student.registration_number == username).first()
                    if not s and username.endswith("-tipsg"):
                        s = db.query(Student).filter(Student.registration_number == username[:-6]).first()
                    if s:
                        if data.get("full_name"): s.full_name = data["full_name"]
                        if data.get("email"): s.email = data["email"]
                        if data.get("phone"): s.phone = data["phone"]
                        if data.get("parent_name"): s.parent_name = data["parent_name"]
                        if data.get("parent_phone"): s.parent_phone = data["parent_phone"]
                        if data.get("parent_email"): s.parent_email = data["parent_email"]
                        if data.get("class_name"): s.class_name = data["class_name"]
                        if data.get("password"): s.hashed_password = get_password_hash(data["password"])
                        if "embedding" in data:
                            import json
                            emb = json.loads(data["embedding"])
                            db.query(FaceEmbedding).filter(FaceEmbedding.student_id == s.id).delete()
                            db.add(FaceEmbedding(student_id=s.id, embedding=emb))
                        db.commit()
                        db.close()
                        QMessageBox.information(dialog, "Success", "Profile updated successfully!")
                        dialog.accept()
                        self.load_page_content(8)
                        return
                    db.close()
                    raise ValueError(f"Student {username} not found in database.")
                except Exception as db_err:
                    QMessageBox.critical(dialog, "Error", f"Failed to update profile: {db_err}")
                    save_btn.setEnabled(True)
                    save_btn.setText("💾  Save Changes")

        save_btn.clicked.connect(handle_save)
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        dialog_layout.addLayout(btn_box)

        dialog.exec()

    def submit_manual_override(self):
        sid = self.override_student_combo.currentData()
        if not sid:
            QMessageBox.warning(self, "Warning", "Target unassigned.")
            return

        try:
            api_client.submit_manual_attendance(sid, self.override_status.currentText(), self.override_date.text())
            QMessageBox.information(self, "Success", "Vector state change committed into the target index layer safely.")
            self.refresh_dashboard()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed runtime tracking write override: {e}")

# ---------------------------------------------------------------------------

class StartupWorker(QThread):
    progress_changed = pyqtSignal(int, str)
    startup_finished = pyqtSignal(object)

    def run(self):
        try:
            self.progress_changed.emit(35, "Connecting to services...")
            
            # Fast restore of saved session
            restored_user = api_client.restore_session()

            self.progress_changed.emit(100, "Ready!")
            self.startup_finished.emit(restored_user)
        except Exception as e:
            logger.error(f"Startup worker encountered exception: {e}")
            self.startup_finished.emit(None)


class StartupSplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(540, 320)
        
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(geo.center().x() - 270, geo.center().y() - 160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.setSpacing(14)

        title_lbl = QLabel("TIPS-G ALWAR")
        title_lbl.setStyleSheet("font-size: 26px; font-weight: 800; color: #38bdf8; letter-spacing: 1px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("Student Attendance AI System")
        sub_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #94a3b8;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_lbl)

        layout.addStretch()

        self.status_label = QLabel("Initializing application...")
        self.status_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #cbd5e1;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #334155;
                border-radius: 5px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #2563eb);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        footer_lbl = QLabel("Powered by AI Face Recognition & Deep Learning")
        footer_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer_lbl)

        self.setStyleSheet("""
            QSplashScreen {
                background-color: #0f172a;
                border: 2px solid #3b82f6;
                border-radius: 16px;
            }
        """)

    @pyqtSlot(int, str)
    def update_progress(self, val: int, text: str):
        self.progress_bar.setValue(val)
        self.status_label.setText(text)
        QApplication.processEvents()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLE)
    
    # Set Windows app ID for proper taskbar icon display
    icon_manager.apply_to_app(app)

    # Show Splash Loading Window IMMEDIATELY on launch
    splash = StartupSplashScreen()
    splash.show()
    app.processEvents()

    main_win = None
    login_win = None

    def on_startup_finished(restored_user):
        nonlocal main_win, login_win
        splash.close()

        if restored_user:
            main_win = MainWindow(restored_user)
            main_win.setStyleSheet(MODERN_STYLE)
            main_win.showMaximized()
        else:
            login_win = LoginWindow()
            login_win.setStyleSheet(MODERN_STYLE)

            def on_login_success(user_info):
                nonlocal main_win
                main_win = MainWindow(user_info)
                main_win.setStyleSheet(MODERN_STYLE)
                main_win.showMaximized()
                login_win.close()

            login_win.login_success.connect(on_login_success)
            login_win.show()

    worker = StartupWorker()
    worker.progress_changed.connect(splash.update_progress)
    worker.startup_finished.connect(on_startup_finished)
    worker.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
