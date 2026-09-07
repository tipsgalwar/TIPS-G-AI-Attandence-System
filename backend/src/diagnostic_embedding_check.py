"""
Database Diagnostic Script - Check Face Embedding Status
Run: python -m src.diagnostic_embedding_check
"""

import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import SessionLocal
from src.database.models import Student, FaceEmbedding
import json

def check_database():
    """Diagnose face embedding status in database"""
    db = SessionLocal()
    
    print("\n" + "="*80)
    print("FACE EMBEDDING DATABASE DIAGNOSTIC")
    print("="*80)
    
    # Check students
    print("\n1. CHECKING ACTIVE STUDENTS")
    print("-" * 80)
    students = db.query(Student).filter(Student.is_active == True).all()
    print(f"Total active students: {len(students)}")
    for s in students:
        print(f"  ✓ ID={s.id}, Name='{s.full_name}', RegNo='{s.registration_number}', Active={s.is_active}")
    
    # Check face embeddings
    print("\n2. CHECKING FACE EMBEDDINGS IN DATABASE")
    print("-" * 80)
    embeddings = db.query(FaceEmbedding).all()
    print(f"Total face embeddings: {len(embeddings)}")
    
    if len(embeddings) == 0:
        print("  ❌ NO EMBEDDINGS FOUND IN DATABASE!")
        print("  This is the ROOT CAUSE of the face detection failure.")
    
    for emb in embeddings:
        student = db.query(Student).filter(Student.id == emb.student_id).first()
        student_name = student.full_name if student else f"UNKNOWN (ID={emb.student_id})"
        emb_type = type(emb.embedding).__name__
        
        if isinstance(emb.embedding, str):
            emb_len = len(emb.embedding)
            print(f"  ⚠️  ID={emb.id}, Student='{student_name}'")
            print(f"      Type: STRING (should be list!), Length: {emb_len}")
            print(f"      Preview: {emb.embedding[:50]}...")
        elif isinstance(emb.embedding, list):
            emb_len = len(emb.embedding)
            first_3 = emb.embedding[:3] if emb_len >= 3 else emb.embedding
            print(f"  ✓ ID={emb.id}, Student='{student_name}'")
            print(f"      Type: LIST (correct!), Length: {emb_len} (expected 512)")
            print(f"      First 3 values: {first_3}")
            if emb_len != 512:
                print(f"      ❌ INVALID LENGTH! Expected 512, got {emb_len}")
        else:
            print(f"  ❌ ID={emb.id}, Student='{student_name}'")
            print(f"      Type: {emb_type} (unexpected!), Value: {emb.embedding}")
    
    # Check file system embeddings
    print("\n3. CHECKING FILE SYSTEM EMBEDDINGS")
    print("-" * 80)
    from src.config_loader import settings
    students_dir = Path(settings.system.get("students_dir", "storage/students"))
    
    if students_dir.exists():
        student_dirs = [d for d in students_dir.iterdir() if d.is_dir()]
        print(f"Total student directories: {len(student_dirs)}")
        
        for student_path in sorted(student_dirs):
            emb_file = student_path / "embeddings.json"
            meta_file = student_path / "metadata.json"
            
            print(f"\n  Student directory: {student_path.name}")
            
            if meta_file.exists():
                with open(meta_file) as f:
                    meta = json.load(f)
                print(f"    Metadata: {meta}")
            
            if emb_file.exists():
                try:
                    with open(emb_file) as f:
                        emb_data = json.load(f)
                    if isinstance(emb_data, list):
                        print(f"    ✓ embeddings.json: Length={len(emb_data)}, Type=list")
                        print(f"      First 3 values: {emb_data[:3]}")
                    else:
                        print(f"    ❌ embeddings.json: Type={type(emb_data).__name__} (expected list)")
                except Exception as e:
                    print(f"    ❌ embeddings.json: ERROR reading file - {e}")
            else:
                print(f"    ❌ embeddings.json: FILE NOT FOUND")
    else:
        print(f"  ❌ Students directory not found: {students_dir}")
    
    # Summary and diagnosis
    print("\n" + "="*80)
    print("DIAGNOSIS SUMMARY")
    print("="*80)
    
    active_students = db.query(Student).filter(Student.is_active == True).count()
    total_embeddings = db.query(FaceEmbedding).count()
    
    if active_students > 0 and total_embeddings == 0:
        print("❌ CRITICAL: Students exist but NO embeddings in database!")
        print("   ACTION: Need to rebuild embeddings from stored photos")
    elif active_students == 0:
        print("⚠️  No active students registered yet")
    elif active_students != total_embeddings:
        print(f"⚠️  WARNING: {active_students} active students but {total_embeddings} embeddings")
    else:
        print(f"✓ Database looks good: {active_students} students with {total_embeddings} embeddings")
    
    db.close()

if __name__ == "__main__":
    check_database()
