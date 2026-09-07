import os
import sys
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


class APIClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIClient, cls).__new__(cls)
            cls._instance.base_url = _get_api_base_url()
            cls._instance.token = None
            cls._instance.user_info = {}
            logger.info(f"API Client initialized → {cls._instance.base_url}")
        return cls._instance

    def set_token(self, token: str):
        self.token = token

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
            response = requests.post(url, data=data, timeout=20)
            if response.status_code == 200:
                resp_json = response.json()
                self.token = resp_json["access_token"]
                self.user_info = {
                    "id": resp_json["id"],
                    "username": resp_json["username"],
                    "role": resp_json["role"],
                    "full_name": resp_json["full_name"]
                }
                self._save_session(self.token)
                logger.info(f"✓ Login successful for {self.user_info['username']} ({self.user_info['role']})")
                logger.debug(f"  Token set: {self.token[:20]}...")
                logger.debug(f"  Headers: {self.headers}")
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

    def _save_session(self, token: str):
        """Persist the bearer token for any authenticated user role."""
        os.makedirs(os.path.dirname(self._session_file), exist_ok=True)
        with open(self._session_file, "w", encoding="utf-8") as session_file:
            session_file.write(token)

    def _clear_saved_session(self):
        for path in [self._session_file, self._legacy_session_file]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def restore_session(self) -> Optional[dict]:
        """Restore a saved session for any authenticated user role if valid on backend."""
        token = None
        for path in [self._session_file, self._legacy_session_file]:
            try:
                with open(path, "r", encoding="utf-8") as session_file:
                    content = session_file.read().strip()
                    if content:
                        token = content
                        break
            except FileNotFoundError:
                continue

        if not token:
            self._clear_saved_session()
            return None

        self.token = token
        try:
            response = requests.get(f"{self.base_url}/auth/me", headers=self.headers, timeout=4)
            response.raise_for_status()
            self.user_info = response.json()
            logger.info(f"✓ Restored session for {self.user_info.get('username')} ({self.user_info.get('role')})")
            return self.user_info
        except Exception as e:
            logger.warning(f"Could not restore saved session: {e}")
            self.token = None
            self.user_info = {}
            self._clear_saved_session()
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
                requests.post(f"{self.base_url}/auth/logout", headers=self.headers, timeout=10)
        except requests.RequestException as error:
            logger.warning(f"Could not revoke server session during logout: {error}")
        self._clear_saved_session()
        self.token = None
        self.user_info = {}

    def forgot_password(self, username: str, new_password: str) -> dict:
        url = f"{self.base_url}/auth/forgot-password"
        response = requests.post(url, json={"username": username, "new_password": new_password}, timeout=10)
        response.raise_for_status()
        return response.json()

    def request_password_reset(self, username: str) -> dict:
        url = f"{self.base_url}/auth/request-password-reset"
        response = requests.post(url, json={"username": username}, timeout=10)
        response.raise_for_status()
        return response.json()

    def verify_password_reset(self, username: str, otp: str, new_password: str) -> dict:
        url = f"{self.base_url}/auth/verify-password-reset"
        response = requests.post(url, json={"username": username, "otp": otp, "new_password": new_password}, timeout=10)
        response.raise_for_status()
        return response.json()

    def verify_otp_only(self, username: str, otp: str) -> dict:
        """Check that an OTP is valid WITHOUT changing the password.
        Raises an HTTPError if the OTP is invalid or expired."""
        url = f"{self.base_url}/auth/check-otp"
        response = requests.post(url, json={"username": username, "otp": otp}, timeout=10)
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
        response = requests.post(url, json=payload, timeout=12)
        response.raise_for_status()
        return response.json()

    def verify_email_otp(self, email: str, otp: str, username: Optional[str] = None) -> dict:
        """Verify the 6-digit OTP code sent to the email."""
        url = f"{self.base_url}/auth/verify-email-otp"
        payload = {"email": email, "otp": otp}
        if username:
            payload["username"] = username
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()


    def get_summary(self, target_date: Optional[str] = None) -> dict:
        if not self.token:
            return {}
        url = f"{self.base_url}/reports/summary"
        params = {"target_date": target_date} if target_date else {}
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=5)
            if response.status_code in [401, 403]:
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"get_summary API call fallback: {e}")
            return {}

    def get_students(self) -> List[dict]:
        url = f"{self.base_url}/students/"
        response = requests.get(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return response.json()

    def delete_student(self, student_id: int) -> dict:
        url = f"{self.base_url}/students/{student_id}"
        response = requests.delete(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return {"status": "success"}

    def add_student(self, data: dict, photo_path: str) -> dict:
        url = f"{self.base_url}/students/"
        # Read file
        with open(photo_path, "rb") as f:
            files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
            response = requests.post(url, data=data, files=files, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()

    def register_student(self, data: dict, photo_path: Optional[str] = None) -> dict:
        url = f"{self.base_url}/students/self-register"
        if photo_path:
            with open(photo_path, "rb") as f:
                files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
                response = requests.post(url, data=data, files=files, timeout=120)
        else:
            # Multipart is required when the endpoint includes an UploadFile field,
            # even when the file is optional. Sending an empty photo part ensures
            # FastAPI can parse the request and avoid the 422 missing field error.
            files = {"photo": ("", b"", "application/octet-stream")}
            response = requests.post(url, data=data, files=files, timeout=120)

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
            response = requests.get(url, params=params, headers=self.headers, timeout=5)
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
            response = requests.get(url, headers=self.headers, timeout=3)
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
            response = requests.put(url, data=data, files=files, headers=self.headers, timeout=120)
        elif photo_path and os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
                response = requests.put(url, data=data, files=files, headers=self.headers, timeout=120)
        else:
            # Ensure multipart form-data is sent so optional UploadFile is parsed properly.
            files = {"photo": ("", b"", "application/octet-stream")}
            response = requests.put(url, data=data, files=files, headers=self.headers, timeout=120)
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
        response = requests.post(url, json=payload, headers=self.headers, timeout=5)
        response.raise_for_status()
        return response.json()

    def get_student_embedding(self, student_id: int) -> dict:
        """Fetch a specific student's face embedding. Requires teacher/admin token."""
        url = f"{self.base_url}/attendance/student-embedding/{student_id}"
        response = requests.get(url, headers=self.headers, timeout=10)
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
        response = requests.post(url, json=payload, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def trigger_absence_scan(self, date_str: Optional[str] = None) -> dict:
        url = f"{self.base_url}/attendance/trigger-scan"
        params = {"target_date": date_str} if date_str else {}
        response = requests.post(url, params=params, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_holidays(self) -> List[dict]:
        url = f"{self.base_url}/holidays/"
        response = requests.get(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return response.json()

    def create_holiday(self, name: str, date_str: str, description: str = "") -> dict:
        url = f"{self.base_url}/holidays/"
        payload = {
            "name": name,
            "date": date_str,
            "description": description
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_notifications(self, unread_only: bool = False) -> List[dict]:
        response = requests.get(
            f"{self.base_url}/notifications/",
            params={"unread_only": unread_only},
            headers=self.headers,
            timeout=5,
        )
        response.raise_for_status()
        return response.json()

    def mark_notification_read(self, notification_id: int) -> None:
        response = requests.post(
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
            response = requests.post(url, data=data, files=files, headers=self.headers, timeout=15)
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
        response = requests.post(url, data=data, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_pending_leaves(self) -> List[dict]:
        url = f"{self.base_url}/leaves/pending"
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_leave_document(self, leave_id: int) -> tuple:
        """Fetches the supporting document binary content and suggested filename."""
        url = f"{self.base_url}/leaves/{leave_id}/document"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
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

    def trigger_absence_scan(self, target_date: Optional[str] = None) -> dict:
        """Triggers daily absence scanning and dispatches parent alerts & emails."""
        url = f"{self.base_url}/attendance/trigger-scan"
        params = {}
        if target_date:
            params["target_date"] = target_date
        response = requests.post(url, params=params, headers=self.headers, timeout=20)
        response.raise_for_status()
        return response.json()

    def approve_leave(self, leave_id: int) -> dict:
        url = f"{self.base_url}/leaves/{leave_id}/approve"
        response = requests.post(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def reject_leave(self, leave_id: int) -> dict:
        url = f"{self.base_url}/leaves/{leave_id}/reject"
        response = requests.post(url, headers=self.headers, timeout=15)
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
        response = requests.get(url, params=params, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.content

    def get_monthly_report_archives(self) -> List[dict]:
        response = requests.get(f"{self.base_url}/reports/archives", headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def download_monthly_report_archive(self, archive_id: int) -> bytes:
        response = requests.get(
            f"{self.base_url}/reports/archives/{archive_id}/download",
            headers=self.headers,
            timeout=30
        )
        response.raise_for_status()
        return response.content

    def delete_monthly_report_archive(self, archive_id: int) -> None:
        response = requests.delete(
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
            response = requests.post(
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
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code in [401, 403, 404]:
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"get_my_embedding API call fallback: {e}")
            return {}
    def get_noticeboard_holidays(self):
        response = requests.get(
            f"{self.base_url}/noticeboard/holidays",
            headers=self.headers,
            timeout=30
        )

        response.raise_for_status()

        return response.json()

import os
api_client = APIClient()
