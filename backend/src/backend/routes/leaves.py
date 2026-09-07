import os
import shutil
from pathlib import Path
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger

from src.database.connection import get_db
from src.database.models import Admin, Student, Teacher, LeaveRequest, Attendance, AppNotification
from src.backend.dependencies import get_current_user, require_teacher, require_admin
from src.config_loader import settings
from src.backend.services.in_app_push import in_app_push_manager
from src.backend.services.email_service import email_service

router = APIRouter(prefix="/leaves", tags=["Leaves"])

class LeaveRequestOut(BaseModel):
    id: int
    applicant_type: str
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    leave_type: str
    start_date: str
    end_date: str
    reason: str
    supporting_document: Optional[str] = None
    status: str
    approval_step: int
    created_at: str

    class Config:
        from_attributes = True

@router.post("/student", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def submit_student_leave(
    student_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form(...),
    document: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Submits a student leave request with an optional supporting document."""
    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_date, "%Y-%m-%d").date()

    if end_d < start_d:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date.")

    # Prevent duplicate or overlapping pending/approved leave requests for this student
    existing_overlap = db.query(LeaveRequest).filter(
        LeaveRequest.student_id == student_id,
        LeaveRequest.status.in_(["Pending", "FacultyApproved", "ManagerApproved", "Approved"]),
        LeaveRequest.start_date <= end_d,
        LeaveRequest.end_date >= start_d
    ).first()

    if existing_overlap:
        if existing_overlap.status == "Approved":
            raise HTTPException(
                status_code=400,
                detail=f"An approved leave request already exists for the period {existing_overlap.start_date} to {existing_overlap.end_date}."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"You already have a pending leave request ({existing_overlap.status}) for the period {existing_overlap.start_date} to {existing_overlap.end_date}."
            )

    doc_path = None
    if document:
        docs_dir = Path(settings.system.get("documents_dir"))
        student_docs_dir = docs_dir / "students" / student.registration_number
        student_docs_dir.mkdir(parents=True, exist_ok=True)
        
        file_ext = Path(document.filename).suffix or ".pdf"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doc_filename = f"leave_{start_date}_{timestamp}{file_ext}"
        target_path = student_docs_dir / doc_filename
        
        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(document.file, buffer)
            doc_path = str(target_path)
        except Exception as e:
            logger.error(f"Failed to save leave document: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded document")

    leave_req = LeaveRequest(
        applicant_type="student",
        student_id=student_id,
        leave_type="Academic",
        start_date=start_d,
        end_date=end_d,
        reason=reason,
        supporting_document=doc_path,
        status="Pending",
        approval_step=1 # Step 1: Faculty Review
    )
    db.add(leave_req)
    db.flush()

    notification_message = (
        f"{student.full_name} ({student.registration_number}) requested leave "
        f"from {start_date} to {end_date}."
    )
    for admin in db.query(Admin).filter(Admin.is_active == True).all():
        db.add(AppNotification(
            recipient_role="admin",
            recipient_user_id=admin.id,
            notification_type="leave_request",
            title="New student leave request",
            message=notification_message,
        ))
    for hr in db.query(Teacher).filter(Teacher.is_active == True, Teacher.role == "hr").all():
        db.add(AppNotification(
            recipient_role="hr",
            recipient_user_id=hr.id,
            notification_type="leave_request",
            title="New student leave request",
            message=notification_message,
        ))
    db.commit()

    push_payload = {
        "type": "leave_request",
        "title": "New student leave request",
        "message": notification_message,
    }
    for admin in db.query(Admin).filter(Admin.is_active == True).all():
        in_app_push_manager.push("admin", admin.id, push_payload)
        if admin.email:
            try:
                email_service.send_leave_request_notification(
                    to_email=admin.email,
                    admin_name=admin.full_name,
                    student_name=student.full_name,
                    registration_number=student.registration_number,
                    start_date=str(start_d),
                    end_date=str(end_d),
                    reason=reason,
                    leave_type=leave_req.leave_type
                )
            except Exception as mail_err:
                logger.warning(f"Could not send leave email to admin {admin.email}: {mail_err}")

    for hr in db.query(Teacher).filter(Teacher.is_active == True, Teacher.role == "hr").all():
        in_app_push_manager.push("hr", hr.id, push_payload)

    logger.info(f"Student leave submitted: {student.full_name} for {start_date} to {end_date}")
    return build_leave_response(leave_req)

@router.post("/staff", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def submit_staff_leave(
    teacher_id: int = Form(...),
    leave_type: str = Form(...), # Casual, Sick, Half Day
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db)
):
    """Submits a staff/teacher leave request."""
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_active == True).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_date, "%Y-%m-%d").date()

    if end_d < start_d:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date.")

    # Prevent duplicate or overlapping staff leave requests
    existing_overlap = db.query(LeaveRequest).filter(
        LeaveRequest.teacher_id == teacher_id,
        LeaveRequest.status.in_(["Pending", "ManagerApproved", "Approved"]),
        LeaveRequest.start_date <= end_d,
        LeaveRequest.end_date >= start_d
    ).first()

    if existing_overlap:
        if existing_overlap.status == "Approved":
            raise HTTPException(
                status_code=400,
                detail=f"An approved staff leave already exists for {existing_overlap.start_date} to {existing_overlap.end_date}."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"You already have a pending leave request for {existing_overlap.start_date} to {existing_overlap.end_date}."
            )

    if leave_type not in ["Casual", "Sick", "Half Day"]:
        raise HTTPException(status_code=400, detail="Invalid leave type. Choose Casual, Sick, or Half Day.")

    leave_req = LeaveRequest(
        applicant_type="staff",
        teacher_id=teacher_id,
        leave_type=leave_type,
        start_date=start_d,
        end_date=end_d,
        reason=reason,
        status="Pending",
        approval_step=1 # Step 1: Manager Review
    )
    db.add(leave_req)
    db.commit()

    logger.info(f"Staff leave submitted: {teacher.full_name} for {start_date} to {end_date}")
    return build_leave_response(leave_req)

@router.get("/pending", response_model=List[LeaveRequestOut])
def get_pending_leaves(
    db: Session = Depends(get_db),
    current_user_data: dict = Depends(get_current_user)
):
    """
    Returns pending leave requests requiring review by the current user.
    - Faculty (teachers) see Student step 1 requests.
    - Managers see Staff step 1 requests.
    - Admins see Student step 2 (FacultyApproved) & Staff step 2 (ManagerApproved) requests.
    """
    user = current_user_data["user"]
    role = current_user_data["role"]

    if role == "admin":
        # Admin can approve Student step 2 and Staff step 2
        student_reqs = db.query(LeaveRequest).filter(
            LeaveRequest.applicant_type == "student",
            LeaveRequest.status == "FacultyApproved"
        ).all()
        
        staff_reqs = db.query(LeaveRequest).filter(
            LeaveRequest.applicant_type == "staff",
            LeaveRequest.status == "ManagerApproved"
        ).all()
        
        # Also return original Pending student requests in case Admin wants to override
        all_student_reqs = db.query(LeaveRequest).filter(
            LeaveRequest.applicant_type == "student",
            LeaveRequest.status == "Pending"
        ).all()
        
        return [build_leave_response(r) for r in (student_reqs + staff_reqs + all_student_reqs)]

    elif role == "teacher":
        # Teacher reviews student step 1
        reqs = db.query(LeaveRequest).filter(
            LeaveRequest.applicant_type == "student",
            LeaveRequest.status == "Pending",
            LeaveRequest.approval_step == 1
        ).all()
        return [build_leave_response(r) for r in reqs]

    elif role == "manager":
        # Manager reviews staff step 1
        reqs = db.query(LeaveRequest).filter(
            LeaveRequest.applicant_type == "staff",
            LeaveRequest.status == "Pending",
            LeaveRequest.approval_step == 1
        ).all()
        return [build_leave_response(r) for r in reqs]

    elif role == "hr":
        # HR reviews staff step 2
        reqs = db.query(LeaveRequest).filter(
            LeaveRequest.applicant_type == "staff",
            LeaveRequest.status == "ManagerApproved"
        ).all()
        return [build_leave_response(r) for r in reqs]
    elif role == "student":
        # Student sees all their own leave requests
        reqs = db.query(LeaveRequest).filter(
            LeaveRequest.applicant_type == "student",
            LeaveRequest.student_id == user.id
        ).all()
        return [build_leave_response(r) for r in reqs]

    return []

@router.get("/{leave_id}/document")
def get_leave_document(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user_data: dict = Depends(get_current_user)
):
    """Serves the supporting document for a leave request if it exists and hasn't been deleted."""
    leave_req = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave_req:
        raise HTTPException(status_code=404, detail="Leave request not found")

    user = current_user_data["user"]
    user_role = current_user_data["role"]

    if user_role == "student" and leave_req.student_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this leave document")

    if not leave_req.supporting_document:
        raise HTTPException(
            status_code=404, 
            detail="No supporting document associated with this leave request or document was permanently deleted post-review."
        )

    doc_path = Path(leave_req.supporting_document)
    if not doc_path.is_absolute():
        doc_path = (Path.cwd() / doc_path).resolve()

    if not doc_path.exists():
        docs_dir = Path(settings.system.get("documents_dir"))
        fallback_matches = list(docs_dir.rglob(doc_path.name))
        if fallback_matches:
            doc_path = fallback_matches[0]
        else:
            raise HTTPException(status_code=404, detail="Document file does not exist on storage or was permanently deleted.")

    return FileResponse(path=str(doc_path), filename=doc_path.name, media_type="application/octet-stream")

def delete_leave_document_if_final(leave_req: LeaveRequest):
    """Deletes supporting document permanently if leave workflow reaches final status (Approved or Rejected)."""
    if leave_req.status in ["Approved", "Rejected"] and leave_req.supporting_document:
        doc_path = Path(leave_req.supporting_document)
        try:
            if doc_path.exists():
                doc_path.unlink()
                logger.info(f"Permanently deleted supporting document: {doc_path} for leave ID {leave_req.id}")
        except Exception as e:
            logger.error(f"Failed to delete supporting document {doc_path}: {e}")
        leave_req.supporting_document = None

@router.post("/{leave_id}/approve", response_model=LeaveRequestOut)
def approve_leave(
    leave_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user_data: dict = Depends(get_current_user)
):
    """Progresses the leave request through the approval pipeline or completes it."""
    user_role = current_user_data["role"]
    if user_role == "student":
        raise HTTPException(status_code=403, detail="Students are not allowed to approve leave requests.")

    leave_req = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave_req:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if leave_req.status in ["Approved", "Rejected"]:
        raise HTTPException(status_code=400, detail=f"Cannot approve request with terminal status: {leave_req.status}")

    # Logic for Student Leave: 1 step (Faculty -> Approved)
    if leave_req.applicant_type == "student":
        leave_req.status = "Approved"
        leave_req.approval_step = 2
        apply_leave_attendance_records(db, leave_req.student_id, leave_req.start_date, leave_req.end_date)
        
    # Logic for Teacher Leave: 2 steps (HR -> Approved)
    elif leave_req.applicant_type == "teacher":
        if user_role == "hr" and leave_req.approval_step == 1:
            leave_req.status = "Approved"
            leave_req.approval_step = 2
        elif user_role == "admin":
            leave_req.status = "Approved"
            leave_req.approval_step = 2
        else:
            raise HTTPException(status_code=400, detail="Unauthorized approval action for staff leave workflow")

    delete_leave_document_if_final(leave_req)
    db.commit()
    logger.info(f"Leave ID {leave_id} approved. New status: {leave_req.status}")

    # Send decision email asynchronously in background
    if leave_req.status == "Approved" and leave_req.applicant_type == "student" and leave_req.student:
        st = leave_req.student
        recipients = [e for e in [st.email, st.parent_email] if e and "@" in e]
        for recipient_email in set(recipients):
            background_tasks.add_task(
                email_service.send_leave_decision_notification,
                to_email=recipient_email,
                student_name=st.full_name,
                registration_number=st.registration_number,
                start_date=str(leave_req.start_date),
                end_date=str(leave_req.end_date),
                status="Approved"
            )

    return build_leave_response(leave_req)

@router.post("/{leave_id}/reject", response_model=LeaveRequestOut)
def reject_leave(
    leave_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user_data: dict = Depends(get_current_user)
):
    """Rejects the leave request (ends the workflow)."""
    user_role = current_user_data["role"]
    if user_role == "student":
        raise HTTPException(status_code=403, detail="Students are not allowed to reject leave requests.")

    leave_req = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave_req:
        raise HTTPException(status_code=404, detail="Leave request not found")

    leave_req.status = "Rejected"
    delete_leave_document_if_final(leave_req)
    db.commit()
    logger.info(f"Leave ID {leave_id} rejected.")

    # Send rejection email asynchronously in background
    if leave_req.applicant_type == "student" and leave_req.student:
        st = leave_req.student
        recipients = [e for e in [st.email, st.parent_email] if e and "@" in e]
        for recipient_email in set(recipients):
            background_tasks.add_task(
                email_service.send_leave_decision_notification,
                to_email=recipient_email,
                student_name=st.full_name,
                registration_number=st.registration_number,
                start_date=str(leave_req.start_date),
                end_date=str(leave_req.end_date),
                status="Rejected"
            )

    return build_leave_response(leave_req)

def apply_leave_attendance_records(db: Session, student_id: int, start_date: date, end_date: date):
    """Automatically marks attendance status as 'Leave' for the duration of the approved leave."""
    curr_date = start_date
    while curr_date <= end_date:
        # Check if attendance record exists
        existing = db.query(Attendance).filter(
            Attendance.student_id == student_id,
            Attendance.date == curr_date
        ).first()

        if existing:
            existing.status = "Leave"
            existing.verification_method = "Leave"
            existing.check_in = None
            existing.check_out = None
        else:
            rec = Attendance(
                student_id=student_id,
                date=curr_date,
                status="Leave",
                verification_method="Leave"
            )
            db.add(rec)
        curr_date += timedelta(days=1)

def build_leave_response(lr: LeaveRequest) -> dict:
    """Helper to convert LeaveRequest object into serializable dict."""
    student_name = lr.student.full_name if lr.student else None
    teacher_name = lr.teacher.full_name if lr.teacher else None
    
    doc_path_str = None
    if lr.supporting_document:
        p = Path(lr.supporting_document)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.exists():
            doc_path_str = str(p)
        else:
            docs_dir = Path(settings.system.get("documents_dir"))
            fallback_matches = list(docs_dir.rglob(p.name))
            if fallback_matches:
                doc_path_str = str(fallback_matches[0])

    return {
        "id": lr.id,
        "applicant_type": lr.applicant_type,
        "student_id": lr.student_id,
        "student_name": student_name,
        "teacher_id": lr.teacher_id,
        "teacher_name": teacher_name,
        "leave_type": lr.leave_type,
        "start_date": str(lr.start_date),
        "end_date": str(lr.end_date),
        "reason": lr.reason,
        "supporting_document": doc_path_str,
        "status": lr.status,
        "approval_step": lr.approval_step,
        "created_at": str(lr.created_at)
    }
