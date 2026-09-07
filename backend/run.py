"""
TIPS-G ALWAR Student Attendance System — Backend Entry Point
Launches the FastAPI backend server and provides admin utilities.

Usage:
    python run.py                  # Start backend server (default)
    python run.py --seed           # Seed initial admin/teacher accounts
    python run.py --cleanup        # Remove orphaned face embeddings
"""
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import sys
import argparse
from loguru import logger


def main():
    parser = argparse.ArgumentParser(description="TIPS-G ALWAR Backend Server")
    parser.add_argument("--seed", action="store_true", help="Seeds initial demo data")
    parser.add_argument("--cleanup", action="store_true", help="Remove orphaned face embeddings (deleted students)")
    parser.add_argument("--download-models", action="store_true", help="Download required AI face ONNX and MediaPipe models")

    args = parser.parse_args()

    # Model download operation if requested
    if args.download_models:
        logger.info("Verifying and downloading AI face models...")
        from models.download_models import ensure_models_exist
        success = ensure_models_exist(verbose=True)
        if not success:
            logger.error("Failed to download one or more models.")
            sys.exit(1)
        logger.info("✓ All models verified successfully.")
        return

    # Cleanup operation if requested
    if args.cleanup:
        logger.info("Cleaning up orphaned face embeddings...")
        from src.database.connection import init_db, SessionLocal
        from src.database.models import FaceEmbedding, Student
        init_db()
        db = SessionLocal()
        
        # Find embeddings whose students are soft-deleted (is_active=False)
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

    # Default: Launch FastAPI backend server
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    is_prod = os.getenv("ENVIRONMENT") == "production"
    
    import uvicorn
    logger.info(f"Launching FastAPI Backend Server on {host}:{port} (workers: {4 if is_prod else 1})...")
    uvicorn.run(
        "src.backend.main:app",
        host=host,
        port=port,
        reload=not is_prod,
        workers=4 if is_prod else 1
    )

if __name__ == "__main__":
    main()
