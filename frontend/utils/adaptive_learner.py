"""
Adaptive Face Appearance Learner for TIPS-G ALWAR Attendance System.
Tracks successful biometric attendances and incrementally updates the student's
stored face embedding vector after every 3 verified attendances using
Exponential Moving Average (EMA) momentum blending.
Ensures seamless adaptation to hairstyle, glasses, lighting, facial hair, and gradual aging.
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
from loguru import logger

def _get_state_file_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent.parent
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "adaptive_face_state.json"


def _load_adaptive_state() -> dict:
    file_path = _get_state_file_path()
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.debug(f"Could not read adaptive state file: {e}")
        return {}


def _save_adaptive_state(state: dict):
    file_path = _get_state_file_path()
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.debug(f"Could not save adaptive state file: {e}")


def record_successful_attendance_and_adapt(
    student_id: int, 
    stored_embedding: List[float], 
    candidate_embedding: List[float],
    confidence: float,
    learning_rate: float = 0.15
) -> Tuple[bool, Optional[List[float]], int]:
    """
    Records a high-confidence attendance scan for the student.
    When 3 successful attendances are reached:
    1. Computes the normalized centroid of recent scans.
    2. Blends with stored embedding: E_new = normalize((1 - alpha) * E_stored + alpha * E_avg).
    3. Persists the updated embedding to the database.
    4. Resets the counter.

    Returns:
        (did_adapt: bool, updated_embedding: Optional[list], current_count: int)
    """
    if not student_id or not candidate_embedding or not stored_embedding:
        return False, None, 0

    sid_str = str(student_id)
    state = _load_adaptive_state()
    student_data = state.get(sid_str, {
        "count": 0,
        "recent_embeddings": []
    })

    # Append current candidate embedding
    embeddings_list = student_data.get("recent_embeddings", [])
    embeddings_list.append(candidate_embedding)
    # Keep at most last 3
    if len(embeddings_list) > 3:
        embeddings_list = embeddings_list[-3:]

    count = student_data.get("count", 0) + 1
    student_data["count"] = count
    student_data["recent_embeddings"] = embeddings_list
    student_data["last_confidence"] = confidence

    did_adapt = False
    updated_embedding = None

    if count >= 3:
        # Trigger 3-attendance Consolidation & Model Update
        try:
            # 1. Compute Centroid of recent 3 scans
            all_recent = [np.array(e, dtype=np.float32) for e in embeddings_list if e]
            if all_recent:
                # Normalize each
                norm_recent = []
                for v in all_recent:
                    v_n = np.linalg.norm(v)
                    if v_n > 0:
                        norm_recent.append(v / v_n)
                    else:
                        norm_recent.append(v)
                
                recent_avg = np.mean(norm_recent, axis=0)
                avg_n = np.linalg.norm(recent_avg)
                if avg_n > 0:
                    recent_avg = recent_avg / avg_n

                # 2. Blend with stored embedding using momentum alpha
                stored_np = np.array(stored_embedding, dtype=np.float32)
                st_n = np.linalg.norm(stored_np)
                if st_n > 0:
                    stored_np = stored_np / st_n

                alpha = max(0.05, min(0.30, float(learning_rate)))
                blended = (1.0 - alpha) * stored_np + alpha * recent_avg
                b_n = np.linalg.norm(blended)
                if b_n > 0:
                    blended = blended / b_n

                updated_embedding = blended.tolist()

                # 3. Persist directly to DB table FaceEmbedding
                from src.database.connection import SessionLocal
                from src.database.models import FaceEmbedding, Student
                db = SessionLocal()
                emb_record = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id).first()
                if emb_record:
                    emb_record.embedding = updated_embedding
                    db.commit()
                    logger.info(f"✨ [ADAPTIVE AI] Face embedding updated in DB after 3 attendances for student ID {student_id}.")
                else:
                    new_emb = FaceEmbedding(student_id=student_id, embedding=updated_embedding)
                    db.add(new_emb)
                    db.commit()
                    logger.info(f"✨ [ADAPTIVE AI] Created new FaceEmbedding in DB after 3 attendances for student ID {student_id}.")
                db.close()

                did_adapt = True

        except Exception as e:
            logger.error(f"Error updating adaptive embedding in DB: {e}")

        # Reset count and buffer after updating
        student_data["count"] = 0
        student_data["recent_embeddings"] = []

    state[sid_str] = student_data
    _save_adaptive_state(state)

    current_progress = student_data["count"]
    return did_adapt, updated_embedding, current_progress
