import os
from datetime import date, datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger

from src.database.connection import get_db
from src.backend.dependencies import require_teacher, require_auth, require_admin
from src.backend.services.report_service import report_service
from src.database.models import MonthlyReportArchive
from src.config_loader import settings

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

@router.get("/archives")
def get_monthly_report_archives(
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """Lists monthly report files generated automatically by the server."""
    # Order so archives with actual recorded rows come first
    records = db.query(MonthlyReportArchive).order_by(
        MonthlyReportArchive.year.desc(),
        MonthlyReportArchive.month.desc(),
        MonthlyReportArchive.attendance_rows_archived.desc(),
        MonthlyReportArchive.id.desc()
    ).all()

    seen = set()
    result = []
    for report in records:
        key = (report.year, report.month, report.report_type)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "id": report.id,
            "year": report.year,
            "month": report.month,
            "report_type": report.report_type,
            "attendance_rows_archived": report.attendance_rows_archived,
            "created_at": report.created_at.isoformat(),
        })
    return result

@router.get("/archives/{archive_id}/download")
def download_monthly_report_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """Downloads a saved automatic monthly report."""
    report = db.query(MonthlyReportArchive).filter(MonthlyReportArchive.id == archive_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Monthly report archive not found")

    resolved_path = None
    # 1. Check direct path from DB
    if report.file_path and os.path.isfile(report.file_path) and os.path.getsize(report.file_path) > 1000:
        resolved_path = report.file_path
    else:
        # 2. Check candidate local directories for the report file
        candidate_paths = [
            Path(settings.system.get("storage_dir", "storage")) / "reports" / f"student_monthly_{report.year}_{report.month:02d}.xlsx",
            Path("storage/reports") / f"student_monthly_{report.year}_{report.month:02d}.xlsx",
            Path("backend/storage/reports") / f"student_monthly_{report.year}_{report.month:02d}.xlsx",
        ]
        for cp in candidate_paths:
            if cp.exists() and cp.stat().st_size > 1000:
                resolved_path = str(cp.resolve())
                report.file_path = resolved_path
                db.commit()
                break

    # 3. If still missing, dynamically generate from database if records exist
    if not resolved_path:
        report_data = report_service.get_student_monthly_data(db, report.year, report.month)
        if report_data:
            excel_bytes = report_service.generate_excel(report_data, "Student Monthly Attendance Report").getvalue()
            dest_dir = Path(settings.system.get("storage_dir", "storage")) / "reports"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / f"student_monthly_{report.year}_{report.month:02d}.xlsx"
            with open(dest_file, "wb") as f:
                f.write(excel_bytes)
            resolved_path = str(dest_file.resolve())
            report.file_path = resolved_path
            db.commit()

    if not resolved_path or not os.path.isfile(resolved_path):
        raise HTTPException(status_code=404, detail="The saved report file is no longer available on this server")

    return FileResponse(
        resolved_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"student_monthly_{report.year}_{report.month:02d}.xlsx"
    )

@router.delete("/archives/{archive_id}", status_code=204)
def delete_monthly_report_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Permanently removes one saved report file and its archive entry."""
    report = db.query(MonthlyReportArchive).filter(MonthlyReportArchive.id == archive_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Monthly report archive not found")

    report_dir = (Path(settings.system["storage_dir"]) / "reports").resolve()
    report_path = Path(report.file_path).resolve()
    if report_dir not in report_path.parents or report_path.suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="Invalid monthly report archive path")
    if report_path.exists():
        report_path.unlink()
    db.delete(report)
    db.commit()

@router.get("/summary")
def get_daily_summary(
    target_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Returns daily student attendance summary metrics for the dashboard cards."""
    try:
        query_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    return report_service.get_daily_summary(db, query_date)

@router.get("/monthly/student")
def get_student_monthly_report(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    export_format: str = Query("json", pattern="^(json|pdf|excel)$"),
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """Generates monthly student reports in JSON, Excel, or PDF format."""
    data = report_service.get_student_monthly_data(db, year, month)
    
    title = f"Student Monthly Attendance Report"
    subtitle = f"Period: {month:02d}/{year} | Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    if export_format == "json":
        return data
        
    elif export_format == "excel":
        excel_file = report_service.generate_excel(data, title)
        headers = {
            'Content-Disposition': f'attachment; filename="student_monthly_{year}_{month}.xlsx"'
        }
        return StreamingResponse(
            excel_file, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            headers=headers
        )
        
    elif export_format == "pdf":
        pdf_file = report_service.generate_pdf(data, title, subtitle)
        headers = {
            'Content-Disposition': f'attachment; filename="student_monthly_{year}_{month}.pdf"'
        }
        return StreamingResponse(
            pdf_file, 
            media_type="application/pdf", 
            headers=headers
        )

@router.get("/monthly/staff")
def get_staff_monthly_report(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    export_format: str = Query("json", pattern="^(json|pdf|excel)$"),
    db: Session = Depends(get_db),
    current_user = Depends(require_teacher)
):
    """Generates monthly staff/teacher reports in JSON, Excel, or PDF format."""
    data = report_service.get_staff_monthly_data(db, year, month)
    
    title = f"Staff Monthly Attendance Report"
    subtitle = f"Period: {month:02d}/{year} | Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    if export_format == "json":
        return data
        
    elif export_format == "excel":
        excel_file = report_service.generate_excel(data, title)
        headers = {
            'Content-Disposition': f'attachment; filename="staff_monthly_{year}_{month}.xlsx"'
        }
        return StreamingResponse(
            excel_file, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            headers=headers
        )
        
    elif export_format == "pdf":
        pdf_file = report_service.generate_pdf(data, title, subtitle)
        headers = {
            'Content-Disposition': f'attachment; filename="staff_monthly_{year}_{month}.pdf"'
        }
        return StreamingResponse(
            pdf_file, 
            media_type="application/pdf", 
            headers=headers
        )
