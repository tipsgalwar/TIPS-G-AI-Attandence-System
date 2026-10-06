import json
import math
from datetime import datetime, date, time, timedelta, timezone

_IST = timezone(timedelta(hours=5, minutes=30))
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from loguru import logger
from src.backend.services.wifi_validator import validate_wifi
from src.database.connection import get_db
from src.database.models import Student, Attendance, FaceEmbedding, Holiday
from src.backend.dependencies import require_teacher, require_admin, require_auth
from src.backend.services.alert_service import alert_service
from src.backend.services.email_service import email_service
from src.config_loader import settings

router = APIRouter(prefix="/attendance", tags=["Attendance"])

class FaceVerificationIn(BaseModel):
    confidence: float
    bssid: str
    candidate_embedding: List[float]


def _normalize_embedding(embedding: list) -> Optional[list]:
    try:
        vector = [float(value) for value in embedding]
    except (TypeError, ValueError):
        return None
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0.0:
        return None
    return [value / norm for value in vector]


def _compute_cosine_distance(a: list, b: list) -> float:
    if len(a) != len(b):
        raise ValueError("Embedding length mismatch")
    return max(0.0, min(2.0, 1.0 - sum(x * y for x, y in zip(a, b))))

class AttendanceOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    registration_number: str
    date: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    status: str
    confidence_score: Optional[float] = None
    verification_method: str

    class Config:
        from_attributes = True

class ManualAttendanceIn(BaseModel):
    student_id: int
    date: str # YYYY-MM-DD
    status: str # Present, Late, Absent, Leave, Holiday
    verification_method: str = "Manual"

