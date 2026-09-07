import os
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO
from loguru import logger

from src.database.models import Student, Teacher, Attendance, LeaveRequest, Holiday, MonthlyReportArchive
from src.config_loader import settings

class ReportService:
    def archive_completed_attendance_months(self, db: Session) -> int:
        """Save Excel reports for completed calendar months, then clear those rows.

        A report row is inserted only after its file has been written successfully;
        this makes the operation safe to retry after a server restart.
        """
        today = date.today()
        current_month_start = today.replace(day=1)
        report_dir = Path(settings.system["storage_dir"]) / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        pending_dates = db.query(Attendance.date).filter(
            Attendance.date < current_month_start
        ).distinct().all()
        periods = sorted({(row[0].year, row[0].month) for row in pending_dates})
        archives_created = 0

        for year, month in periods:
            exists = db.query(MonthlyReportArchive).filter(
                MonthlyReportArchive.year == year,
                MonthlyReportArchive.month == month,
                MonthlyReportArchive.report_type == "student"
            ).first()
            if exists:
                continue

            report_data = self.get_student_monthly_data(db, year, month)
            file_path = report_dir / f"student_monthly_{year}_{month:02d}.xlsx"
            with open(file_path, "wb") as report_file:
                report_file.write(self.generate_excel(report_data, "Student Monthly Attendance Report").getvalue())

            start_date = date(year, month, 1)
            end_date = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1))
            rows_archived = db.query(Attendance).filter(
                Attendance.date >= start_date,
                Attendance.date < end_date
            ).delete(synchronize_session=False)
            db.add(MonthlyReportArchive(
                year=year,
                month=month,
                report_type="student",
                file_path=str(file_path),
                attendance_rows_archived=rows_archived
            ))
            db.commit()
            archives_created += 1
            logger.info(f"Archived {rows_archived} attendance rows for {year}-{month:02d}: {file_path}")

        return archives_created
    def get_daily_summary(self, db: Session, target_date: date) -> dict:
        """
        Calculates student statistics for a specific date.
        """
        total_students = db.query(func.count(Student.id)).filter(Student.is_active == True).scalar() or 0
        
        # Check if target_date is a registered holiday
        is_holiday = db.query(Holiday).filter(Holiday.date == target_date).first() is not None
        
        if is_holiday:
            return {
                "date": str(target_date),
                "total_students": total_students,
                "present": 0,
                "absent": 0,
                "late": 0,
                "leave": 0,
                "holiday": total_students,
                "is_holiday": True
            }

        # Count statuses
        attendance_counts = db.query(
            Attendance.status, func.count(Attendance.id)
        ).filter(Attendance.date == target_date).group_by(Attendance.status).all()

        counts = {status: count for status, count in attendance_counts}
        
        present = counts.get("Present", 0)
        late = counts.get("Late", 0)
        absent = counts.get("Absent", 0)
        leave = counts.get("Leave", 0)
        
        # If any active student is unaccounted for, they should count as absent by default
        unaccounted = total_students - (present + late + absent + leave)
        if unaccounted > 0:
            absent += unaccounted

        return {
            "date": str(target_date),
            "total_students": total_students,
            "present": present,
            "absent": absent,
            "late": late,
            "leave": leave,
            "holiday": 0,
            "is_holiday": False
        }

    def get_student_monthly_data(self, db: Session, year: int, month: int) -> list:
        """
        Aggregates monthly data for students.
        """
        start_date = date(year, month, 1)
        # End date calculation
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        # Count total holidays in month
        holidays_count = db.query(func.count(Holiday.id)).filter(
            Holiday.date >= start_date, Holiday.date <= end_date
        ).scalar() or 0

        # Total days in month
        total_days = (end_date - start_date).days + 1
        school_days = total_days - holidays_count

        students = db.query(Student).filter(Student.is_active == True).all()
        report_data = []

        for s in students:
            # Query attendance counts
            att_records = db.query(Attendance).filter(
                Attendance.student_id == s.id,
                Attendance.date >= start_date,
                Attendance.date <= end_date
            ).all()

            present_days = sum(1 for r in att_records if r.status in ["Present", "Late"])
            late_days = sum(1 for r in att_records if r.status == "Late")
            absent_days = sum(1 for r in att_records if r.status == "Absent")
            leave_days = sum(1 for r in att_records if r.status == "Leave")

            # Fallback: if student has no records for some days, treat difference as absent
            tracked_days = len(att_records)
            if tracked_days < school_days:
                absent_days += (school_days - tracked_days)

            att_pct = (present_days / school_days * 100) if school_days > 0 else 100.0

            report_data.append({
                "registration_number": s.registration_number,
                "full_name": s.full_name,
                "class_name": s.class_name,
                "attendance_percentage": round(att_pct, 2),
                "present_days": present_days,
                "late_days": late_days,
                "absent_days": absent_days,
                "leaves_taken": leave_days
            })
        
        return report_data

    def get_staff_monthly_data(self, db: Session, year: int, month: int) -> list:
        """
        Aggregates monthly data for staff/teachers.
        """
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        holidays_count = db.query(func.count(Holiday.id)).filter(
            Holiday.date >= start_date, Holiday.date <= end_date
        ).scalar() or 0

        total_days = (end_date - start_date).days + 1
        work_days = total_days - holidays_count

        staff_list = db.query(Teacher).filter(Teacher.is_active == True).all()
        report_data = []

        # Annual Base Leaves
        BASE_CASUAL_LEAVES = 12
        BASE_SICK_LEAVES = 10

        for t in staff_list:
            # For teachers, we mock attendance check-ins because they check in via database/app
            # and count leave requests approved.
            approved_leaves = db.query(LeaveRequest).filter(
                LeaveRequest.teacher_id == t.id,
                LeaveRequest.applicant_type == "staff",
                LeaveRequest.status == "Approved",
                LeaveRequest.start_date >= date(year, 1, 1), # calendar year leave balance
                LeaveRequest.end_date <= date(year, 12, 31)
            ).all()

            # Calculate total leaves taken in this year
            leaves_taken_ytd = 0
            leaves_taken_this_month = 0
            for lr in approved_leaves:
                days = (lr.end_date - lr.start_date).days + 1
                leaves_taken_ytd += days
                
                # Check if it was in the current month
                if lr.start_date.month == month:
                    leaves_taken_this_month += days

            # Mock some check-ins based on database or full completion
            # In a real app we'd track their attendance table records (if staff checked in too)
            # For simplicity, we assume staff is present except on leave days
            present_days = work_days - leaves_taken_this_month
            late_days = 0 # Dummy late count for mock

            att_pct = (present_days / work_days * 100) if work_days > 0 else 100.0
            leave_balance = (BASE_CASUAL_LEAVES + BASE_SICK_LEAVES) - leaves_taken_ytd

            report_data.append({
                "employee_id": t.employee_id,
                "full_name": t.full_name,
                "department": t.department,
                "attendance_percentage": round(att_pct, 2),
                "present_days": present_days,
                "late_entries": late_days,
                "leaves_taken": leaves_taken_this_month,
                "leave_balance": max(0, leave_balance)
            })

        return report_data

    def generate_excel(self, data: list, title: str) -> BytesIO:
        """
        Generates an Excel spreadsheet from list of dicts.
        """
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Report", index=False)
            
            # Format workbook auto-adjust columns
            workbook = writer.book
            worksheet = writer.sheets["Report"]
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 10)
                
        output.seek(0)
        return output

    def generate_pdf(self, data: list, title: str, subtitle: str) -> BytesIO:
        """
        Generates a professionally formatted PDF report.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1A365D"), # Deep Navy Blue
            spaceAfter=6
        )
        
        subtitle_style = ParagraphStyle(
            name="ReportSubTitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#4A5568"), # Slate Grey
            spaceAfter=20
        )

        elements = []
        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(subtitle, subtitle_style))
        elements.append(Spacer(1, 10))

        if not data:
            elements.append(Paragraph("No records found for the selected period.", styles["Normal"]))
        else:
            # Build Table
            headers = list(data[0].keys())
            # Format header names: replace underscores with spaces and capitalize
            formatted_headers = [h.replace("_", " ").title() for h in headers]
            
            table_rows = [formatted_headers]
            for item in data:
                row = [str(item[h]) for h in headers]
                table_rows.append(row)

            # Auto-size columns proportionally
            col_widths = [80] * len(headers)
            if "full_name" in headers:
                idx = headers.index("full_name")
                col_widths[idx] = 130 # give name column more space
            
            t = Table(table_rows, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#EDF2F7")]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
            ]))
            elements.append(t)

        doc.build(elements)
        buffer.seek(0)
        return buffer

report_service = ReportService()
