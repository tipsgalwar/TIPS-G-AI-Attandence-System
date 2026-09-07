import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from loguru import logger

from src.database.connection import get_db
from src.database.models import Admin, Teacher, Student, UserSession, PasswordResetToken, EmailVerificationToken
from src.backend.dependencies import get_current_user
from src.backend.services.auth_service import verify_password, create_access_token, get_password_hash
from src.backend.services.email_service import email_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

class TokenResponse(BaseModel):
    id: int
    access_token: str
    token_type: str
    role: str
    username: str
    full_name: str
    session_id: Optional[str] = None

class SeedResponse(BaseModel):
    message: str
    admin_created: bool
    teacher_created: bool

class ForgotPasswordRequest(BaseModel):
    username: str
    new_password: str

class PasswordResetRequest(BaseModel):
    username: str

class PasswordResetConfirm(BaseModel):
    username: str
    otp: str
    new_password: str

class CheckOtpRequest(BaseModel):
    username: str
    otp: str

class SendEmailVerificationRequest(BaseModel):
    email: str
    username: Optional[str] = None
    full_name: Optional[str] = "Student"

class VerifyEmailOtpRequest(BaseModel):
    email: str
    otp: str
    username: Optional[str] = None


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Legacy direct reset route kept for internal use only. Prefer OTP-based reset."""
    if not payload.new_password or len(payload.new_password.strip()) < 6:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 6 characters long."
        )

    hashed = get_password_hash(payload.new_password.strip())

    admin = db.query(Admin).filter(Admin.username == payload.username, Admin.is_active == True).first()
    if admin:
        admin.hashed_password = hashed
        db.commit()
        return {"status": "success", "message": "Password has been reset successfully."}

    teacher = db.query(Teacher).filter(Teacher.username == payload.username, Teacher.is_active == True).first()
    if teacher:
        teacher.hashed_password = hashed
        db.commit()
        return {"status": "success", "message": "Password has been reset successfully."}

    normalized_username = _normalize_student_registration(payload.username)
    student = db.query(Student).filter(Student.registration_number == normalized_username, Student.is_active == True).first()
    if student:
        student.hashed_password = hashed
        db.commit()
        return {"status": "success", "message": "Password has been reset successfully."}

    raise HTTPException(status_code=404, detail="Username or Registration ID not found.")

@router.post("/request-password-reset")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    username = _normalize_student_registration(payload.username)
    student = db.query(Student).filter(Student.registration_number == username, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student username not found.")

    recipient_email = student.email or student.parent_email
    if not recipient_email:
        raise HTTPException(status_code=400, detail="No email address available for this student.")

    # Validate that the stored email is a proper RFC-5321 address before attempting to send
    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    if not _EMAIL_REGEX.match(recipient_email):
        logger.warning(
            f"Student '{username}' has an invalid email on record: '{recipient_email}'. "
            "Please update the student profile with a valid email address."
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"The email address on file ('{recipient_email}') is not valid. "
                "Please contact the administrator to update your email address."
            )
        )

    otp_code = "".join(secrets.choice("0123456789") for _ in range(6))
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    db.query(PasswordResetToken).filter(PasswordResetToken.student_id == student.id).delete()
    token = PasswordResetToken(
        student_id=student.id,
        otp_code=otp_code,
        expires_at=expires_at,
        created_at=datetime.utcnow()
    )
    db.add(token)
    db.commit()

    sent = email_service.send_password_reset_otp(recipient_email, student.full_name, otp_code)
    if not sent:
        # Roll back the token so stale OTPs don't accumulate
        db.query(PasswordResetToken).filter(PasswordResetToken.student_id == student.id).delete()
        db.commit()
        raise HTTPException(
            status_code=500,
            detail="Failed to send OTP email. Please check email configuration or try again later."
        )

    return {"status": "success", "message": "OTP sent to your registered email address."}

@router.post("/verify-password-reset")
def verify_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    if not payload.new_password or len(payload.new_password.strip()) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")

    username = _normalize_student_registration(payload.username)
    student = db.query(Student).filter(Student.registration_number == username, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student username not found.")

    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.student_id == student.id,
        PasswordResetToken.otp_code == payload.otp
    ).first()

    if not reset_token or reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    student.hashed_password = get_password_hash(payload.new_password.strip())
    db.query(PasswordResetToken).filter(PasswordResetToken.student_id == student.id).delete()
    db.commit()
    return {"status": "success", "message": "Password has been reset successfully."}


@router.post("/check-otp")
def check_otp(payload: CheckOtpRequest, db: Session = Depends(get_db)):
    """Validate an OTP without resetting the password.
    Returns 200 if valid, 400 if invalid or expired.
    The token is intentionally NOT deleted so the same OTP can be used
    by the subsequent /verify-password-reset call."""
    username = _normalize_student_registration(payload.username)
    student = db.query(Student).filter(
        Student.registration_number == username, Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student username not found.")

    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.student_id == student.id,
        PasswordResetToken.otp_code == payload.otp
    ).first()

    if not reset_token or reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Incorrect OTP.")

    return {"status": "valid", "message": "OTP is correct."}


@router.post("/send-verification-otp")
def send_verification_otp(payload: SendEmailVerificationRequest, db: Session = Depends(get_db)):
    """Generates and sends a 6-digit OTP to verify a student's Gmail/email address."""
    email = payload.email.strip().lower()
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(status_code=400, detail="Invalid email address format.")

    # 1. Verify whether this email is already registered to another account
    existing_student = db.query(Student).filter(Student.email == email, Student.is_active == True).first()
    existing_teacher = db.query(Teacher).filter(Teacher.email == email, Teacher.is_active == True).first()
    existing_admin = db.query(Admin).filter(Admin.email == email, Admin.is_active == True).first()

    is_same_user = False
    if payload.username:
        normalized_u = _normalize_student_registration(payload.username)
        if existing_student and existing_student.registration_number == normalized_u:
            is_same_user = True

    if (existing_student and not is_same_user) or existing_teacher or existing_admin:
        raise HTTPException(
            status_code=400,
            detail="This email address is already registered to another account."
        )

    otp_code = "".join(secrets.choice("0123456789") for _ in range(6))
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Delete any pending unverified tokens for this email
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.email == email,
        EmailVerificationToken.verified == False
    ).delete()

    token_entry = EmailVerificationToken(
        email=email,
        username=payload.username.strip() if payload.username else None,
        otp_code=otp_code,
        expires_at=expires_at,
        verified=False
    )
    db.add(token_entry)
    db.commit()

    student_name = payload.full_name or payload.username or "Student"
    sent = email_service.send_email_verification_otp(email, student_name, otp_code)
    if not sent:
        # Roll back unverified token if mail delivery completely fails
        try:
            db.delete(token_entry)
            db.commit()
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail="Failed to send verification email. Please check internet connection or email configuration."
        )

    return {"status": "success", "message": f"Verification OTP sent to {email}."}


