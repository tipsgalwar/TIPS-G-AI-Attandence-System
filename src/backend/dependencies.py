from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from fastapi import Request
from sqlalchemy.orm import Session
from loguru import logger

from src.database.connection import get_db
from src.database.models import Admin, Teacher, Student, UserSession
from src.backend.services.auth_service import decode_access_token

# -----------------------------------------------------------------------
# DEV BYPASS — Set to False before deploying to production!
# When True, all auth checks are skipped and every request is treated
# as the default "admin" user (username: admin).
DEV_BYPASS_AUTH: bool = False
# -----------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=not DEV_BYPASS_AUTH)


def get_current_user(request: Request, db: Session = Depends(get_db)):
    # --- DEV BYPASS ---
    if DEV_BYPASS_AUTH:
        logger.warning("DEV_BYPASS_AUTH is enabled — skipping authentication!")
        dev_user = db.query(Admin).filter(Admin.username == "admin", Admin.is_active == True).first()
        if dev_user is None:
            # Fallback: return a simple namespace so routes don't crash even
            # if the DB hasn't been seeded yet.
            class _FakeAdmin:
                username = "admin"
                full_name = "Dev Admin"
                email = "dev@localhost"
                role = "admin"
                is_active = True
            dev_user = _FakeAdmin()
        return {"user": dev_user, "role": "admin"}
    # --- END DEV BYPASS ---

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    authorization: str = request.headers.get("Authorization")
    scheme, token = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "bearer":
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    username: str = payload.get("sub")
    role: str = payload.get("role")

    if username is None or role is None:
        raise credentials_exception

    if role == "admin":
        user = db.query(Admin).filter(Admin.username == username, Admin.is_active == True).first()
        if user is None:
            raise credentials_exception
        return {"user": user, "role": "admin"}
    elif role in ["teacher", "manager", "hr"]:
        user = db.query(Teacher).filter(Teacher.username == username, Teacher.is_active == True).first()
        if user is None:
            raise credentials_exception
        return {"user": user, "role": role}
    elif role == "student":
        user = db.query(Student).filter(Student.registration_number == username, Student.is_active == True).first()
        if user is None:
            raise credentials_exception
        session_id = payload.get("sid")
        if not session_id:
            raise credentials_exception
        session = db.query(UserSession).filter(
            UserSession.session_id == session_id,
            UserSession.student_id == user.id,
            UserSession.revoked_at == None,
        ).first()
        if session is None:
            raise credentials_exception
        session.last_active_at = datetime.utcnow()
        db.commit()
        return {"user": user, "role": "student", "session": session}

    raise credentials_exception


def require_admin(current_user: dict = Depends(get_current_user)):
    if DEV_BYPASS_AUTH:
        return current_user["user"]
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires administrator privileges"
        )
    return current_user["user"]


def require_admin_or_hr(current_user: dict = Depends(get_current_user)):
    if DEV_BYPASS_AUTH:
        return current_user["user"]
    if current_user["role"] not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires administrator or HR privileges"
        )
    return current_user["user"]

def require_teacher(current_user: dict = Depends(get_current_user)):
    if DEV_BYPASS_AUTH:
        return current_user["user"]
    if current_user["role"] not in ["admin", "teacher", "manager", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires educator privileges"
        )
    return current_user["user"]


def require_auth(current_user: dict = Depends(get_current_user)):
    """Allow any authenticated user (admin, teacher, student)."""
    if DEV_BYPASS_AUTH:
        return current_user["user"]
    # All roles allowed - just needs to be authenticated
    return current_user["user"]

