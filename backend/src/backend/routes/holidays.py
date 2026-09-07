from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger

from src.database.connection import get_db
from src.database.models import Student, Teacher, Holiday, Attendance, Notification, AppNotification
from src.backend.dependencies import require_admin_or_hr
from src.backend.services.notification import notification_service
from src.backend.services.in_app_push import in_app_push_manager
from src.backend.services.email_service import email_service

router = APIRouter(prefix="/holidays", tags=["Holidays"])

class HolidayOut(BaseModel):
    id: int
    date: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True

class HolidayCreate(BaseModel):
    date: str # YYYY-MM-DD
    name: str
    description: Optional[str] = None

@router.get("/", response_model=List[HolidayOut])
def get_holidays(db: Session = Depends(get_db)):
    """Lists all registered holidays."""
    holidays = db.query(Holiday).order_by(Holiday.date.asc()).all()
    return [{
        "id": h.id,
        "date": str(h.date),
        "name": h.name,
        "description": h.description
    } for h in holidays]

def parse_holiday_date(date_str: str) -> date:
    """
    Parses a date string supporting multiple standard formats:
    YYYY-MM-DD, YYYY-DD-MM, DD-MM-YYYY, DD/MM/YYYY, YYYY/MM/DD
    """
    date_str = date_str.strip()
    formats = [
        "%Y-%m-%d",  # 2026-10-15 (Standard ISO)
        "%Y-%d-%m",  # 2026-15-10
        "%d-%m-%Y",  # 15-10-2026
        "%d/%m/%Y",  # 15/10/2026
        "%Y/%m/%d",  # 2026/10/15
        "%d.%m.%Y",  # 15.10.2026
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"Invalid date '{date_str}'. Please provide a valid date in YYYY-MM-DD format (e.g. 2026-10-15)."
    )

@router.post("/", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
def create_holiday(
    payload: HolidayCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_or_hr)
):
    """
    Creates a holiday, automatically updates the attendance roster on that date
    for all active students to 'Holiday', and broadcasts SMTP emails and WhatsApp/Push alerts.
    """
    holiday_date = parse_holiday_date(payload.date)

    # Check if holiday already exists
    existing = db.query(Holiday).filter(Holiday.date == holiday_date).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A holiday '{existing.name}' already exists on {holiday_date}.")

    # 1. Create Holiday database entry
    holiday = Holiday(
        date=holiday_date,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None
    )

    db.add(holiday)
    db.flush()

    # 2. Automark Attendance roster on that date for all active students as 'Holiday'
    active_students = db.query(Student).filter(Student.is_active == True).all()
    for student in active_students:
        att_record = db.query(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.date == holiday_date
        ).first()

        if att_record:
            att_record.status = "Holiday"
            att_record.verification_method = "Holiday"
            att_record.check_in = None
            att_record.check_out = None
        else:
            new_att = Attendance(
                student_id=student.id,
                date=holiday_date,
                status="Holiday",
                verification_method="Holiday"
            )
            db.add(new_att)

    # Calculate Resume Date (holiday_date + 1 day)
    resume_date = holiday_date + timedelta(days=1)
    
    # Format dates for message template
    holiday_str = holiday_date.strftime("%d %B %Y")
    resume_str = resume_date.strftime("%d %B %Y")

    # 3. Queue SMTP Email Broadcast to all active students with email addresses
    students_email_list = [
        {"name": s.full_name, "email": s.email}
        for s in active_students
        if s.email and "@" in s.email
    ]

    if students_email_list:
        background_tasks.add_task(
            email_service.broadcast_holiday_email_to_students,
            students=students_email_list,
            holiday_name=payload.name,
            holiday_date_str=holiday_str,
            resume_date_str=resume_str,
            description=payload.description or ""
        )
        logger.info(f"Queued SMTP holiday announcement email broadcast for {len(students_email_list)} student(s).")

    # 4. Compile Recipients list for multi-channel broadcast (WhatsApp/Push/Staff)
    recipients = []
    
    # Add Students & Parents
    for s in active_students:
        # Parent Broadcast
        if s.parent_phone:
            recipients.append({
                "role": "parent",
                "phone": s.parent_phone,
                "email": s.parent_email,
                "push_token": f"parent_token_{s.registration_number}"
            })
        # Student Broadcast
        if s.phone:
            recipients.append({
                "role": "student",
                "phone": s.phone,
                "email": s.email,
                "push_token": f"student_token_{s.registration_number}"
            })

    # Add Staff/Teachers
    active_staff = db.query(Teacher).filter(Teacher.is_active == True).all()
    for t in active_staff:
        if t.phone:
            recipients.append({
                "role": "staff",
                "phone": t.phone,
                "email": t.email,
                "push_token": f"staff_token_{t.employee_id}"
            })

    # 5. Trigger multi-channel notifications
    sent_count = notification_service.broadcast_holiday(
        holiday_name=payload.name,
        holiday_date_str=holiday_str,
        resume_date_str=resume_str,
        recipients=recipients
    )

    # Create an in-app alert and notification logs
    for student in active_students:
        db.add(AppNotification(
            recipient_role="student",
            recipient_user_id=student.id,
            notification_type="holiday",
            title=f"Holiday update: {payload.name}",
            message=f"{payload.name} is on {holiday_str}. Classes resume on {resume_str}.",
        ))
        if student.email and "@" in student.email:
            db.add(Notification(
                recipient_type="Student",
                recipient_id=student.id,
                notification_type="HolidayEmail",
                recipient_address=student.email,
                message=f"Holiday Notice: {payload.name} on {holiday_str}. Classes resume on {resume_str}.",
                status="Dispatched",
                sent_at=datetime.utcnow()
            ))

    # Log the global holiday event execution
    db_notif_log = Notification(
        recipient_type="System",
        recipient_id=holiday.id,
        notification_type="Broadcast",
        recipient_address="ALL_STUDENTS_SMTP",
        message=f"Dispatched holiday '{payload.name}' on {holiday_str} to {len(students_email_list)} student emails.",
        status="Sent",
        sent_at=datetime.utcnow()
    )
    db.add(db_notif_log)
    
    db.commit()

    push_payload = {
        "type": "holiday",
        "title": f"Holiday update: {payload.name}",
        "message": f"{payload.name} is on {holiday_str}. Classes resume on {resume_str}.",
    }
    for student in active_students:
        in_app_push_manager.push("student", student.id, push_payload)

    logger.info(f"Holiday '{payload.name}' created on {payload.date}. Automated SMTP emails and push alerts triggered.")

    return {
        "id": holiday.id,
        "date": str(holiday.date),
        "name": holiday.name,
        "description": holiday.description
    }