@router.post("/verify-email-otp")
def verify_email_otp(payload: VerifyEmailOtpRequest, db: Session = Depends(get_db)):
    """Verifies the 6-digit OTP sent to a student's Gmail address."""
    email = payload.email.strip().lower()
    otp = payload.otp.strip()

    token_entry = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.email == email,
        EmailVerificationToken.otp_code == otp
    ).order_by(EmailVerificationToken.created_at.desc()).first()

    if not token_entry or token_entry.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code.")

    token_entry.verified = True
    db.commit()

    return {"status": "success", "verified": True, "message": "Gmail address verified successfully."}




def _normalize_student_registration(username: str) -> str:
    """Normalize student login strings to canonical lowercase registration number ending in -tipsg."""
    if not username:
        return username
    normalized = username.strip().lower()
    if not normalized.endswith("-tipsg"):
        normalized = f"{normalized}-tipsg"
    return normalized


def _find_student_by_username(username: str, db: Session) -> Optional[Student]:
    """Look up a student by normalized registration or raw entered username.

    This helps support older records created before the registration suffix
    normalization fix, as well as current normalized student login values.
    """
    if not username:
        return None

    normalized_regno = _normalize_student_registration(username)
    student = db.query(Student).filter(Student.registration_number == normalized_regno, Student.is_active == True).first()
    if student:
        return student

    # Backward compatibility: allow exact raw registration values too.
    student = db.query(Student).filter(Student.registration_number == username.strip().lower(), Student.is_active == True).first()
    return student


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Logs in an Admin or Teacher and returns a JWT access token."""
    # 1. Search in Admins
    admin = db.query(Admin).filter(Admin.username == form_data.username, Admin.is_active == True).first()
    if admin and verify_password(form_data.password, admin.hashed_password):
        token = create_access_token(admin.username, "admin")
        return {
            "id": admin.id,
            "access_token": token,
            "token_type": "bearer",
            "role": "admin",
            "username": admin.username,
            "full_name": admin.full_name
        }

    # 2. Search in Teachers
    teacher = db.query(Teacher).filter(Teacher.username == form_data.username, Teacher.is_active == True).first()
    if teacher and verify_password(form_data.password, teacher.hashed_password):
        token = create_access_token(teacher.username, teacher.role)
        return {
            "id": teacher.id,
            "access_token": token,
            "token_type": "bearer",
            "role": teacher.role,
            "username": teacher.username,
            "full_name": teacher.full_name
        }

    # 3. Search in Students
    normalized_regno = _normalize_student_registration(form_data.username)
    student = db.query(Student).filter(Student.registration_number == normalized_regno, Student.is_active == True).first()
    if student and student.hashed_password and verify_password(form_data.password, student.hashed_password):
        # Each device has a separately revocable server-side session.
        session = UserSession(session_id=secrets.token_urlsafe(48), student_id=student.id)
        db.add(session)
        db.commit()
        token = create_access_token(student.registration_number, "student", session_id=session.session_id)
        return {
            "id": student.id,
            "access_token": token,
            "token_type": "bearer",
            "role": "student",
            "username": student.registration_number,
            "full_name": student.full_name,
            "session_id": session.session_id,
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revokes the current student session so its token cannot be reused."""
    if current_user["role"] != "student":
        return {"status": "success"}

    session = current_user.get("session")
    if session and session.revoked_at is None:
        session.revoked_at = datetime.utcnow()
        db.commit()
    return {"status": "success"}


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Validates a saved session and returns the signed-in user's identity."""
    user = current_user["user"]
    role = current_user["role"]
    data = {
        "id": user.id,
        "username": user.registration_number if role == "student" else user.username,
        "role": role,
        "full_name": user.full_name,
        "email": getattr(user, "email", None),
    }
    if role == "student":
        data.update({
            "registration_number": user.registration_number,
            "phone": getattr(user, "phone", None),
            "parent_name": getattr(user, "parent_name", None),
            "parent_phone": getattr(user, "parent_phone", None),
            "parent_email": getattr(user, "parent_email", None),
            "class_name": getattr(user, "class_name", None),
            "photo_path": getattr(user, "photo_path", None),
        })
    elif role in ["teacher", "manager", "hr"]:
        data.update({
            "phone": getattr(user, "phone", None),
            "department": getattr(user, "department", None),
        })
    return data

