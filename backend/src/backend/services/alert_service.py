from datetime import date, timedelta
from sqlalchemy.orm import Session
from loguru import logger

from src.database.models import Student, Attendance, Notification
from src.backend.services.notification import notification_service
from src.backend.services.email_service import EmailService
from src.config_loader import settings

email_service = EmailService()

class AlertService:
    def check_and_trigger_absence_alerts(self, db: Session, target_date: date):
        """
        Scans attendance for the target_date and triggers alerts:
        1. Parent email notification for single-day absence.
        2. Parent WhatsApp / SMS notification.
        3. Parental alert for 3 consecutive absences.
        """
        logger.info(f"Running absence alerts scanner for date: {target_date}")
        
        # 1. Get all students marked 'Absent' on this day
        absences = db.query(Attendance).filter(
            Attendance.date == target_date,
            Attendance.status == "Absent"
        ).all()

        triggered_alerts_count = 0

        for record in absences:
            student = record.student
            if not student or not student.is_active:
                continue

            # Check single-day alert
            if settings.attendance.get("notify_parents_on_absence", True):
                parent_phone = student.parent_phone
                parent_email = student.parent_email or student.email
                parent_name = student.parent_name
                student_name = student.full_name
                date_str = target_date.strftime('%d %B %Y')
                
                msg = f"Dear {parent_name or 'Parent'}, {student_name} was absent today ({date_str}). Regards, TIPS-G Administration"
                
                # Dispatch Email to Parent
                if parent_email:
                    email_sent = email_service.send_absence_alert_email(parent_email, parent_name, student_name, date_str)
                    db_email_notif = Notification(
                        recipient_type="Parent",
                        recipient_id=student.id,
                        notification_type="Email",
                        recipient_address=parent_email,
                        message=msg,
                        status="Sent" if email_sent else "Failed"
                    )
                    db.add(db_email_notif)
                    triggered_alerts_count += 1

                # Dispatch WhatsApp / Phone notification
                if parent_phone:
                    notification_service.send_whatsapp(parent_phone, msg)
                    db_notif = Notification(
                        recipient_type="Parent",
                        recipient_id=student.id,
                        notification_type="WhatsApp",
                        recipient_address=parent_phone,
                        message=msg,
                        status="Sent"
                    )
                    db.add(db_notif)
                    triggered_alerts_count += 1

            # 2. Check consecutive absences (e.g. 3 consecutive days)
            consecutive_limit = settings.attendance.get("consecutive_absent_days_trigger", 3)
            
            # Find the last N school/attendance days for this student
            # We look at the student's attendance records sorted descending by date
            recent_attendance = db.query(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.date <= target_date
            ).order_by(Attendance.date.desc()).limit(consecutive_limit).all()

            # Verify if they are all 'Absent' and we have at least N records
            if len(recent_attendance) == consecutive_limit and all(r.status == "Absent" for r in recent_attendance):
                # Check if we've already triggered consecutive alert recently to avoid spamming
                # For simplicity, we just trigger it
                streak_msg = f"Alert: Student {student.full_name} has been absent for {consecutive_limit} consecutive days."
                logger.warning(streak_msg)

                # Send to Parents & Admin
                parent_phone = student.parent_phone
                parent_streak_msg = f"Dear {parent_name}, {student_name} has been absent for {consecutive_limit} consecutive days. Please contact the school office. Regards, TIPS-G Administration"
                
                notification_service.send_whatsapp(parent_phone, parent_streak_msg)
                
                db_notif_streak = Notification(
                    recipient_type="Parent",
                    recipient_id=student.id,
                    notification_type="WhatsApp",
                    recipient_address=parent_phone,
                    message=parent_streak_msg,
                    status="Sent"
                )
                db.add(db_notif_streak)
                triggered_alerts_count += 1
                
        db.commit()
        logger.info(f"Absence alert scan complete. Triggered {triggered_alerts_count} notifications.")
        return triggered_alerts_count

alert_service = AlertService()
