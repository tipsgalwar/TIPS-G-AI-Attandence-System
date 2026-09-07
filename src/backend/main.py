import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import threading
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from src.config_loader import settings
from src.database.connection import init_db, SessionLocal
from src.backend.routes import auth, students, attendance, leaves, holidays, reports, noticeboard, notifications
from src.backend.routes.auth import seed_initial_accounts
from src.backend.services.report_service import report_service

monthly_archive_stop = threading.Event()

def monthly_archive_worker():
    """Checks hourly so a completed month is archived without manual action."""
    while not monthly_archive_stop.is_set():
        db = SessionLocal()
        try:
            created = report_service.archive_completed_attendance_months(db)
            if created:
                logger.info(f"Created {created} automatic monthly attendance archive(s).")
        except Exception as e:
            db.rollback()
            logger.error(f"Automatic monthly report archive failed: {e}")
        finally:
            db.close()
        monthly_archive_stop.wait(3600)

app = FastAPI(
    title="Student Guardian AI API",
    description="Backend API for Face Recognition Attendance, Leave, and Holiday Management System.",
    version="1.0.0"
)

# Set up CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to desktop app client origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(leaves.router, prefix="/api")
app.include_router(holidays.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(noticeboard.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")

@app.on_event("startup")
def on_startup():
    logger.info("Starting Student Guardian AI Backend...")
    
    # Initialize Database tables
    try:
        init_db()
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        
    # Auto-seed initial admin and teacher accounts for demo out-of-the-box support
    db = SessionLocal()
    try:
        res = seed_initial_accounts(db)
        logger.info(f"Database seeder: {res['message']}")
    except Exception as e:
        logger.error(f"Failed to run database seed: {e}")
    finally:
        db.close()

    # Run once at startup (covers downtime), then check once per hour.
    threading.Thread(target=monthly_archive_worker, name="monthly-report-archive", daemon=True).start()

@app.on_event("shutdown")
def on_shutdown():
    monthly_archive_stop.set()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": "Student Guardian AI",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    host = settings.system.get("host", "127.0.0.1")
    port = settings.system.get("port", 8000)
    uvicorn.run("src.backend.main:app", host=host, port=port, reload=True)
