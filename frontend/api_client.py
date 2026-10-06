import os
import sys
import json
import configparser
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


def _get_api_base_url() -> str:
    """
    Read backend URL from config.ini.
    Looks for config.ini next to the executable (PyInstaller) or project root (dev).
    Falls back to environment variables, then defaults.
    """
    # Determine base directory
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        base_dir = Path(sys.executable).parent
    else:
        # Running in development — project root (2 levels up from this file)
        base_dir = Path(__file__).resolve().parent.parent

    config_file = base_dir / "config.ini"
    config = configparser.ConfigParser()

    if config_file.exists():
        config.read(config_file)
        host = config.get("server", "host", fallback="127.0.0.1")
        port = config.get("server", "port", fallback="8000")
    else:
        # Fallback to environment variables
        host = os.getenv("BACKEND_HOST", "127.0.0.1")
        port = os.getenv("BACKEND_PORT", "8000")
        logger.warning(f"config.ini not found at {config_file}, using env/defaults: {host}:{port}")

    # 0.0.0.0 is a server bind address and invalid for client connections on Windows
    if host.strip() in ["0.0.0.0", "::", "0"]:
        host = "127.0.0.1"

    return f"http://{host}:{port}/api"


def _get_storage_dir() -> str:
    """
    Read storage directory from config.ini or environment variables, defaulting to 'storage'.
    Returns an absolute path string.
    """
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).resolve().parent.parent

    config_file = base_dir / "config.ini"
    config = configparser.ConfigParser()

    if config_file.exists():
        config.read(config_file)
        storage = config.get("app", "storage_dir", fallback="storage")
    else:
        storage = os.getenv("STORAGE_DIR", "storage")

    storage_path = Path(storage)
    if not storage_path.is_absolute():
        storage_path = base_dir / storage_path

    return str(storage_path)


from requests.adapters import HTTPAdapter


class APIClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIClient, cls).__new__(cls)
            cls._instance.base_url = _get_api_base_url()
            cls._instance.token = None
            cls._instance.user_info = {}
            cls._instance.session = requests.Session()
            adapter = HTTPAdapter(pool_connections=20, pool_maxsize=30, max_retries=1)
            cls._instance.session.mount("http://", adapter)
            cls._instance.session.mount("https://", adapter)
            logger.info(f"API Client initialized → {cls._instance.base_url}")
        return cls._instance

    def set_token(self, token: str):
        self.token = token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    @property
    def headers(self) -> Dict[str, str]:
        hdrs = {}
        if self.token:
            hdrs["Authorization"] = f"Bearer {self.token}"
        return hdrs

    def login(self, username: str, password: str) -> dict:
        """Authenticates with the API backend and sets the auth header token."""
        url = f"{self.base_url}/auth/login"
        data = {
            "username": username,
            "password": password
        }
        try:
            response = self.session.post(url, data=data, timeout=20)
            if response.status_code == 200:
                resp_json = response.json()
                self.set_token(resp_json["access_token"])
                self.user_info = {
                    "id": resp_json["id"],
                    "username": resp_json["username"],
                    "role": resp_json["role"],
                    "full_name": resp_json["full_name"]
                }
                self._save_session(self.token, self.user_info)
                logger.info(f"✓ Login successful for {self.user_info['username']} ({self.user_info['role']})")
                logger.debug(f"  Token set: {self.token[:20]}...")
                return {"status": "success", "user": self.user_info}
            else:
                detail = response.json().get("detail", "Invalid credentials")
                logger.error(f"✗ Login failed: {detail}")
                return {"status": "failed", "error": detail}
        except Exception as e:
            logger.error(f"API Client login failed: {e}")
            return {"status": "failed", "error": "Could not connect to FastAPI server."}

    @property
    def _session_file(self):
        storage_dir = _get_storage_dir()
        return os.path.join(storage_dir, "user_session.token")

    @property
    def _legacy_session_file(self):
        storage_dir = _get_storage_dir()
        return os.path.join(storage_dir, "student_session.token")

    def _save_session(self, token: str, user_info: dict = None):
        """Persist the bearer token and cached user profile for any authenticated user role."""
        try:
            os.makedirs(os.path.dirname(self._session_file), exist_ok=True)
            payload = {
                "token": token,
                "user_info": user_info or self.user_info or {}
            }
            with open(self._session_file, "w", encoding="utf-8") as session_file:
                json.dump(payload, session_file)
        except Exception as e:
            logger.warning(f"Could not persist session file: {e}")

    def _clear_saved_session(self):
        for path in [self._session_file, self._legacy_session_file]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def restore_session(self) -> Optional[dict]:
        """
        Restore a saved session for any authenticated user role.
        Never wipes valid sessions during app close/shutdown or temporary network drops.
        """
        token = None
        cached_user = None
        for path in [self._session_file, self._legacy_session_file]:
            try:
                with open(path, "r", encoding="utf-8") as session_file:
                    content = session_file.read().strip()
                    if content:
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict) and "token" in parsed:
                                token = parsed.get("token")
                                cached_user = parsed.get("user_info")
                            else:
                                token = content
                        except Exception:
                            token = content
                        break
            except FileNotFoundError:
                continue

        if not token:
            return None

        self.set_token(token)

        # 1. Ultra-fast path: If cached user profile exists, restore immediately with 0ms delay!
        if cached_user and isinstance(cached_user, dict) and cached_user.get("username"):
            self.user_info = cached_user
            logger.info(f"⚡ Instant session restore for {self.user_info.get('username')} ({self.user_info.get('role')})")
            
            # Non-blocking async background verification to sync any profile changes or token expiry
            def _async_verify():
                try:
                    response = self.session.get(f"{self.base_url}/auth/me", headers=self.headers, timeout=4)
                    if response.status_code == 200:
                        fresh_info = response.json()
                        self.user_info.update(fresh_info)
                        self._save_session(self.token, self.user_info)
                    elif response.status_code in [401, 403]:
                        logger.warning("Background session verification failed (token expired/revoked)")
                        self._clear_saved_session()
                except Exception:
                    pass
            import threading
            threading.Thread(target=_async_verify, daemon=True).start()
            return self.user_info

        # 2. Fast synchronous attempt if no cached user profile exists (2s timeout)
        try:
            response = self.session.get(f"{self.base_url}/auth/me", headers=self.headers, timeout=2.0)
            if response.status_code == 200:
                self.user_info = response.json()
                self._save_session(self.token, self.user_info)
                logger.info(f"✓ Restored verified session for {self.user_info.get('username')} ({self.user_info.get('role')})")
                return self.user_info
            elif response.status_code in [401, 403]:
                logger.warning(f"Saved session rejected by backend ({response.status_code})")
                self._clear_saved_session()
                self.set_token(None)
                self.user_info = {}
                return None
        except Exception as e:
            logger.warning(f"Backend verification network hiccup: {e}")

        # 3. Direct DB verification fallback if database is locally reachable
        try:
            from src.database.connection import SessionLocal
            from src.database.models import Student, Teacher, Admin
            import jwt
            from src.core.config import settings
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
            sub = payload.get("sub")
            role = payload.get("role", "student")
            db = SessionLocal()
            user_obj = None
            if role == "student":
                user_obj = db.query(Student).filter(Student.registration_number == sub).first()
            elif role in ["teacher", "manager", "hr"]:
                user_obj = db.query(Teacher).filter(Teacher.username == sub).first()
            else:
                user_obj = db.query(Admin).filter(Admin.username == sub).first()
            if user_obj:
                self.user_info = {
                    "id": user_obj.id,
                    "username": getattr(user_obj, "registration_number", getattr(user_obj, "username", sub)),
                    "role": role,
                    "full_name": user_obj.full_name
                }
                self._save_session(token, self.user_info)
                db.close()
                logger.info(f"✓ Restored session via DB verification for {self.user_info['username']}")
                return self.user_info
            db.close()
        except Exception as db_err:
            logger.debug(f"Direct DB session verification: {db_err}")

        if cached_user:
            self.user_info = cached_user
            return self.user_info

        return None

    # Aliases for backward compatibility
    def _save_student_session(self, token: str):
        self._save_session(token)

    def _clear_saved_student_session(self):
        self._clear_saved_session()

    def restore_student_session(self) -> Optional[dict]:
        return self.restore_session()

    def logout(self):
        try:
            if self.token:
                self.session.post(f"{self.base_url}/auth/logout", headers=self.headers, timeout=10)
        except requests.RequestException as error:
            logger.warning(f"Could not revoke server session during logout: {error}")
        self._clear_saved_session()
        self.set_token(None)
        self.user_info = {}

    def forgot_password(self, username: str, new_password: str) -> dict:
        url = f"{self.base_url}/auth/forgot-password"
        response = self.session.post(url, json={"username": username, "new_password": new_password}, timeout=10)
        response.raise_for_status()
        return response.json()

    def request_password_reset(self, username: str) -> dict:
        url = f"{self.base_url}/auth/request-password-reset"
        response = self.session.post(url, json={"username": username}, timeout=10)
        response.raise_for_status()
        return response.json()

    def verify_password_reset(self, username: str, otp: str, new_password: str) -> dict:
        url = f"{self.base_url}/auth/verify-password-reset"
        response = self.session.post(url, json={"username": username, "otp": otp, "new_password": new_password}, timeout=10)
        response.raise_for_status()
        return response.json()

    def verify_otp_only(self, username: str, otp: str) -> dict:
        """Check that an OTP is valid WITHOUT changing the password.
        Raises an HTTPError if the OTP is invalid or expired."""
        url = f"{self.base_url}/auth/check-otp"
        response = self.session.post(url, json={"username": username, "otp": otp}, timeout=10)
        response.raise_for_status()
        return response.json()

    def send_email_verification_otp(self, email: str, username: Optional[str] = None, full_name: Optional[str] = None) -> dict:
        """Request a 6-digit OTP sent to a Gmail/email address."""
        url = f"{self.base_url}/auth/send-verification-otp"
        payload = {"email": email}
        if username:
            payload["username"] = username
        if full_name:
            payload["full_name"] = full_name
        response = self.session.post(url, json=payload, timeout=12)
        response.raise_for_status()
        return response.json()

    def verify_email_otp(self, email: str, otp: str, username: Optional[str] = None) -> dict:
        """Verify the 6-digit OTP code sent to the email."""
        url = f"{self.base_url}/auth/verify-email-otp"
        payload = {"email": email, "otp": otp}
        if username:
            payload["username"] = username
        response = self.session.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_summary(self, target_date: Optional[str] = None) -> dict:
        if not self.token:
            return {}
        url = f"{self.base_url}/reports/summary"
        params = {"target_date": target_date} if target_date else {}
        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=5)
            if response.status_code in [401, 403]:
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"get_summary API call fallback: {e}")
            return {}

    def get_students(self) -> List[dict]:
        url = f"{self.base_url}/students/"
        response = self.session.get(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return response.json()

    def delete_student(self, student_id: int) -> dict:
        url = f"{self.base_url}/students/{student_id}"
        response = self.session.delete(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return {"status": "success"}

    def add_student(self, data: dict, photo_path: str) -> dict:
        url = f"{self.base_url}/students/"
        # Read file
        with open(photo_path, "rb") as f:
            files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
            response = self.session.post(url, data=data, files=files, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()

    def register_student(self, data: dict, photo_path: Optional[str] = None) -> dict:
        url = f"{self.base_url}/students/self-register"
        if photo_path:
            with open(photo_path, "rb") as f:
                files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
                response = self.session.post(url, data=data, files=files, timeout=120)
        else:
            files = {"photo": ("", b"", "application/octet-stream")}
            response = self.session.post(url, data=data, files=files, timeout=120)

        if not response.ok:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            if detail:
                raise requests.HTTPError(detail, response=response)
        response.raise_for_status()
        return response.json()

    def get_daily_attendance(self, target_date: Optional[str] = None) -> List[dict]:
        if not self.token:
            return []
        url = f"{self.base_url}/attendance/daily"
        params = {"target_date": target_date} if target_date else {}
        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=5)
            if response.status_code in [401, 403, 404]:
                return []
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"get_daily_attendance API call fallback: {e}")
            return []

    def get_my_profile(self) -> dict:
        url = f"{self.base_url}/students/me"
        try:
            response = self.session.get(url, headers=self.headers, timeout=3)
            if response.status_code in [401, 403]:
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"get_my_profile API call: {e}")
            return {}

    def update_my_profile(self, data: dict, photo_path: Optional[str] = None, photo_bytes: Optional[bytes] = None) -> dict:
        url = f"{self.base_url}/students/me"
        files = {}
        if photo_bytes is not None:
            files = {"photo": ("profile.jpg", photo_bytes, "image/jpeg")}
            response = self.session.put(url, data=data, files=files, headers=self.headers, timeout=120)
        elif photo_path and os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
                response = self.session.put(url, data=data, files=files, headers=self.headers, timeout=120)
        else:
            files = {"photo": ("", b"", "application/octet-stream")}
            response = self.session.put(url, data=data, files=files, headers=self.headers, timeout=120)
        response.raise_for_status()
        return response.json()

    def submit_manual_attendance(self, student_id: int, status_str: str, date_str: str) -> dict:
        url = f"{self.base_url}/attendance/manual"
        payload = {
            "student_id": student_id,
            "date": date_str,
            "status": status_str,
            "verification_method": "Manual Override"
        }
        response = self.session.post(url, json=payload, headers=self.headers, timeout=5)
        response.raise_for_status()
        return response.json()

    def get_student_embedding(self, student_id: int) -> dict:
        """Fetch a specific student's face embedding. Requires teacher/admin token."""
        url = f"{self.base_url}/attendance/student-embedding/{student_id}"
        response = self.session.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def submit_admin_face_attendance(self, student_id: int, confidence: float, bssid: str, candidate_embedding: list) -> dict:
        """Admin-assisted face attendance — marks attendance for a specific student
        using the admin's camera after face verification against the student's stored embedding."""
        url = f"{self.base_url}/attendance/admin-verify"
        payload = {
            "student_id": student_id,
            "confidence": confidence,
            "bssid": bssid,
            "candidate_embedding": candidate_embedding,
        }
        response = self.session.post(url, json=payload, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def trigger_absence_scan(self, date_str: Optional[str] = None) -> dict:
        url = f"{self.base_url}/attendance/trigger-scan"
        params = {"target_date": date_str} if date_str else {}
        response = self.session.post(url, params=params, headers=self.headers, timeout=60)
        response.raise_for_status()
        return response.json()

    def get_holidays(self) -> List[dict]:
        url = f"{self.base_url}/holidays/"
        response = self.session.get(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return response.json()

    def create_holiday(self, name: str, date_str: str, description: str = "") -> dict:
        url = f"{self.base_url}/holidays/"
        payload = {
            "name": name,
            "date": date_str,
            "description": description
        }
        response = self.session.post(url, json=payload, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_notifications(self, unread_only: bool = False) -> List[dict]:
        response = self.session.get(
            f"{self.base_url}/notifications/",
            params={"unread_only": unread_only},
            headers=self.headers,
            timeout=5,
        )
        response.raise_for_status()
        return response.json()

    def mark_notification_read(self, notification_id: int) -> None:
        response = self.session.post(
            f"{self.base_url}/notifications/{notification_id}/read",
            headers=self.headers,
            timeout=5,
        )
        response.raise_for_status()

    def submit_student_leave(self, student_id: int, start_date: str, end_date: str, reason: str, doc_path: Optional[str] = None) -> dict:
        url = f"{self.base_url}/leaves/student"
        data = {
            "student_id": student_id,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason
        }
        files = {}
        if doc_path and os.path.exists(doc_path):
            f = open(doc_path, "rb")
            files = {"document": (os.path.basename(doc_path), f, "application/octet-stream")}
            
        try:
            response = self.session.post(url, data=data, files=files, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        finally:
            if files:
                files["document"][1].close()

    def submit_staff_leave(self, teacher_id: int, leave_type: str, start_date: str, end_date: str, reason: str) -> dict:
        url = f"{self.base_url}/leaves/staff"
        data = {
            "teacher_id": teacher_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason
        }
        response = self.session.post(url, data=data, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_pending_leaves(self) -> List[dict]:
        url = f"{self.base_url}/leaves/pending"
        response = self.session.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_leave_document(self, leave_id: int) -> tuple:
        """Fetches the supporting document binary content and suggested filename."""
        url = f"{self.base_url}/leaves/{leave_id}/document"
        try:
            response = self.session.get(url, headers=self.headers, timeout=15)
            if response.status_code == 404:
                raise RuntimeError("No supporting document attached to this request or it was permanently deleted post-review.")
            response.raise_for_status()
            
            cd = response.headers.get("Content-Disposition", "")
            filename = f"leave_doc_{leave_id}.pdf"
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"\'')
            return response.content, filename
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                raise RuntimeError("No supporting document attached to this request or it was permanently deleted post-review.")
            raise e

    def approve_leave(self, leave_id: int) -> dict:
        url = f"{self.base_url}/leaves/{leave_id}/approve"
        response = self.session.post(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def reject_leave(self, leave_id: int) -> dict:
        url = f"{self.base_url}/leaves/{leave_id}/reject"
        response = self.session.post(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def download_report(self, target_type: str, year: int, month: int, format_str: str) -> bytes:
        """Downloads Student or Staff reports as bytes."""
        url = f"{self.base_url}/reports/monthly/{target_type}"
        params = {
            "year": year,
            "month": month,
            "export_format": format_str
        }
        response = self.session.get(url, params=params, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.content

    def get_monthly_report_archives(self) -> List[dict]:
        response = self.session.get(f"{self.base_url}/reports/archives", headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def download_monthly_report_archive(self, archive_id: int) -> bytes:
        response = self.session.get(
            f"{self.base_url}/reports/archives/{archive_id}/download",
            headers=self.headers,
            timeout=30
        )
        response.raise_for_status()
        return response.content

    def delete_monthly_report_archive(self, archive_id: int) -> None:
        response = self.session.delete(
            f"{self.base_url}/reports/archives/{archive_id}",
            headers=self.headers,
            timeout=15
        )
        response.raise_for_status()

    def submit_verified_attendance(self, confidence: float, bssid: str, candidate_embedding: List[float]) -> dict:
        """
        Sends verified face data and the candidate embedding to the backend for authoritative attendance recording.
        """
        url = f"{self.base_url}/attendance/verify"
        data = {
            "confidence": confidence,
            "bssid": bssid,
            "candidate_embedding": candidate_embedding
        }
        
        try:
            response = self.session.post(
                url, 
                json=data,
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"Face verification API error: {e}")
            return {
                "status": "failed",
                "error": f"API verification unavailable: {e}"
            }

    def get_my_embedding(self) -> dict:
        """Retrieves the logged-in student's registered face embedding."""
        if not self.token:
            return {}
        url = f"{self.base_url}/attendance/my-embedding"
        try:
            response = self.session.get(url, headers=self.headers, timeout=5)
            if response.status_code in [401, 403, 404]:
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"get_my_embedding API call fallback: {e}")
            return {}

    def get_noticeboard_holidays(self):
        response = self.session.get(
            f"{self.base_url}/noticeboard/holidays",
            headers=self.headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_student_monthly_analytics(self, student_id: int = None, month: int = None, year: int = None) -> dict:
        """Retrieves monthly attendance statistics, calendar data, and annual trends for student."""
        params = {}
        if student_id: params["student_id"] = student_id
        if month: params["month"] = month
        if year: params["year"] = year
        try:
            response = self.session.get(
                f"{self.base_url}/attendance/student/monthly-analytics",
                params=params,
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"HTTP monthly analytics fetch failed ({e}), attempting direct DB calculation fallback...")
            try:
                import calendar
                from datetime import date, datetime
                from src.database.connection import SessionLocal
                from src.database.models import Student, Attendance, Holiday
                
                now_dt = datetime.now()
                target_month = month or now_dt.month
                target_year = year or now_dt.year
                target_sid = student_id or (self.user_info.get("id") if self.user_info else None)

                db = SessionLocal()
                student = None
                if target_sid:
                    student = db.query(Student).filter(Student.id == target_sid).first()

                if not student and self.user_info:
                    uname = (self.user_info.get("username") or self.user_info.get("registration_number") or "").strip()
                    if uname:
                        student = db.query(Student).filter(
                            (Student.registration_number == uname) |
                            (Student.registration_number == f"{uname}-tipsg") |
                            (Student.email == uname)
                        ).first()
                        if student:
                            target_sid = student.id

                if not student or not target_sid:
                    db.close()
                    return {}

                num_days = calendar.monthrange(target_year, target_month)[1]
                start_d = date(target_year, target_month, 1)
                end_d = date(target_year, target_month, num_days)

                records = db.query(Attendance).filter(
                    Attendance.student_id == target_sid,
                    Attendance.date >= start_d,
                    Attendance.date <= end_d
                ).all()
                record_map = {}
                for r in records:
                    record_map[str(r.date)] = r
                    record_map[r.date] = r

                holidays = db.query(Holiday).filter(
                    Holiday.date >= start_d,
                    Holiday.date <= end_d
                ).all()
                holiday_map = {str(h.date): h.name for h in holidays}
                for h in holidays:
                    holiday_map[h.date] = h.name

                total_working_days = 0
                present_count = 0
                late_count = 0
                absent_count = 0
                leave_count = 0
                daily_map = {}
                today_d = date.today()

                for d in range(1, num_days + 1):
                    cur_date = date(target_year, target_month, d)
                    date_str = str(cur_date)
                    is_weekend = cur_date.weekday() in [5, 6]  # Saturday (5) & Sunday (6)
                    is_holiday = cur_date in holiday_map

                    if cur_date in record_map:
                        r = record_map[cur_date]
                        st = (r.status or "Present").capitalize()
                        c_in = str(r.check_in)[:5] if r.check_in else None
                        c_out = str(r.check_out)[:5] if r.check_out else None

                        if st in ["Present", "Late"]:
                            present_count += 1
                            if st == "Late":
                                late_count += 1
                        elif st == "Absent":
                            absent_count += 1
                        elif st == "Leave":
                            leave_count += 1

                        if not is_weekend and not is_holiday:
                            total_working_days += 1

                        daily_map[date_str] = {
                            "status": st,
                            "check_in": c_in,
                            "check_out": c_out,
                            "is_holiday": is_holiday,
                            "holiday_name": holiday_map.get(cur_date, "")
                        }
                    else:
                        weekend_title = "Saturday" if cur_date.weekday() == 5 else "Sunday"
                        if is_holiday:
                            status_label = "Holiday"
                        elif is_weekend:
                            status_label = "Weekend"
                        elif cur_date < today_d:
                            status_label = "Absent"
                            total_working_days += 1
                            absent_count += 1
                        else:
                            status_label = "Upcoming"

                        daily_map[date_str] = {
                            "status": status_label,
                            "check_in": None,
                            "check_out": None,
                            "is_holiday": is_holiday,
                            "holiday_name": holiday_map.get(cur_date, ""),
                            "weekend_label": weekend_title
                        }

                pct = round((present_count / total_working_days * 100), 1) if total_working_days > 0 else 100.0

                # 12-Month trend
                monthly_trend = []
                month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                for m in range(1, 13):
                    m_start = date(target_year, m, 1)
                    m_end = date(target_year, m, calendar.monthrange(target_year, m)[1])
                    m_recs = db.query(Attendance).filter(
                        Attendance.student_id == target_sid,
                        Attendance.date >= m_start,
                        Attendance.date <= m_end,
                        Attendance.status.in_(["Present", "Late", "present", "late"])
                    ).count()
                    m_total = db.query(Attendance).filter(
                        Attendance.student_id == target_sid,
                        Attendance.date >= m_start,
                        Attendance.date <= m_end
                    ).count()
                    m_pct = round((m_recs / m_total * 100), 1) if m_total > 0 else (pct if m == target_month else 0.0)
                    monthly_trend.append({"month": month_names[m - 1], "month_num": m, "percentage": m_pct, "present": m_recs})

                db.close()
                return {
                    "student_id": target_sid,
                    "student_name": student.full_name,
                    "registration_number": student.registration_number,
                    "month": target_month,
                    "year": target_year,
                    "percentage": pct,
                    "present_count": present_count,
                    "late_count": late_count,
                    "absent_count": absent_count,
                    "leave_count": leave_count,
                    "total_working_days": total_working_days,
                    "daily_map": daily_map,
                    "monthly_trend": monthly_trend
                }
            except Exception as db_err:
                logger.error(f"Fallback DB calculation also failed: {db_err}")
                return {}

    def get_admin_attendance_matrix(self, month: int = None, year: int = None, department: str = None, search: str = None) -> dict:
        """Retrieves college-wide attendance matrix for all students with monthly percentage filters."""
        params = {}
        if month: params["month"] = month
        if year: params["year"] = year
        if department: params["department"] = department
        if search: params["search"] = search
        try:
            response = self.session.get(
                f"{self.base_url}/attendance/admin/matrix",
                params=params,
                headers=self.headers,
                timeout=20
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching admin attendance matrix: {e}")
            return {}


api_client = APIClient()