@router.get("/daily", response_model=List[AttendanceOut])
def get_daily_attendance(
    target_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Retrieves all attendance records for a particular date (defaults to today)."""
    query_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()
    
    if isinstance(current_user, Student):
        records = db.query(Attendance).filter(Attendance.date == query_date, Attendance.student_id == current_user.id).all()
    else:
        records = db.query(Attendance).filter(Attendance.date == query_date).all()
    results = []
    
    for r in records:
        student = r.student
        check_in_str = r.check_in.strftime("%I:%M %p") if r.check_in and hasattr(r.check_in, "strftime") else (str(r.check_in)[:5] if r.check_in else None)
        check_out_str = r.check_out.strftime("%I:%M %p") if r.check_out and hasattr(r.check_out, "strftime") else (str(r.check_out)[:5] if r.check_out else None)
        results.append({
            "id": r.id,
            "student_id": r.student_id,
            "student_name": student.full_name if student else "Unknown",
            "registration_number": student.registration_number if student else "Unknown",
            "date": str(r.date),
            "check_in": check_in_str,
            "check_out": check_out_str,
            "status": r.status,
            "confidence_score": r.confidence_score,
            "verification_method": r.verification_method
        })
    return results

@router.get("/my-embedding")
def get_my_embedding(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Retrieves the logged-in student's face embedding for local verification."""
    student = None
    if isinstance(current_user, Student):
        student = current_user
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students have face embeddings.")
        
    user_embedding = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).first()
    if not user_embedding:
        return {"embedding": None}
        
    embedding_data = user_embedding.embedding
    if isinstance(embedding_data, str):
        try:
            embedding_data = json.loads(embedding_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Corrupted face embedding data.")
            
    return {"embedding": embedding_data}


@router.get("/student-embedding/{student_id}")
def get_student_embedding_for_admin(
    student_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """Retrieve a specific student's face embedding. Admin/teacher only — used for admin-assisted face verification."""
    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    emb_record = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id).first()
    if not emb_record:
        return {"embedding": None, "student_name": student.full_name}
    embedding_data = emb_record.embedding
    if isinstance(embedding_data, str):
        try:
            embedding_data = json.loads(embedding_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Corrupted face embedding data.")
    return {"embedding": embedding_data, "student_name": student.full_name}

@router.post("/verify")
async def verify_face_attendance(
    payload: FaceVerificationIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
    ):
    """
    Verifies the logged-in student's face on the backend using a submitted
    candidate embedding and the stored student embedding.
    """
    print("Steps 1: Received BSSID:", payload.bssid)
    if not validate_wifi(payload.bssid):
        print("______________problem in attendance.py of wifi validation___________________________")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized WiFi network. Attendance registration denied.")
    
    # Get the logged-in user
    student = None
    if isinstance(current_user, Student):
        student = current_user
    else:
        logger.warning(f"Non-student user {current_user} attempted face verification")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only students can use face-based attendance verification. Teachers/Admins use manual attendance."
        )
    
    if not student or not student.is_active:
        logger.warning(f"Inactive or invalid student attempted face verification: {student}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your student account is inactive. Please contact admin."
        )
    
    print(f"Steps 2: User {student.full_name} (ID: {student.id}, RegNo: {student.registration_number}) is logged in")

    if not isinstance(payload.candidate_embedding, list) or len(payload.candidate_embedding) != 512:
        return {
            "status": "failed",
            "error": "Invalid candidate face embedding submitted.",
            "confidence": 0.0
        }

    stored_embedding_record = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).first()
    if not stored_embedding_record:
        return {
            "status": "failed",
            "error": "No registered face embedding found for your account. Please ask admin to register your photo.",
            "confidence": 0.0
        }

    stored_embedding = stored_embedding_record.embedding
    if isinstance(stored_embedding, str):
        try:
            stored_embedding = json.loads(stored_embedding)
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "error": "Stored face embedding is corrupted. Please contact admin.",
                "confidence": 0.0
            }

    candidate_norm = _normalize_embedding(payload.candidate_embedding)
    stored_norm = _normalize_embedding(stored_embedding)
    if candidate_norm is None or stored_norm is None:
        return {
            "status": "failed",
            "error": "Invalid face embedding values were submitted.",
            "confidence": 0.0
        }

    cosine_dist = _compute_cosine_distance(candidate_norm, stored_norm)
    confidence = round((1.0 - cosine_dist) * 100, 2)
    min_conf = float(settings.ai_models.get("minimum_confidence", 50.0))
    similarity_threshold = float(settings.ai_models.get("similarity_threshold", 0.50))

    if cosine_dist > similarity_threshold or confidence < min_conf:
        print(f"Steps 4b: Verification rejected - distance {cosine_dist:.4f}, confidence {confidence:.2f}%")
        return {
            "status": "failed",
            "error": "Face verification failed. Low similarity or confidence.",
            "confidence": confidence,
            "distance": round(cosine_dist, 4)
        }

    print(f"Steps 4a: ✅ Face verified on backend: {student.full_name} with confidence: {confidence}%")
    
    # Adaptive template update on high-confidence verified match (>= 85%)
    try:
        adaptive_enabled = bool(settings.ai_models.get("adaptive_update_enabled", True))
        adaptive_thresh = float(settings.ai_models.get("adaptive_confidence_threshold", 85.0))
        adaptive_lr = float(settings.ai_models.get("adaptive_learning_rate", 0.10))
        if adaptive_enabled and confidence >= adaptive_thresh:
            blended = [(1.0 - adaptive_lr) * s + adaptive_lr * c for s, c in zip(stored_norm, candidate_norm)]
            b_norm = math.sqrt(sum(v * v for v in blended))
            if b_norm > 0:
                stored_embedding_record.embedding = [v / b_norm for v in blended]
                db.commit()
                print(f"Steps 4c: 🔄 Adaptive embedding updated for {student.full_name}")
    except Exception as adapt_err:
        print(f"Steps 4c: Adaptive update non-fatal error: {adapt_err}")

    today = datetime.now(_IST).date()
    now_time = datetime.now(_IST).time()
    print(f"Steps 5: Marking attendance for {student.full_name} on {today} at {now_time}")
    
    # Check if today is a holiday
    is_holiday = db.query(Holiday).filter(Holiday.date == today).first() is not None
    if is_holiday:
        return {"status": "failed", "error": "Today is a holiday. No attendance registration required."}
    
    # Auto-close previous days if forgotten
    previous_open = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.date < today,
        Attendance.check_out == None
    ).all()
    for prev in previous_open:
        prev.check_out = time(16, 0, 0)
    if previous_open:
        db.commit()

    print("Steps 6: Checking if student already has a check-in for today...")
    # Check if student already has a check-in for today
    existing = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.date == today
    ).first()
    formatted_now = now_time.strftime("%I:%M %p") if hasattr(now_time, "strftime") else str(now_time)[:5]
    print("Steps 7: Existing attendance record:", existing)
    if existing:
        # Update check-out time
        existing.check_out = now_time
        db.commit()
        check_in_formatted = existing.check_in.strftime("%I:%M %p") if existing.check_in and hasattr(existing.check_in, "strftime") else (str(existing.check_in)[:5] if existing.check_in else None)
        return {
            "status": "success",
            "message": f"Goodbye {student.full_name}! Check-out registered at {formatted_now}.",
            "student_id": student.id,
            "student_name": student.full_name,
            "check_in": check_in_formatted,
            "check_out": formatted_now,
            "attendance_status": existing.status,
            "confidence": confidence
        }
    print("Steps 8: No existing record found. Determining attendance status based on timing policies...")
    # Parse timing policies
    start_time_str = settings.attendance.get("start_time", "09:00:00")
    late_buffer = settings.attendance.get("late_threshold_minutes", 15)
    
    start_time_obj = datetime.strptime(start_time_str, "%H:%M:%S").time()
    
    # Calculate Late Threshold Limit
    late_threshold_datetime = datetime.combine(today, start_time_obj) + timedelta(minutes=late_buffer)
    late_threshold_time = late_threshold_datetime.time()
    print(f"Steps 9: Start time: {start_time_obj}, Late threshold time: {late_threshold_time}, Current time: {now_time}")
    # Determine attendance status
    if now_time <= late_threshold_time:
        att_status = "Present"
    else:
        att_status = "Late"

    # Save to database
    record = Attendance(
        student_id=student.id,
        date=today,
        check_in=now_time,
        status=att_status,
        confidence_score=confidence,
        verification_method="Face"
    )
    db.add(record)
    db.commit()
    print(f"Steps 10: Attendance recorded for {student.full_name} ({att_status}) at {formatted_now}.")
    logger.info(f"Attendance recorded via face match: {student.full_name} ({att_status}) at {formatted_now}")

    if att_status == "Late":
        formatted_date = today.strftime("%d %B %Y") if hasattr(today, "strftime") else str(today)

        # 1. Send alert to Parent
        if student.parent_email:
            email_service.send_late_alert_email(
                to_email=student.parent_email,
                student_name=student.full_name,
                arrival_time=formatted_now,
                date_str=formatted_date,
                recipient_name=student.parent_name or "Parent / Guardian"
            )
        # 2. Send notification copy to Student
        if student.email and student.email != student.parent_email:
            email_service.send_late_alert_email(
                to_email=student.email,
                student_name=student.full_name,
                arrival_time=formatted_now,
                date_str=formatted_date,
                recipient_name=student.full_name
            )


    return {
        "status": "success",
        "message": f"Welcome {student.full_name}! Attendance marked as {att_status} at {formatted_now}.",
        "student_id": student.id,
        "student_name": student.full_name,
        "check_in": formatted_now,
        "attendance_status": att_status,
        "confidence": confidence
    }
    
