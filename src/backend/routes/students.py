import os
import json
import math
import hashlib
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger

from src.database.connection import get_db
from src.database.models import Student, FaceEmbedding, Admin, Teacher, EmailVerificationToken
from src.backend.dependencies import require_teacher, require_admin, require_auth
from src.backend.services.auth_service import get_password_hash
from src.backend.services.email_service import email_service
from src.config_loader import settings

router = APIRouter(prefix="/students", tags=["Students"])

class StudentOut(BaseModel):
    id: int
    registration_number: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    parent_name: str
    parent_phone: str
    parent_email: Optional[str] = None
    class_name: str
    photo_path: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


def _face_embedding_is_already_registered(db: Session, candidate_embedding: list, exclude_student_id: Optional[int] = None) -> bool:
    """Return True when the submitted face matches an active student.

    Uses a reliable duplicate detection distance threshold (<= 0.45) so that
    the same person cannot register multiple student accounts.
    """
    try:
        candidate = [float(value) for value in candidate_embedding]
        candidate_norm = math.sqrt(sum(value * value for value in candidate))
    except (TypeError, ValueError):
        return False
    if not candidate_norm:
        return False

    duplicate_threshold = float(settings.ai_models.get("duplicate_threshold", 0.49))
    active_students = db.query(Student).filter(Student.is_active == True).all()
    for student in active_students:
        if exclude_student_id and student.id == exclude_student_id:
            continue
        stored_embedding = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).first()
        stored = stored_embedding.embedding if stored_embedding else None
        if stored is None:
            continue
        if isinstance(stored, str):
            try:
                stored = json.loads(stored)
            except json.JSONDecodeError:
                continue
        try:
            stored = [float(value) for value in stored]
        except (TypeError, ValueError):
            continue
        if len(stored) != len(candidate):
            continue
        stored_norm = math.sqrt(sum(value * value for value in stored))
        if not stored_norm:
            continue
        cosine_similarity = sum(a * b for a, b in zip(candidate, stored)) / (candidate_norm * stored_norm)
        cosine_distance = max(0.0, min(2.0, 1.0 - cosine_similarity))
        if cosine_distance <= duplicate_threshold:
            logger.warning(
                "Rejected registration because the submitted face is already registered. "
                f"matched_student_id={student.id} regno={student.registration_number if student.registration_number else 'unknown'} "
                f"distance={cosine_distance:.4f} threshold={duplicate_threshold:.4f} similarity={cosine_similarity*100:.1f}%"
            )
            return True
    return False


def _format_student_username(username: str) -> str:
    """Create the canonical student login/registration ID ending in -tipsg."""
    base_name = (username or "").strip().lower()
    if base_name.endswith("-tipsg"):
        base_name = base_name[:-6]
    base_name = re.sub(r"[^a-z0-9]+", "-", base_name).strip("-")
    if not base_name:
        raise HTTPException(status_code=422, detail="Enter a valid student username")
    return f"{base_name}-tipsg"

@router.get("/", response_model=List[StudentOut])
def get_students(db: Session = Depends(get_db), current_user = Depends(require_teacher)):
    """Lists all active students in the system."""
    return db.query(Student).filter(Student.is_active == True).all()

@router.get("/me", response_model=StudentOut)
def get_my_profile(db: Session = Depends(get_db), current_user = Depends(require_auth)):
    """Get the current authenticated student's profile."""
    if getattr(current_user, "registration_number", None) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this endpoint.")
    student = current_user
    if not student.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student account is inactive.")
    return student

