"""
TIPS-G ALWAR Student Attendance System
Batch Face Embedding Re-calculation Script (5-Point Landmark ArcFace)

Re-extracts normalized 512-D ArcFace embeddings for active students using
the updated 5-point similarity transformation alignment.
Zero-loss: Does NOT delete or drop any tables or student history.
"""

import sys
import math
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import SessionLocal
from src.database.models import Student, FaceEmbedding
from frontend.onnx_face_service import onnx_face_service

def recalculate_embeddings():
    db = SessionLocal()
    print("=" * 70)
    print("  TIPS-G ALWAR: 5-Point ArcFace Embedding Batch Re-calculator")
    print("=" * 70)

    try:
        # 1. Load ONNX & MediaPipe models
        print("[1/3] Loading AI Models...")
        loaded = onnx_face_service.load_models()
        if not loaded:
            print("❌ Failed to load AI models. Please ensure models exist in models/ directory.")
            return

        # 2. Query active students
        students = db.query(Student).filter(Student.is_active == True).all()
        print(f"[2/3] Found {len(students)} active student(s). Processing...")

        updated_count = 0
        skipped_count = 0

        for student in students:
            # Check if student has a valid photo path
            photo_file = None
            if student.photo_path and Path(student.photo_path).exists():
                photo_file = Path(student.photo_path)
            else:
                # Check candidate storage paths
                candidates = [
                    PROJECT_ROOT / "storage" / "students" / f"{student.registration_number}.jpg",
                    PROJECT_ROOT / "storage" / "students" / f"{student.registration_number}.png",
                    PROJECT_ROOT / "storage" / "registration_captures" / f"{student.registration_number}.jpg",
                ]
                for cand in candidates:
                    if cand.exists():
                        photo_file = cand
                        break

            if not photo_file:
                print(f"  [-] Student {student.full_name} ({student.registration_number}): No photo file found on disk. Keeping existing vector.")
                skipped_count += 1
                continue

            # Extract new 5-point aligned embedding
            try:
                emb = onnx_face_service.extract_embedding(str(photo_file))
                if emb and len(emb) == 512:
                    # Update database embedding record
                    emb_record = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).first()
                    if emb_record:
                        emb_record.embedding = emb
                    else:
                        db.add(FaceEmbedding(student_id=student.id, embedding=emb))
                    
                    student.photo_path = str(photo_file)
                    db.commit()
                    updated_count += 1
                    print(f"  [✓] Updated {student.full_name} ({student.registration_number}) with 5-point aligned embedding.")
                else:
                    print(f"  [!] Failed to extract valid 512-D embedding for {student.full_name}.")
                    skipped_count += 1
            except Exception as exc:
                print(f"  [!] Error processing {student.full_name}: {exc}")
                skipped_count += 1

        print("-" * 70)
        print(f"[3/3] Done! Updated: {updated_count}, Skipped/Unchanged: {skipped_count}")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    recalculate_embeddings()
