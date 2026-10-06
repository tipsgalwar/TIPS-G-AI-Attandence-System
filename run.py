"""
TIPS-G ALWAR Student Attendance System — Backend Entry Point
Launches the FastAPI backend server using uvicorn.

Usage:
    python run.py                  # Start backend server with uvicorn
    uvicorn src.backend.main:app --host 0.0.0.0 --port 8003 --reload
"""
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import sys
import argparse
from loguru import logger


def main():
    parser = argparse.ArgumentParser(description="TIPS-G ALWAR Backend Server")
    parser.add_argument("--host", default=None, help="Host to bind (default: from env or 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: 8003)")
    parser.add_argument("--reload", action="store_true", default=None, help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes")
    parser.add_argument("--seed", action="store_true", help="Seeds initial demo data")
    parser.add_argument("--cleanup", action="store_true", help="Remove orphaned face embeddings (deleted students)")

    args = parser.parse_args()

    # Cleanup operation if requested
    if args.cleanup:
        logger.info("Cleaning up orphaned face embeddings...")
        from src.database.connection import init_db, SessionLocal
        from src.database.models import FaceEmbedding, Student
        init_db()
        db = SessionLocal()
        orphaned = db.query(FaceEmbedding).join(Student).filter(Student.is_active == False).all()
        orphaned_count = len(orphaned)
        if orphaned_count > 0:
            for emb in orphaned:
                student_name = emb.student.full_name if emb.student else "Unknown"
                logger.info(f"  Removing embedding for soft-deleted student: {student_name} (ID: {emb.student_id})")
            db.query(FaceEmbedding).join(Student).filter(Student.is_active == False).delete()
            db.commit()
            logger.info(f"✓ Cleanup complete: Removed {orphaned_count} orphaned embedding(s)")
        else:
            logger.info("✓ No orphaned embeddings found")
        db.close()
        return

    # Seed operation if requested
    if args.seed:
        logger.info("Seeding database...")
        from src.database.connection import init_db, SessionLocal
        from src.backend.routes.auth import seed_initial_accounts
        init_db()
        db = SessionLocal()
        res = seed_initial_accounts(db)
        db.close()
        logger.info(f"Seed results: {res['message']}")
        return

    # Launch FastAPI backend server directly via uvicorn
    host = args.host or os.getenv("BACKEND_HOST", "0.0.0.0")
    port = args.port or int(os.getenv("BACKEND_PORT", "8003"))
    is_prod = os.getenv("ENVIRONMENT") == "production"
    reload_flag = args.reload if args.reload is not None else (not is_prod)
    workers_count = args.workers or (2 if is_prod else 1)

    import uvicorn
    logger.info(f"🚀 Starting Uvicorn backend server on http://{host}:{port} (workers={workers_count}, reload={reload_flag})...")
    uvicorn.run(
        "src.backend.main:app",
        host=host,
        port=port,
        reload=reload_flag,
        workers=workers_count,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )


if __name__ == "__main__":
    main()