@router.put("/me", response_model=StudentOut)
def update_my_profile(
    full_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    parent_name: Optional[str] = Form(None),
    parent_phone: Optional[str] = Form(None),
    parent_email: Optional[str] = Form(None),
    class_name: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    embedding: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Update the current student's profile and optionally refresh face embedding."""
    if getattr(current_user, "registration_number", None) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this endpoint.")
    student = current_user
    target_email = (email or student.email or "").strip().lower()
    if target_email:
        verified_token = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.email == target_email,
            EmailVerificationToken.verified == True,
            EmailVerificationToken.expires_at >= datetime.utcnow() - timedelta(minutes=30)
        ).first()
        if not verified_token:
            raise HTTPException(
                status_code=400,
                detail="Security OTP verification is required to update profile details."
            )

    if full_name is not None:
        student.full_name = full_name.strip()
    
    if email is not None:
        new_email = email.strip().lower()
        curr_email = (student.email or "").strip().lower()
        if new_email and new_email != curr_email:
            # 1. Check if email is already taken by another user
            existing_student = db.query(Student).filter(Student.email == new_email, Student.id != student.id, Student.is_active == True).first()
            existing_teacher = db.query(Teacher).filter(Teacher.email == new_email, Teacher.is_active == True).first()
            existing_admin = db.query(Admin).filter(Admin.email == new_email, Admin.is_active == True).first()
            if existing_student or existing_teacher or existing_admin:
                raise HTTPException(
                    status_code=400,
                    detail="This email address is already registered to another account."
                )
            student.email = new_email
        elif not new_email:
            student.email = None

    if phone is not None:
        student.phone = phone.strip()
    if parent_name is not None:
        student.parent_name = parent_name.strip()
    if parent_phone is not None:
        student.parent_phone = parent_phone.strip()
    if parent_email is not None:
        student.parent_email = parent_email.strip()
    if class_name is not None:
        student.class_name = class_name.strip()
    if password:
        student.hashed_password = get_password_hash(password)

    if embedding is not None:
        try:
            embedding_vector = json.loads(embedding)
            if not isinstance(embedding_vector, list) or len(embedding_vector) != 512:
                raise ValueError("Embedding must be a 512-dimensional vector list.")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid embedding format: {e}"
            )

        db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).delete()
        db.add(FaceEmbedding(student_id=student.id, embedding=embedding_vector))

    db.commit()
    return student

