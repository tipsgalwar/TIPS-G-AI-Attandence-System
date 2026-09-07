# Gutted face_service.py to remove heavy AI imports (TensorFlow, DeepFace, MediaPipe) on the backend.
# All face recognition and liveness checking has been moved to the client/frontend.

from loguru import logger

class FaceService:
    def __init__(self):
        logger.info("Stub FaceService initialized (AI processing moved to client).")

    def generate_mock_embedding(self) -> list:
        return [0.0] * 512

    def extract_embedding(self, image_path: str) -> list:
        raise NotImplementedError("Embedding extraction moved to client-side.")

    def detect_and_verify(self, frame_bytes: bytes, known_students: list) -> dict:
        raise NotImplementedError("Face verification moved to client-side.")

    def check_liveness(self, img) -> dict:
        raise NotImplementedError("Liveness check moved to client-side.")

face_service = FaceService()