class AdminFaceVerifyIn(BaseModel):
    student_id: int
    confidence: float
    bssid: str
    candidate_embedding: List[float]


@router.post("/admin-verify")
async def admin_verify_face_attendance(
    payload: AdminFaceVerifyIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """
    Admin/Teacher-assisted face verification: marks attendance for a specific student
    after verifying their face against their stored embedding.
    Used when a student's own camera is unavailable.
    """
    if not validate_wifi(payload.bssid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized WiFi network. Attendance registration denied."
        )

    student = db.query(Student).filter(Student.id == payload.student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if not isinstance(payload.candidate_embedding, list) or len(payload.candidate_embedding) != 512:
        return {"status": "failed", "error": "Invalid candidate face embedding submitted.", "confidence": 0.0}

    stored_embedding_record = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).first()
    if not stored_embedding_record:
        return {
            "status": "failed",
            "error": f"No registered face embedding found for {student.full_name}. Please register their photo first.",
            "confidence": 0.0
        }

    stored_embedding = stored_embedding_record.embedding
    if isinstance(stored_embedding, str):
        try:
            stored_embedding = json.loads(stored_embedding)
        except json.JSONDecodeError:
            return {"status": "failed", "error": "Stored face embedding is corrupted. Contact admin.", "confidence": 0.0}

    candidate_norm = _normalize_embedding(payload.candidate_embedding)
    stored_norm = _normalize_embedding(stored_embedding)
    if candidate_norm is None or stored_norm is None:
        return {"status": "failed", "error": "Invalid face embedding values submitted.", "confidence": 0.0}

    cosine_dist = _compute_cosine_distance(candidate_norm, stored_norm)
    confidence = round((1.0 - cosine_dist) * 100, 2)
    min_conf = float(settings.ai_models.get("minimum_confidence", 50.0))
    similarity_threshold = float(settings.ai_models.get("similarity_threshold", 0.50))

    if cosine_dist > similarity_threshold or confidence < min_conf:
        return {
            "status": "failed",
            "error": f"Face verification failed. The person in frame does not match {student.full_name}.",
            "confidence": confidence,
            "distance": round(cosine_dist, 4),
        }

    today = datetime.now(_IST).date()
    now_time = datetime.now(_IST).time()

    is_holiday = db.query(Holiday).filter(Holiday.date == today).first() is not None
    if is_holiday:
        return {"status": "failed", "error": "Today is a holiday. No attendance registration required."}

    existing = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.date == today
    ).first()

    if existing:
        existing.check_out = now_time
        db.commit()
        return {
            "status": "success",
            "message": f"Goodbye {student.full_name}! Check-out registered.",
            "student_id": student.id,
            "student_name": student.full_name,
            "check_in": str(existing.check_in),
            "check_out": str(now_time),
            "attendance_status": existing.status,
            "confidence": confidence
        }

    start_time_str = settings.attendance.get("start_time", "09:00:00")
    late_buffer = settings.attendance.get("late_threshold_minutes", 15)
    start_time_obj = datetime.strptime(start_time_str, "%H:%M:%S").time()
    late_threshold_time = (datetime.combine(today, start_time_obj) + timedelta(minutes=late_buffer)).time()
    att_status = "Present" if now_time <= late_threshold_time else "Late"

    record = Attendance(
        student_id=student.id,
        date=today,
        check_in=now_time,
        status=att_status,
        confidence_score=confidence,
        verification_method="Admin-Face"
    )
    db.add(record)
    db.commit()

    logger.info(f"Admin-assisted face attendance: {student.full_name} ({att_status}) at {now_time} by {getattr(current_user, 'username', 'unknown')}")

    if att_status == "Late":
        formatted_time = now_time.strftime("%I:%M %p") if hasattr(now_time, "strftime") else str(now_time)[:5]
        formatted_date = today.strftime("%d %B %Y") if hasattr(today, "strftime") else str(today)

        # 1. Send alert to Parent
        if student.parent_email:
            email_service.send_late_alert_email(
                to_email=student.parent_email,
                student_name=student.full_name,
                arrival_time=formatted_time,
                date_str=formatted_date,
                recipient_name=student.parent_name or "Parent / Guardian"
            )
        # 2. Send notification copy to Student
        if student.email and student.email != student.parent_email:
            email_service.send_late_alert_email(
                to_email=student.email,
                student_name=student.full_name,
                arrival_time=formatted_time,
                date_str=formatted_date,
                recipient_name=student.full_name
            )


    return {
        "status": "success",
        "message": f"✅ {student.full_name} marked as {att_status} via admin face verification.",
        "student_id": student.id,
        "student_name": student.full_name,
        "check_in": str(now_time),
        "attendance_status": att_status,
        "confidence": confidence
    }


