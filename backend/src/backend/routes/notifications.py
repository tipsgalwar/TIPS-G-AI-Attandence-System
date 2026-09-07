from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.dependencies import get_current_user
from src.database.connection import get_db
from src.database.models import Admin, AppNotification, Student, Teacher, UserSession
from src.backend.services.auth_service import decode_access_token
from src.backend.services.in_app_push import in_app_push_manager

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class AppNotificationOut(BaseModel):
    id: int
    notification_type: str
    title: str
    message: str
    created_at: str
    read_at: Optional[str] = None


@router.get("/", response_model=List[AppNotificationOut])
def get_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Returns only the notifications addressed to the signed-in account."""
    user = current_user["user"]
    query = db.query(AppNotification).filter(
        AppNotification.recipient_role == current_user["role"],
        AppNotification.recipient_user_id == user.id,
    )
    if unread_only:
        query = query.filter(AppNotification.read_at == None)
    notifications = query.order_by(AppNotification.created_at.desc()).limit(100).all()
    return [
        {
            "id": item.id,
            "notification_type": item.notification_type,
            "title": item.title,
            "message": item.message,
            "created_at": item.created_at.isoformat(),
            "read_at": item.read_at.isoformat() if item.read_at else None,
        }
        for item in notifications
    ]


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user = current_user["user"]
    notification = db.query(AppNotification).filter(
        AppNotification.id == notification_id,
        AppNotification.recipient_role == current_user["role"],
        AppNotification.recipient_user_id == user.id,
    ).first()
    if notification and notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
    return {"status": "success"}
@router.websocket("/ws")
async def notification_socket(websocket: WebSocket, token: str):
    """Authenticated live notification channel for one desktop application login."""
    payload = decode_access_token(token)
    username = payload.get("sub") if payload else None
    role = payload.get("role") if payload else None
    if not username or not role:
        await websocket.close(code=1008)
        return

    from src.database.connection import SessionLocal
    db = SessionLocal()
    try:
        if role == "student":
            user = db.query(Student).filter(Student.registration_number == username, Student.is_active == True).first()
            session_id = payload.get("sid")
            session = db.query(UserSession).filter(
                UserSession.session_id == session_id,
                UserSession.student_id == user.id if user else False,
                UserSession.revoked_at == None,
            ).first()
            if not user or not session:
                await websocket.close(code=1008)
                return
        elif role == "admin":
            user = db.query(Admin).filter(Admin.username == username, Admin.is_active == True).first()
        elif role in ["teacher", "manager", "hr"]:
            user = db.query(Teacher).filter(Teacher.username == username, Teacher.is_active == True).first()
        else:
            user = None
        if not user:
            await websocket.close(code=1008)
            return
        user_id = user.id
    finally:
        db.close()

    await in_app_push_manager.connect(websocket, role, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        in_app_push_manager.disconnect(websocket, role, user_id)