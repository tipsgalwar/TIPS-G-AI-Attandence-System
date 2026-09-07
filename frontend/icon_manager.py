"""
Icon Manager for TIPS-G ALWAR Application
Handles all icon loading, integrity verification, and Windows Desktop shortcut creation.
"""

import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path
from loguru import logger

# Optional PyQt6 imports for GUI vs CLI standalone compatibility
try:
    from PyQt6.QtGui import QIcon, QPixmap
    from PyQt6.QtWidgets import QApplication
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    class QIcon:
        def __init__(self, *args, **kwargs): pass
        def isNull(self): return False
    class QPixmap:
        def __init__(self, *args, **kwargs): pass
        def isNull(self): return True
    class QApplication:
        pass


# For Windows taskbar icon support
if sys.platform == "win32":
    try:
        import ctypes
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False


class IconManager:
    """Manages application icons, verification, and desktop shortcuts"""
    
    _instance = None
    _icon_cache = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IconManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize icon paths with multi-path discovery and auto-repair"""
        # Determine project root (handling both script and PyInstaller frozen runtime)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.project_root = Path(sys._MEIPASS)
        else:
            self.project_root = Path(__file__).resolve().parent.parent

        self.storage_dir = self.project_root / "storage"
        self.icon_path = self.storage_dir / "TIPS-G-ALWAR.ico"
        
        # Multi-location candidate discovery
        candidates = [
            self.storage_dir / "TIPS-G-ALWAR.ico",
            self.project_root / "TIPS-G-ALWAR.ico",
            self.storage_dir / "_TIPS-G ALWAR.ico",
            self.storage_dir / "_TIPS-G ALWAR.png",
            self.project_root / "TIPS-G-ALWAR.png",
        ]
        
        found_icon = None
        for cand in candidates:
            if cand.exists() and cand.stat().st_size > 0:
                found_icon = cand
                break

        if found_icon:
            self.icon_path = found_icon
            # Ensure root and storage copies exist so users browsing files always see the icon
            try:
                root_ico = self.project_root / "TIPS-G-ALWAR.ico"
                storage_ico = self.storage_dir / "TIPS-G-ALWAR.ico"
                if found_icon.suffix.lower() == ".ico":
                    if not storage_ico.exists() and self.storage_dir.exists():
                        shutil.copy2(found_icon, storage_ico)
                    if not root_ico.exists():
                        shutil.copy2(found_icon, root_ico)
            except Exception as e:
                logger.debug(f"Icon auto-sync skipped: {e}")
            logger.info(f"[ICON] Active application icon loaded: {self.icon_path}")
        else:
            logger.warning(f"[ICON] Application icon not found in search paths: {[str(c) for c in candidates]}")

    
    def verify_icon_status(self) -> dict:
        """
        Verifies icon integrity and returns diagnostic information.
        """
        exists = self.icon_path.exists() and self.icon_path.stat().st_size > 0
        size_bytes = self.icon_path.stat().st_size if exists else 0
        
        # Test loading into QIcon if Qt application context is available
        is_valid = exists and size_bytes > 0
        if PYQT6_AVAILABLE and QApplication.instance() is not None:
            icon = self.get_app_icon()
            if icon is not None and not icon.isNull():
                is_valid = True

        return {
            "found": exists,
            "path": str(self.icon_path.resolve()) if exists else "Missing",
            "size_bytes": size_bytes,
            "is_valid": is_valid,
            "filename": self.icon_path.name if exists else "None",
            "extension": self.icon_path.suffix if exists else ""
        }

    def get_app_icon(self) -> QIcon:
        """
        Get application main icon (used in task manager and window decorations)
        """
        if not PYQT6_AVAILABLE:
            return None
            
        if QApplication.instance() is None:
            return None

        if 'app_icon' not in self._icon_cache:
            if self.icon_path.exists():
                self._icon_cache['app_icon'] = QIcon(str(self.icon_path))
            else:
                self._icon_cache['app_icon'] = QIcon()
        
        return self._icon_cache.get('app_icon')

    
    def apply_to_app(self, app: QApplication) -> None:
        """
        Apply icon to QApplication and set Windows app ID for taskbar
        """
        icon = self.get_app_icon()
        if not icon.isNull():
            app.setWindowIcon(icon)
        self._set_windows_app_id_for_app()
    
    def _set_windows_app_id_for_app(self) -> None:
        """
        Set Windows app user model ID early for taskbar icon support
        """
        if not WINDOWS_AVAILABLE or sys.platform != "win32":
            return
        
        try:
            app_id = "TIPS-G-ALWAR.Student.Attendance.System"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            logger.debug(f"Windows app ID set: {app_id}")
        except Exception as e:
            logger.debug(f"Could not set Windows app ID: {e}")
    
    def apply_to_window(self, window) -> None:
        """
        Apply icon to a window
        """
        icon = self.get_app_icon()
        if not icon.isNull():
            window.setWindowIcon(icon)
            self._set_windows_app_id(window)
    
    def _set_windows_app_id(self, window) -> None:
        if not WINDOWS_AVAILABLE or sys.platform != "win32":
            return
        try:
            app_id = "TIPS-G-ALWAR.Student.Attendance.System"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception as e:
            logger.debug(f"Could not set Windows app ID: {e}")
    
    def apply_to_dialog(self, dialog) -> None:
        icon = self.get_app_icon()
        if not icon.isNull():
            dialog.setWindowIcon(icon)
    
    def get_icon_pixmap(self, size: int = 64) -> QPixmap:
        icon = self.get_app_icon()
        return icon.pixmap(size, size) if not icon.isNull() else QPixmap()
    
    def icon_path_str(self) -> str:
        return str(self.icon_path.resolve())

    def create_desktop_shortcut(
        self,
        shortcut_name: str = "TIPS-G Attendance System",
        include_start_menu: bool = True
    ) -> tuple:
        """
        Creates a native Windows shortcut (.lnk) with the TIPS-G icon on the user's Desktop
        and optionally in the Start Menu.

        Returns:
            (success: bool, message: str, created_paths: list)
        """
        if sys.platform != "win32":
            return False, "Desktop shortcuts are only supported on Windows.", []

        try:
            # 1. Determine target python executable (prefer pythonw.exe for no console window)
            venv_dir = self.project_root / ".venv"
            pythonw_exe = venv_dir / "Scripts" / "pythonw.exe"
            python_exe = venv_dir / "Scripts" / "python.exe"

            if pythonw_exe.exists():
                target_exe = str(pythonw_exe.resolve())
            elif python_exe.exists():
                target_exe = str(python_exe.resolve())
            else:
                # Fallback to current sys.executable
                curr_exe = Path(sys.executable)
                curr_w = curr_exe.parent / "pythonw.exe"
                target_exe = str(curr_w.resolve()) if curr_w.exists() else str(curr_exe.resolve())

            # 2. Target script and working directory
            script_path = str((self.project_root / "run_frontend.py").resolve())
            working_dir = str(self.project_root.resolve())
            icon_file = str(self.icon_path.resolve())

            # 3. Determine Desktop path
            desktop_path = None
            try:
                # Query Desktop path via PowerShell for reliable OneDrive/User desktop resolution
                cmd = 'powershell -NoProfile -Command "[Environment]::GetFolderPath(\'Desktop\')"'
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    desktop_path = Path(res.stdout.strip())
            except Exception:
                pass

            if not desktop_path or not desktop_path.exists():
                desktop_path = Path(os.environ.get("USERPROFILE", "")) / "Desktop"

            created_locations = []

            # 4. Generate VBScript to create the shortcut safely without quoting issues
            targets_to_create = []
            if desktop_path.exists():
                targets_to_create.append(desktop_path / f"{shortcut_name}.lnk")

            if include_start_menu:
                try:
                    cmd_sm = 'powershell -NoProfile -Command "[Environment]::GetFolderPath(\'Programs\')"'
                    res_sm = subprocess.run(cmd_sm, shell=True, capture_output=True, text=True, timeout=5)
                    if res_sm.returncode == 0 and res_sm.stdout.strip():
                        sm_dir = Path(res_sm.stdout.strip())
                        if sm_dir.exists():
                            targets_to_create.append(sm_dir / f"{shortcut_name}.lnk")
                except Exception:
                    pass

            vbs_commands = ['Set oWS = WScript.CreateObject("WScript.Shell")']
            for link_target in targets_to_create:
                resolved_link = str(link_target.resolve())
                vbs_commands.append(f'Set oLink = oWS.CreateShortcut("{resolved_link}")')
                vbs_commands.append(f'oLink.TargetPath = "{target_exe}"')
                vbs_commands.append(f'oLink.Arguments = "{script_path}"')
                vbs_commands.append(f'oLink.WorkingDirectory = "{working_dir}"')
                vbs_commands.append(f'oLink.IconLocation = "{icon_file}, 0"')
                vbs_commands.append('oLink.Description = "TIPS-G ALWAR Student Attendance System"')
                vbs_commands.append('oLink.Save')

            vbs_script = "\r\n".join(vbs_commands)
            with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False, encoding="utf-8") as tf:
                tf.write(vbs_script)
                temp_vbs_path = tf.name

            try:
                sub_res = subprocess.run(
                    ["cscript.exe", "//Nologo", temp_vbs_path],
                    capture_output=True,
                    timeout=10
                )
            finally:
                if os.path.exists(temp_vbs_path):
                    try:
                        os.remove(temp_vbs_path)
                    except Exception:
                        pass


            for t in targets_to_create:
                if t.exists():
                    created_locations.append(str(t))

            if created_locations:
                logger.info(f"[SUCCESS] Desktop shortcut created successfully at: {created_locations}")
                return True, f"Shortcut successfully created on your Desktop:\n{created_locations[0]}", created_locations
            else:
                return False, "Failed to generate shortcut file on Desktop.", []

        except Exception as e:
            logger.error(f"Failed to create desktop shortcut: {e}")
            return False, f"Error creating shortcut: {str(e)}", []
    
    @staticmethod
    def setup_application_icons(app: QApplication, main_window=None) -> None:
        """
        Set up all application icons in one call
        """
        manager = IconManager()
        manager.apply_to_app(app)
        if main_window:
            manager.apply_to_window(main_window)
        logger.info("[ICON] Application icons configured successfully")



# Export singleton instance
icon_manager = IconManager()