@router.post("/manual", response_model=AttendanceOut)
def record_manual_attendance(
    payload: ManualAttendanceIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """Allows an educator or admin to manually log or override attendance for a student."""
    record_date = datetime.strptime(payload.date, "%Y-%m-%d").date()
    student = db.query(Student).filter(Student.id == payload.student_id, Student.is_active == True).first()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    existing = db.query(Attendance).filter(
        Attendance.student_id == payload.student_id,
        Attendance.date == record_date
    ).first()

    now_time = datetime.now(_IST).time()

    if existing:
        existing.status = payload.status
        existing.verification_method = payload.verification_method
        if payload.status in ["Present", "Late"] and not existing.check_in:
            existing.check_in = now_time
        elif payload.status in ["Absent", "Leave", "Holiday"]:
            existing.check_in = None
            existing.check_out = None
        db.commit()
        record = existing
    else:
        check_in_val = now_time if payload.status in ["Present", "Late"] else None
        record = Attendance(
            student_id=payload.student_id,
            date=record_date,
            check_in=check_in_val,
            status=payload.status,
            verification_method=payload.verification_method,
            confidence_score=100.0
        )
        db.add(record)
        db.commit()

    logger.info(f"Manual attendance update: {student.full_name} set to {payload.status} for {payload.date}")
    
    if payload.status == "Late":
        formatted_time = (record.check_in.strftime("%I:%M %p") if hasattr(record.check_in, "strftime") else str(record.check_in)[:5]) if record.check_in else datetime.now().strftime("%I:%M %p")
        formatted_date = record_date.strftime("%d %B %Y") if hasattr(record_date, "strftime") else str(record_date)
        
        if student.parent_email:
            email_service.send_late_alert_email(
                to_email=student.parent_email,
                student_name=student.full_name,
                arrival_time=formatted_time,
                date_str=formatted_date,
                recipient_name=student.parent_name or "Parent / Guardian"
            )
        if student.email and student.email != student.parent_email:
            email_service.send_late_alert_email(
                to_email=student.email,
                student_name=student.full_name,
                arrival_time=formatted_time,
                date_str=formatted_date,
                recipient_name=student.full_name
            )

    
    return {
        "id": record.id,
        "student_id": record.student_id,
        "student_name": student.full_name,
        "registration_number": student.registration_number,
        "date": str(record.date),
        "check_in": str(record.check_in) if record.check_in else None,
        "check_out": str(record.check_out) if record.check_out else None,
        "status": record.status,
        "confidence_score": record.confidence_score,
        "verification_method": record.verification_method
    }

def _dispatch_absence_alerts_task(scan_date: date):
    from src.database.connection import SessionLocal
    bg_db = SessionLocal()
    try:
        alert_service.check_and_trigger_absence_alerts(bg_db, scan_date)
    except Exception as exc:
        logger.error(f"Background absence alerts dispatch error: {exc}")
    finally:
        bg_db.close()

@router.post("/trigger-scan")
def trigger_evening_absence_scan(
    target_date: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """
    Triggers evening routine:
    1. Sets all active students who missed checking in to 'Absent' status.
    2. Dispatches absence parent alerts.
    3. Scans consecutive absences (e.g. 3 days absent) to send streak notifications.
    """
    scan_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else datetime.now(_IST).date()
    
    # Check if target_date is a registered holiday
    is_holiday = db.query(Holiday).filter(Holiday.date == scan_date).first() is not None
    if is_holiday:
        return {"message": "Selected day is a holiday. Scanner aborted."}

    # 1. Pull all active students
    active_students = db.query(Student).filter(Student.is_active == True).all()

    marked_absent_count = 0
    for s in active_students:
        existing = db.query(Attendance).filter(
            Attendance.student_id == s.id,
            Attendance.date == scan_date
        ).first()

        if not existing:
            # Create default Absent entry
            absent_record = Attendance(
                student_id=s.id,
                date=scan_date,
                status="Absent",
                verification_method="System"
            )
            db.add(absent_record)
            marked_absent_count += 1
        elif existing.check_in is not None and existing.check_out is None:
            # Auto sign-out at 16:00 if they forgot
            existing.check_out = time(16, 0, 0)

    db.commit()
    
    # 2. Trigger notifications via AlertService in background to prevent client timeouts
    if background_tasks:
        background_tasks.add_task(_dispatch_absence_alerts_task, scan_date)
        triggered_alerts = marked_absent_count
    else:
        triggered_alerts = alert_service.check_and_trigger_absence_alerts(db, scan_date)

    return {
        "message": "Daily evening scan completed successfully.",
        "marked_absent_count": marked_absent_count,
        "triggered_alerts_count": triggered_alerts
    }


@router.get("/student/monthly-analytics")
def get_student_monthly_analytics(
    student_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Returns comprehensive monthly attendance analytics, calendar heatmap data,
    and annual trend metrics for the requested student.
    """
    import calendar
    now = datetime.now(_IST)
    target_month = month or now.month
    target_year = year or now.year

    target_student_id = student_id
    if isinstance(current_user, Student):
        target_student_id = current_user.id
    elif not target_student_id:
        target_student_id = current_user.id if hasattr(current_user, "id") else None

    if not target_student_id:
        raise HTTPException(status_code=400, detail="Student ID required")

    student = db.query(Student).filter(Student.id == target_student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    num_days = calendar.monthrange(target_year, target_month)[1]
    start_d = date(target_year, target_month, 1)
    end_d = date(target_year, target_month, num_days)

    records = db.query(Attendance).filter(
        Attendance.student_id == target_student_id,
        Attendance.date >= start_d,
        Attendance.date <= end_d
    ).all()
    record_map = {r.date: r for r in records}

    holidays = db.query(Holiday).filter(
        Holiday.date >= start_d,
        Holiday.date <= end_d
    ).all()
    holiday_map = {h.date: h.name for h in holidays}

    total_working_days = 0
    present_count = 0
    late_count = 0
    absent_count = 0
    leave_count = 0
    daily_map = {}

    for d in range(1, num_days + 1):
        cur_date = date(target_year, target_month, d)
        date_str = str(cur_date)
        is_sunday = cur_date.weekday() == 6
        is_holiday = cur_date in holiday_map

        if cur_date in record_map:
            r = record_map[cur_date]
            st = r.status.capitalize()
            c_in = r.check_in.strftime("%I:%M %p") if r.check_in and hasattr(r.check_in, "strftime") else (str(r.check_in)[:5] if r.check_in else None)
            c_out = r.check_out.strftime("%I:%M %p") if r.check_out and hasattr(r.check_out, "strftime") else (str(r.check_out)[:5] if r.check_out else None)
            
            if st in ["Present", "Late"]:
                present_count += 1
                if st == "Late":
                    late_count += 1
            elif st == "Absent":
                absent_count += 1
            elif st == "Leave":
                leave_count += 1

            if not is_sunday and not is_holiday:
                total_working_days += 1

            daily_map[date_str] = {
                "status": st,
                "check_in": c_in,
                "check_out": c_out,
                "is_holiday": is_holiday,
                "holiday_name": holiday_map.get(cur_date, "")
            }
        else:
            if is_holiday:
                status_label = "Holiday"
            elif is_sunday:
                status_label = "Weekend"
            elif cur_date < now.date():
                status_label = "Unrecorded"
                total_working_days += 1
            else:
                status_label = "Upcoming"

            daily_map[date_str] = {
                "status": status_label,
                "check_in": None,
                "check_out": None,
                "is_holiday": is_holiday,
                "holiday_name": holiday_map.get(cur_date, "")
            }

    pct = round((present_count / total_working_days * 100), 1) if total_working_days > 0 else 100.0

    # Annual Month-by-Month Trend for chart
    monthly_trend = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for m in range(1, 13):
        m_start = date(target_year, m, 1)
        m_end = date(target_year, m, calendar.monthrange(target_year, m)[1])
        m_recs = db.query(Attendance).filter(
            Attendance.student_id == target_student_id,
            Attendance.date >= m_start,
            Attendance.date <= m_end,
            Attendance.status.in_(["Present", "Late"])
        ).count()
        m_total = db.query(Attendance).filter(
            Attendance.student_id == target_student_id,
            Attendance.date >= m_start,
            Attendance.date <= m_end
        ).count()
        m_pct = round((m_recs / m_total * 100), 1) if m_total > 0 else 0.0
        monthly_trend.append({"month": month_names[m - 1], "month_num": m, "percentage": m_pct, "present": m_recs})

    return {
        "student_id": target_student_id,
        "student_name": student.full_name,
        "registration_number": student.registration_number,
        "month": target_month,
        "month_name": month_names[target_month - 1],
        "year": target_year,
        "total_days": num_days,
        "total_working_days": total_working_days,
        "present_days": present_count,
        "on_time_days": max(0, present_count - late_count),
        "late_days": late_count,
        "absent_days": absent_count,
        "leave_days": leave_count,
        "percentage": pct,
        "target_percentage": 75.0,
        "is_shortage": pct < 75.0,
        "daily_map": daily_map,
        "monthly_trend": monthly_trend
    }


@router.get("/admin/matrix")
def get_admin_attendance_matrix(
    month: Optional[int] = None,
    year: Optional[int] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """
    Returns college-wide / class-wide attendance matrix for all students
    with monthly aggregates, percentage thresholds, and shortage indicators.
    """
    import calendar
    now = datetime.now(_IST)
    target_month = month or now.month
    target_year = year or now.year

    query = db.query(Student).filter(Student.is_active == True)
    if department and department.lower() != "all":
        query = query.filter(Student.department == department)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Student.full_name.ilike(search_fmt)) |
            (Student.registration_number.ilike(search_fmt)) |
            (Student.roll_number.ilike(search_fmt))
        )

    students = query.order_by(Student.registration_number).all()

    num_days = calendar.monthrange(target_year, target_month)[1]
    start_d = date(target_year, target_month, 1)
    end_d = date(target_year, target_month, num_days)

    all_records = db.query(Attendance).filter(
        Attendance.date >= start_d,
        Attendance.date <= end_d
    ).all()

    from collections import defaultdict
    student_records = defaultdict(list)
    for r in all_records:
        student_records[r.student_id].append(r)

    rows = []
    total_pct_sum = 0.0
    defaulter_count = 0

    for s in students:
        s_recs = student_records[s.id]
        total_logged = len(s_recs)
        present = sum(1 for r in s_recs if r.status in ["Present", "Late"])
        late = sum(1 for r in s_recs if r.status == "Late")
        absent = sum(1 for r in s_recs if r.status == "Absent")
        leave = sum(1 for r in s_recs if r.status == "Leave")

        effective_total = max(1, total_logged)
        pct = round((present / effective_total) * 100, 1) if total_logged > 0 else 0.0
        total_pct_sum += pct

        status_flag = "good"
        if pct < 65.0:
            status_flag = "danger"
            defaulter_count += 1
        elif pct < 75.0:
            status_flag = "warning"
            defaulter_count += 1

        rows.append({
            "id": s.id,
            "registration_number": s.registration_number,
            "roll_number": s.roll_number or s.registration_number,
            "full_name": s.full_name,
            "department": s.department or "General",
            "semester": s.semester or "1",
            "total_logged": total_logged,
            "present": present,
            "late": late,
            "absent": absent,
            "leave": leave,
            "percentage": pct,
            "status_flag": status_flag
        })

    avg_pct = round(total_pct_sum / max(1, len(students)), 1)

    return {
        "month": target_month,
        "year": target_year,
        "total_students": len(students),
        "class_average_percentage": avg_pct,
        "defaulters_count": defaulter_count,
        "matrix": rows
    }
