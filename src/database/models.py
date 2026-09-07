from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, Time, DateTime, Text, ForeignKey, Boolean, JSON
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(String(50), default="admin") # superadmin, admin
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    activity_logs = relationship("ActivityLog", back_populates="admin")

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    department = Column(String(100), nullable=True)
    role = Column(String(50), default="teacher") # teacher, manager, hr, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    leave_requests = relationship("LeaveRequest", back_populates="teacher")
    activity_logs = relationship("ActivityLog", back_populates="teacher")

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    registration_number = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    parent_name = Column(String(100), nullable=False)
    parent_phone = Column(String(20), nullable=False)
    parent_email = Column(String(100), nullable=True)
    class_name = Column(String(50), nullable=False)
    photo_path = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    attendance_records = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="student", cascade="all, delete-orphan")
    face_embeddings = relationship("FaceEmbedding", back_populates="student", cascade="all, delete-orphan")
    achievements = relationship("Achievement", back_populates="student", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="student", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="student", cascade="all, delete-orphan")


class UserSession(Base):
    """A server-side record for an authenticated student device session."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(128), unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="sessions")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    otp_code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    student = relationship("Student", back_populates="password_reset_tokens")

class EmailVerificationToken(Base):
    """A record for verifying a Gmail/email address via OTP before registration/profile activation."""
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False, index=True)
    username = Column(String(50), nullable=True)
    otp_code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AppNotification(Base):
    """In-app notification delivered to one authenticated application user."""
    __tablename__ = "app_notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_role = Column(String(50), nullable=False, index=True)
    recipient_user_id = Column(Integer, nullable=False, index=True)
    notification_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    date = Column(Date, index=True, nullable=False)
    check_in = Column(Time, nullable=True)
    check_out = Column(Time, nullable=True)
    status = Column(String(20), nullable=False) # Present, Late, Absent, Leave, Holiday
    confidence_score = Column(Float, nullable=True)
    verification_method = Column(String(50), default="Face") # Face, Manual, RFID, Password, Leave, Holiday
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="attendance_records")

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    applicant_type = Column(String(20), nullable=False) # student, staff
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    
    # Common fields
    leave_type = Column(String(50), nullable=False) # Casual, Sick, Half Day, Academic
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    supporting_document = Column(String(255), nullable=True) # file path
    
    # Workflow status
    # Students: Pending -> FacultyApproved -> AdminApproved
    # Staff: Pending -> ManagerApproved -> HRApproved
    status = Column(String(50), default="Pending") # Pending, Approved, Rejected, FacultyApproved, ManagerApproved
    approval_step = Column(Integer, default=1) # 1, 2, 3 (stages of workflow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="leave_requests")
    teacher = relationship("Teacher", back_populates="leave_requests")

class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_type = Column(String(50), nullable=False) # Student, Parent, Teacher, Admin
    recipient_id = Column(Integer, nullable=True)
    notification_type = Column(String(50), nullable=False) # WhatsApp, Email, Push, SMS
    recipient_address = Column(String(100), nullable=False) # phone or email
    message = Column(Text, nullable=False)
    status = Column(String(50), default="Pending") # Pending, Sent, Failed
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    embedding = Column(JSON, nullable=False) # Holds list of floats
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="face_embeddings")

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(50), nullable=False) # Admin, Teacher, Student, System
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    action = Column(String(100), nullable=False) # Login, Marked Attendance, Added Student, Approved Leave
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin = relationship("Admin", back_populates="activity_logs")
    teacher = relationship("Teacher", back_populates="activity_logs")

class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    title = Column(String(100), nullable=False) # e.g. 100% Monthly Attendance
    description = Column(Text, nullable=True)
    points = Column(Integer, default=0)
    earned_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="achievements")

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True) # attendance, notification, security
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MonthlyReportArchive(Base):
    """A report file generated before its source attendance rows are archived."""
    __tablename__ = "monthly_report_archives"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    report_type = Column(String(20), nullable=False, default="student")
    file_path = Column(String(500), nullable=False)
    attendance_rows_archived = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