@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db), current_user = Depends(require_teacher)):
    """Retrieves student details."""
    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.post("/", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(
    registration_number: str = Form(...),
    full_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    parent_name: str = Form(...),
    parent_phone: str = Form(...),
    parent_email: Optional[str] = Form(None),
    class_name: str = Form(...),
    embedding: str = Form(...),  # Received from frontend
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Registers a new student, saves their face profile photo,
    saves the client-side computed embedding, and registers them in the database.
    """
    registration_number = _format_student_username(registration_number)
    
    # Parse embedding
    try:
        embedding_vector = json.loads(embedding)
        if not isinstance(embedding_vector, list) or len(embedding_vector) != 512:
            raise ValueError("Embedding must be a 512-dimensional vector list.")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid embedding format: {e}"
        )

    # Check if student registration number already exists
    existing = db.query(Student).filter(Student.registration_number == registration_number).first()
    if email:
        clean_email = email.strip().lower()
        email_student = db.query(Student).filter(Student.email == clean_email, Student.is_active == True).first()
        email_teacher = db.query(Teacher).filter(Teacher.email == clean_email, Teacher.is_active == True).first()
        email_admin = db.query(Admin).filter(Admin.email == clean_email, Admin.is_active == True).first()
        if (email_student and (not existing or email_student.id != existing.id)) or email_teacher or email_admin:
            raise HTTPException(status_code=400, detail="This email address is already registered to another account.")

    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Student registration number already exists")
        else:
            # Re-activate previously deleted student and refresh embedding only.
            existing.is_active = True
            existing.full_name = full_name
            existing.email = email
            existing.phone = phone
            existing.parent_name = parent_name
            existing.parent_phone = parent_phone
            existing.parent_email = parent_email
            existing.class_name = class_name
            existing.photo_path = None

            # Replace all old embeddings with fresh one
            db.query(FaceEmbedding).filter(FaceEmbedding.student_id == existing.id).delete()
            db.add(FaceEmbedding(student_id=existing.id, embedding=embedding_vector))
            db.commit()
            return existing

    # Ignore local photo storage; only save embedding in the database.
    if _face_embedding_is_already_registered(db, embedding_vector):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This face image is already registered. Please use the student's own photo."
        )

    # Save to Database
    student = Student(
        registration_number=registration_number,
        full_name=full_name,
        email=email,
        phone=phone,
        parent_name=parent_name,
        parent_phone=parent_phone,
        parent_email=parent_email,
        class_name=class_name,
        photo_path=None,
        is_active=True
    )
    db.add(student)
    db.flush() # Populate student.id

    # Store Embedding linked to Student ID only in the database
    embedding_record = FaceEmbedding(
        student_id=student.id,
        embedding=embedding_vector
    )
    db.add(embedding_record)

    db.commit()
    logger.info(f"Successfully created student {full_name} ({registration_number}) with face verification.")
    return student

@router.post("/self-register", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def self_register_student(
    registration_number: str = Form(...),
    full_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    parent_name: str = Form(...),
    parent_phone: str = Form(...),
    parent_email: Optional[str] = Form(None),
    class_name: str = Form(...),
    password: str = Form(...),
    embedding: str = Form(...),  # Received from frontend
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Self-registration endpoint for students using client-side face embeddings.

    The registration photo is optional because the client submits only the computed face embedding.
    """
    registration_number = _format_student_username(registration_number)
    request_started = time.perf_counter()
    
    # Parse embedding
    try:
        embedding_vector = json.loads(embedding)
        if not isinstance(embedding_vector, list) or len(embedding_vector) != 512:
            raise ValueError("Embedding must be a 512-dimensional vector list.")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid embedding format: {e}"
        )

    existing = db.query(Student).filter(Student.registration_number == registration_number).first()
    if email:
        clean_email = email.strip().lower()
        email_student = db.query(Student).filter(Student.email == clean_email, Student.is_active == True).first()
        email_teacher = db.query(Teacher).filter(Teacher.email == clean_email, Teacher.is_active == True).first()
        email_admin = db.query(Admin).filter(Admin.email == clean_email, Admin.is_active == True).first()
        if (email_student and (not existing or email_student.id != existing.id)) or email_teacher or email_admin:
            raise HTTPException(status_code=400, detail="This email address is already registered to another account.")
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Student registration number already exists")
        # Re-activate previously deleted student — save new photo & fresh embedding
        existing.is_active = True
        existing.full_name = full_name
        existing.email = email
        existing.phone = phone
        existing.parent_name = parent_name
        existing.parent_phone = parent_phone
        existing.parent_email = parent_email
        existing.class_name = class_name
        existing.hashed_password = get_password_hash(password)

        # Refresh embedding only; do not save the photo locally.
        existing.photo_path = None

        db.query(FaceEmbedding).filter(FaceEmbedding.student_id == existing.id).delete()
        db.add(FaceEmbedding(student_id=existing.id, embedding=embedding_vector))
        db.commit()
        if existing.email:
            email_service.send_registration_email(existing.email, existing.full_name, existing.registration_number, password)
        return existing

    if _face_embedding_is_already_registered(db, embedding_vector):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This face image is already registered. Please use the student's own photo."
        )

    student = Student(
        registration_number=registration_number,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        email=email,
        phone=phone,
        parent_name=parent_name,
        parent_phone=parent_phone,
        parent_email=parent_email,
        class_name=class_name,
        photo_path=None,
        is_active=True
    )
    db.add(student)
    db.flush()

    embedding_record = FaceEmbedding(
        student_id=student.id,
        embedding=embedding_vector
    )
    db.add(embedding_record)

    db.commit()
    if email:
        email_service.send_registration_email(email, full_name, registration_number, password)

    logger.info(
        f"Successfully self-registered student {full_name} ({registration_number}) "
        f"with face verification. total={time.perf_counter() - request_started:.2f}s"
    )
    return student

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    """Deletes a student and fully purges their face embeddings and profile directory."""
    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Remove profile photo directory from disk if it exists
    if student.photo_path:
        try:
            profile_dir = Path(student.photo_path).parent
            if profile_dir.exists() and profile_dir.is_dir():
                shutil.rmtree(str(profile_dir), ignore_errors=True)
                logger.info(f"Removed profile directory: {profile_dir}")
        except Exception as e:
            logger.warning(f"Could not remove profile directory for student {student_id}: {e}")

    # Fully delete the student and cascade related records (face embeddings, attendance, sessions, etc.)
    db.delete(student)
    db.commit()
    logger.info(f"Student ID {student_id} ({student.full_name}) deleted successfully.")
    return None