@router.post("/seed", response_model=SeedResponse)
def seed_initial_accounts(db: Session = Depends(get_db)):
    """Seeds default admin and teacher accounts for initial run if they don't exist."""
    admin_created = False
    teacher_created = False

    # Check if admin table is empty
    admin = db.query(Admin).first()
    if not admin:
        default_admin = Admin(
            username="admin",
            hashed_password=get_password_hash("admin123"),
            full_name="System Administrator",
            email="tipsgalwar@gmail.com",
            role="admin",
            is_active=True
        )
        db.add(default_admin)
        admin_created = True
        logger.info("Seeded default admin account (username: admin, password: admin123)")
    else:
        if admin.email in ["admin@tipsg.edu.in", "admin@tipsg", None, ""]:
            admin.email = "tipsgalwar@gmail.com"
            db.commit()

    # Check if teacher table is empty
    teacher_count = db.query(Teacher).count()
    if teacher_count == 0:
        default_teacher = Teacher(
            employee_id="T01",
            username="teacher",
            hashed_password=get_password_hash("teacher123"),
            full_name="Prof. John Doe",
            email="john.doe@tipsg.edu.in",
            phone="9876543210",
            department="Computer Science",
            role="teacher",
            is_active=True
        )
        db.add(default_teacher)
        
        # Add another manager/HR teacher
        default_hr = Teacher(
            employee_id="T02",
            username="hr",
            hashed_password=get_password_hash("hr123"),
            full_name="HR Manager Sarah",
            email="sarah.hr@tipsg.edu.in",
            phone="9876543211",
            department="Human Resources",
            role="hr",
            is_active=True
        )
        db.add(default_hr)
        
        teacher_created = True
        logger.info("Seeded default teacher/hr accounts (teacher/teacher123, hr/hr123)")

    if admin_created or teacher_created:
        db.commit()
        return {
            "message": "Accounts successfully seeded.",
            "admin_created": admin_created,
            "teacher_created": teacher_created
        }
    else:
        return {
            "message": "Accounts already exist. No seeding performed.",
            "admin_created": False,
            "teacher_created": False
        }
