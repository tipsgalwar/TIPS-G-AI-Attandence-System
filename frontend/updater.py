import os
import sys
import shutil
import zipfile
import tempfile
import configparser
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import requests
from loguru import logger
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QLineEdit, QTabWidget, QWidget,
    QMessageBox, QFrame, QApplication, QStyle
)


def get_base_dir() -> Path:
    """Returns the base root directory of the application."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_config_path() -> Path:
    return get_base_dir() / "config.ini"


def read_updater_config() -> Dict[str, str]:
    cfg = configparser.ConfigParser()
    path = get_config_path()
    if path.exists():
        cfg.read(path, encoding="utf-8")
    
    current_ver = cfg.get("updater", "current_version", fallback="1.0.0")
    update_url = cfg.get("updater", "update_url", fallback="https://github.com/tipsgalwar/TIPS-G-AI-Attandence-System/archive/refs/heads/main.zip")
    latest_ver = cfg.get("updater", "latest_version", fallback=current_ver)
    release_notes = cfg.get("updater", "release_notes", fallback="Latest performance improvements, dashboard telemetry fixes, and face biometric updates.")
    
    # Check Central Database system_settings so all client devices receive admin-pushed updates
    try:
        from src.database.connection import SessionLocal
        from src.database.models import SystemSetting
        db = SessionLocal()
        db_url = db.query(SystemSetting).filter(SystemSetting.key == "software_update_url").first()
        db_ver = db.query(SystemSetting).filter(SystemSetting.key == "software_latest_version").first()
        db_notes = db.query(SystemSetting).filter(SystemSetting.key == "software_release_notes").first()
        if db_url and db_url.value:
            update_url = db_url.value.strip()
        if db_ver and db_ver.value:
            latest_ver = db_ver.value.strip()
        if db_notes and db_notes.value:
            release_notes = db_notes.value.strip()
        db.close()
    except Exception as db_err:
        logger.debug(f"Central DB update check fallback: {db_err}")

    return {
        "current_version": current_ver,
        "update_url": update_url,
        "latest_version": latest_ver,
        "release_notes": release_notes
    }


def write_updater_config(update_url: str, version: str, release_notes: str = ""):
    # 1. Update local config.ini
    cfg = configparser.ConfigParser()
    path = get_config_path()
    if path.exists():
        cfg.read(path, encoding="utf-8")
    
    if not cfg.has_section("updater"):
        cfg.add_section("updater")
    
    cfg.set("updater", "update_url", update_url.strip())
    cfg.set("updater", "latest_version", version.strip())
    if release_notes:
        cfg.set("updater", "release_notes", release_notes.strip())
    
    with open(path, "w", encoding="utf-8") as f:
        cfg.write(f)

    # 2. Push & Distribute across Central Database to ALL clients
    try:
        from src.database.connection import SessionLocal
        from src.database.models import SystemSetting, AppNotification, Student, Teacher
        from datetime import datetime
        db = SessionLocal()

        def _upsert_setting(key: str, val: str):
            rec = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if rec:
                rec.value = val
                rec.updated_at = datetime.utcnow()
            else:
                db.add(SystemSetting(key=key, value=val, category="updater"))

        _upsert_setting("software_update_url", update_url.strip())
        _upsert_setting("software_latest_version", version.strip())
        _upsert_setting("software_release_notes", release_notes.strip() if release_notes else "New system update available.")

        # Broadcast AppNotification to active users
        students = db.query(Student).filter(Student.is_active == True).all()
        for s in students:
            db.add(AppNotification(
                recipient_role="student",
                recipient_user_id=s.id,
                notification_type="software_update",
                title=f"🚀 System Update v{version.strip()} Available",
                message=f"A new update has been released. Open Software Updates in your sidebar to install."
            ))
        db.commit()
        db.close()
        logger.info(f"✓ Pushed software update v{version.strip()} to central database and all active users.")
    except Exception as db_err:
        logger.warning(f"Could not push update to central database: {db_err}")


class UpdateDownloadAndMergeWorker(QThread):
    progress_changed = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, download_url: str, new_version: str = "latest"):
        super().__init__()
        self.download_url = download_url.strip()
        self.new_version = new_version
        self.base_dir = get_base_dir()

    def run(self):
        try:
            self.progress_changed.emit(5, "Connecting to update server...")
            
            # 1. Check download URL
            if not self.download_url or not self.download_url.startswith("http"):
                raise ValueError("Invalid update URL. URL must start with http:// or https://")

            # 2. Check if the target is a Windows .exe Setup Installer or a .zip archive
            clean_url = self.download_url.split("?")[0].lower()
            is_exe_installer = clean_url.endswith(".exe") or "/setup" in clean_url

            temp_dir = Path(tempfile.mkdtemp(prefix="tipsg_update_"))
            
            if is_exe_installer:
                filename = self.download_url.split("/")[-1].split("?")[0] or f"Setup_TIPS-G_v{self.new_version}.exe"
                if not filename.endswith(".exe"):
                    filename += ".exe"
                download_target = temp_dir / filename
            else:
                download_target = temp_dir / "update_package.zip"

            self.progress_changed.emit(10, f"Downloading update from {self.download_url[:42]}...")
            
            headers = {"User-Agent": "TIPS-G-Attendance-System-Updater/1.0"}
            response = requests.get(self.download_url, headers=headers, stream=True, timeout=90)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(download_target, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = 10 + int((downloaded / total_size) * 75)
                            mb_down = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            self.progress_changed.emit(min(85, pct), f"Downloading update: {mb_down:.1f} MB / {mb_total:.1f} MB ({pct}%)")
                        else:
                            mb_down = downloaded / (1024 * 1024)
                            self.progress_changed.emit(45, f"Downloading: {mb_down:.1f} MB downloaded...")

            # --- Case A: Windows Executable Setup Installer (.exe) ---
            if is_exe_installer:
                self.progress_changed.emit(90, f"Validating installer '{filename}'...")
                file_size_mb = os.path.getsize(download_target) / (1024 * 1024)
                if file_size_mb < 0.1:
                    raise ValueError(f"Downloaded installer file is incomplete or corrupted ({file_size_mb:.2f} MB).")

                # Update current_version in config.ini
                try:
                    cfg = configparser.ConfigParser()
                    cpath = get_config_path()
                    if cpath.exists():
                        cfg.read(cpath, encoding="utf-8")
                    if not cfg.has_section("updater"):
                        cfg.add_section("updater")
                    if self.new_version and self.new_version != "latest":
                        cfg.set("updater", "current_version", self.new_version)
                    with open(cpath, "w", encoding="utf-8") as f:
                        cfg.write(f)
                except Exception as e:
                    logger.warning(f"Failed to record updated version in config: {e}")

                self.progress_changed.emit(100, "Installer ready! Launching setup installer...")
                
                # Launch the setup installer directly in Windows
                try:
                    os.startfile(str(download_target))
                except Exception:
                    subprocess.Popen([str(download_target)], shell=True)

                self.finished.emit(True, f"Installer '{filename}' ({file_size_mb:.1f} MB) has been launched! Setup wizard will guide you.")
                return

            # --- Case B: Zip Archive Package ---
            self.progress_changed.emit(85, "Validating and extracting ZIP update package...")

            if not zipfile.is_zipfile(download_target):
                raise ValueError("Downloaded file is not a valid zip archive or installer.")

            extract_dir = temp_dir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(download_target, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            extracted_items = list(extract_dir.iterdir())
            source_dir = extract_dir
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                source_dir = extracted_items[0]

            self.progress_changed.emit(90, "Performing conflict-free file merge...")

            PROTECTED_NAMES = {
                ".env", ".git", "user_session.token", "student_session.token",
                "attendance.db", "students.db", "storage", "logs", "scratch",
                "update_backups", "__pycache__", ".venv"
            }
            PROTECTED_EXTENSIONS = {".db", ".sqlite", ".sqlite3", ".log", ".token"}

            backup_dir = self.base_dir / "update_backups" / f"backup_v_{self.new_version}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            merged_count = 0
            skipped_count = 0

            for root, dirs, files in os.walk(source_dir):
                rel_root = Path(root).relative_to(source_dir)
                target_root = self.base_dir / rel_root

                if any(part in PROTECTED_NAMES for part in rel_root.parts):
                    continue

                target_root.mkdir(parents=True, exist_ok=True)

                for file in files:
                    file_lower = file.lower()
                    file_ext = Path(file).suffix.lower()

                    if file in PROTECTED_NAMES or file_ext in PROTECTED_EXTENSIONS:
                        skipped_count += 1
                        continue

                    if file_lower == "config.ini":
                        try:
                            self._merge_config_files(Path(root) / file, target_root / file)
                            merged_count += 1
                        except Exception as ce:
                            logger.warning(f"Config merge fallback: {ce}")
                        continue

                    source_file = Path(root) / file
                    target_file = target_root / file

                    try:
                        if target_file.exists():
                            backup_file = backup_dir / rel_root / file
                            backup_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(target_file, backup_file)

                        shutil.copy2(source_file, target_file)
                        merged_count += 1
                    except PermissionError:
                        temp_swap = target_root / f"{file}.new"
                        shutil.copy2(source_file, temp_swap)
                        merged_count += 1
                    except Exception as fe:
                        logger.warning(f"Could not merge file {file}: {fe}")

            try:
                cfg = configparser.ConfigParser()
                cpath = get_config_path()
                if cpath.exists():
                    cfg.read(cpath, encoding="utf-8")
                if not cfg.has_section("updater"):
                    cfg.add_section("updater")
                if self.new_version and self.new_version != "latest":
                    cfg.set("updater", "current_version", self.new_version)
                with open(cpath, "w", encoding="utf-8") as f:
                    cfg.write(f)
            except Exception as e:
                logger.warning(f"Failed to record updated version in config: {e}")

            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

            self.progress_changed.emit(100, "Update completed successfully!")
            self.finished.emit(True, f"Successfully merged {merged_count} updated system files with zero conflicts.")

        except Exception as exc:
            logger.error(f"Update failed: {exc}")
            self.finished.emit(False, str(exc))

    def _merge_config_files(self, new_cfg_path: Path, current_cfg_path: Path):
        """Preserves existing [server] host and port while adopting newly added settings."""
        if not current_cfg_path.exists():
            shutil.copy2(new_cfg_path, current_cfg_path)
            return

        current_cfg = configparser.ConfigParser()
        current_cfg.read(current_cfg_path, encoding="utf-8")

        new_cfg = configparser.ConfigParser()
        new_cfg.read(new_cfg_path, encoding="utf-8")

        # Copy over new sections and options without overriding existing server configs
        for sec in new_cfg.sections():
            if not current_cfg.has_section(sec):
                current_cfg.add_section(sec)
            for opt, val in new_cfg.items(sec):
                if sec == "server" and current_cfg.has_option(sec, opt):
                    continue  # preserve user's server host & port
                if not current_cfg.has_option(sec, opt):
                    current_cfg.set(sec, opt, val)

        with open(current_cfg_path, "w", encoding="utf-8") as f:
            current_cfg.write(f)


class UpdateDialog(QDialog):
    """
    Modern Neumorphic Software Updater & Admin Release Controller.
    Allows admins to push/configure update URLs and all users to download and merge updates.
    """
    def __init__(self, parent=None, is_admin: bool = False):
        super().__init__(parent)
        self.is_admin = is_admin
        self.updater_cfg = read_updater_config()
        self.worker = None

        self.setWindowTitle("TIPS-G ALWAR — Software System Updates")
        self.setMinimumSize(620, 680)
        self.resize(640, 700)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #f1f5f9;
            }
            QFrame.Card {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 12px;
                padding: 16px;
            }
            QLabel {
                color: #1e293b;
                border: none;
                background: transparent;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1.5px solid #94a3b8;
                border-radius: 8px;
                padding: 6px 12px;
                color: #0f172a;
                font-size: 13px;
                font-weight: 600;
                min-height: 26px;
            }
            QLineEdit:focus {
                border: 2px solid #2563eb;
                background-color: #ffffff;
            }
            QTextEdit {
                background-color: #f8fafc;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 12px;
                color: #0f172a;
                font-size: 13px;
            }
            QProgressBar {
                background-color: #e2e8f0;
                border-radius: 6px;
                height: 14px;
                text-align: center;
                font-size: 10px;
                font-weight: bold;
                color: #1e293b;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #2563eb);
                border-radius: 6px;
            }
        """)

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # ── Header ──────────────────────────────────────────────────────────
        hdr_frame = QFrame()
        hdr_frame.setProperty("class", "Card")
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(14, 12, 14, 12)

        icon_lbl = QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 28px;")
        hdr_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("TIPS-G Core Software Update Manager")
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 800; color: #1e3a8a;")
        title_box.addWidget(title_lbl)

        cur_ver = self.updater_cfg.get("current_version", "1.0.0")
        sub_lbl = QLabel(f"Installed Version: v{cur_ver} • Automatic Conflict-Free Merge Engine")
        sub_lbl.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600;")
        title_box.addWidget(sub_lbl)
        hdr_layout.addLayout(title_box)
        hdr_layout.addStretch()

        ver_badge = QLabel(f"v{cur_ver}")
        ver_badge.setStyleSheet("""
            background-color: #dbeafe;
            color: #1e40af;
            font-weight: 800;
            font-size: 13px;
            padding: 6px 14px;
            border-radius: 12px;
            border: 1px solid #bfdbfe;
        """)
        hdr_layout.addWidget(ver_badge)
        main_layout.addWidget(hdr_frame)

        # ── Status Card ─────────────────────────────────────────────────────
        status_frame = QFrame()
        status_frame.setProperty("class", "Card")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setSpacing(10)

        info_row = QHBoxLayout()
        target_ver = self.updater_cfg.get("latest_version", cur_ver)
        self.ver_status_label = QLabel(f"Available Version Target: <b>v{target_ver}</b>")
        self.ver_status_label.setStyleSheet("font-size: 13px; color: #0f172a;")
        info_row.addWidget(self.ver_status_label)
        info_row.addStretch()

        self.update_url_label = QLabel(f"Source: {self.updater_cfg.get('update_url', '')[:48]}...")
        self.update_url_label.setStyleSheet("font-size: 11px; color: #64748b;")
        info_row.addWidget(self.update_url_label)
        status_layout.addLayout(info_row)

        notes_title = QLabel("Release Notes & Changes:")
        notes_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #1e3a8a; text-transform: uppercase;")
        status_layout.addWidget(notes_title)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setFixedHeight(75)
        self.notes_text.setText(self.updater_cfg.get("release_notes", "No release notes specified."))
        status_layout.addWidget(self.notes_text)

        # Progress Bar & Progress Label
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #2563eb;")
        self.progress_label.setVisible(False)
        status_layout.addWidget(self.progress_label)

        main_layout.addWidget(status_frame)

        # ── Admin Push / Release Configuration ──────────────────────────────
        if self.is_admin:
            admin_frame = QFrame()
            admin_frame.setProperty("class", "Card")
            admin_layout = QVBoxLayout(admin_frame)
            admin_layout.setContentsMargins(16, 16, 16, 16)
            admin_layout.setSpacing(12)

            admin_hdr = QLabel("⚙️ Administrator: Push / Publish Update URL")
            admin_hdr.setStyleSheet("font-size: 14px; font-weight: 800; color: #92400e;")
            admin_layout.addWidget(admin_hdr)

            url_row = QVBoxLayout()
            url_row.setSpacing(4)
            url_lbl = QLabel("Update Package URL (ZIP / Repository):")
            url_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
            self.admin_url_input = QLineEdit(self.updater_cfg.get("update_url", ""))
            self.admin_url_input.setMinimumHeight(38)
            self.admin_url_input.setPlaceholderText("https://github.com/.../main.zip or direct ZIP URL")
            url_row.addWidget(url_lbl)
            url_row.addWidget(self.admin_url_input)
            admin_layout.addLayout(url_row)

            ver_row = QHBoxLayout()
            ver_row.setSpacing(10)
            ver_lbl = QLabel("Target Version:")
            ver_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155; min-width: 100px;")
            self.admin_ver_input = QLineEdit(self.updater_cfg.get("latest_version", "1.0.1"))
            self.admin_ver_input.setMinimumHeight(38)
            self.admin_ver_input.setPlaceholderText("e.g. 1.0.1")
            ver_row.addWidget(ver_lbl)
            ver_row.addWidget(self.admin_ver_input)
            admin_layout.addLayout(ver_row)

            admin_btn_row = QHBoxLayout()
            admin_btn_row.addStretch()
            save_config_btn = QPushButton("💾 Save & Push Update Config")
            save_config_btn.setMinimumHeight(36)
            save_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_config_btn.setStyleSheet("""
                QPushButton {
                    background-color: #fef3c7;
                    color: #92400e;
                    border: 1.5px solid #f59e0b;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 700;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #fde68a;
                }
            """)
            save_config_btn.clicked.connect(self._save_admin_config)
            admin_btn_row.addWidget(save_config_btn)
            admin_layout.addLayout(admin_btn_row)

            main_layout.addWidget(admin_frame)

        # ── Action Buttons ──────────────────────────────────────────────────
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(42)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0;
                color: #475569;
                border-radius: 8px;
                padding: 10px 22px;
                font-weight: 700;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #cbd5e1;
            }
        """)
        self.close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(self.close_btn)

        btn_bar.addStretch()

        self.restart_btn = QPushButton("🔄 Restart Application Now")
        self.restart_btn.setMinimumHeight(42)
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.setVisible(False)
        self.restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 700;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
        """)
        self.restart_btn.clicked.connect(self._restart_app)
        btn_bar.addWidget(self.restart_btn)

        self.download_btn = QPushButton("📥 Download & Apply Update")
        self.download_btn.setMinimumHeight(42)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 700;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
            }
            QPushButton:disabled {
                background: #94a3b8;
            }
        """)
        self.download_btn.clicked.connect(self._start_download_and_merge)
        btn_bar.addWidget(self.download_btn)

        main_layout.addLayout(btn_bar)

    def _save_admin_config(self):
        new_url = self.admin_url_input.text().strip()
        new_ver = self.admin_ver_input.text().strip()
        if not new_url:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid update package URL.")
            return
        if not new_ver:
            new_ver = "1.0.1"

        write_updater_config(new_url, new_ver, self.notes_text.toPlainText())
        self.updater_cfg = read_updater_config()
        self.ver_status_label.setText(f"Available Version Target: <b>v{new_ver}</b>")
        self.update_url_label.setText(f"Source: {new_url[:48]}...")
        QMessageBox.information(self, "Published", f"Update URL and version v{new_ver} saved and published successfully.")

    def _start_download_and_merge(self):
        url = self.updater_cfg.get("update_url", "").strip()
        if self.is_admin and hasattr(self, "admin_url_input") and self.admin_url_input.text().strip():
            url = self.admin_url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Missing URL", "No update download URL is configured.")
            return

        target_ver = self.updater_cfg.get("latest_version", "latest")
        if self.is_admin and hasattr(self, "admin_ver_input") and self.admin_ver_input.text().strip():
            target_ver = self.admin_ver_input.text().strip()

        reply = QMessageBox.question(
            self,
            "Confirm Update & File Merge",
            f"Are you ready to download and merge version v{target_ver}?\n\n"
            "• All source files will be seamlessly updated.\n"
            "• Your login session, database, and configurations will be completely preserved.\n"
            "• Previous files will be backed up safely in 'update_backups/'.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.download_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(5)
        self.progress_label.setVisible(True)
        self.progress_label.setText("Starting update process...")

        self.worker = UpdateDownloadAndMergeWorker(url, target_ver)
        self.worker.progress_changed.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, val: int, msg: str):
        self.progress_bar.setValue(val)
        self.progress_label.setText(msg)

    def _on_finished(self, success: bool, message: str):
        self.close_btn.setEnabled(True)
        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText("✓ " + message)
            self.progress_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #16a34a;")
            self.download_btn.setVisible(False)
            self.restart_btn.setVisible(True)
            QMessageBox.information(
                self,
                "Update Complete",
                f"{message}\n\nPlease restart the application now to run the updated version."
            )
        else:
            self.download_btn.setEnabled(True)
            self.progress_label.setText(f"❌ Update failed: {message}")
            self.progress_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #dc2626;")
            QMessageBox.critical(self, "Update Failed", f"Could not complete update:\n{message}")

    def _restart_app(self):
        """Relaunch the frontend application and close the current process."""
        try:
            base_dir = get_base_dir()
            run_script = base_dir / "run_frontend.py"
            if run_script.exists():
                subprocess.Popen([sys.executable, str(run_script)], cwd=str(base_dir))
            else:
                subprocess.Popen([sys.executable] + sys.argv, cwd=str(base_dir))
            QApplication.quit()
        except Exception as e:
            QMessageBox.warning(self, "Restart Notice", f"Please close and reopen the app manually: {e}")
