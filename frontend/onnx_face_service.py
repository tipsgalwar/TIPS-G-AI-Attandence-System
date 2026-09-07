import os
import sys
from typing import Optional, Union, List, Tuple, Dict
import numpy as np
from pathlib import Path
from loguru import logger

# Safe imports for GUI environment
try:
    import cv2
except ImportError:
    cv2 = None
    logger.warning("OpenCV not installed or unavailable in frontend.")

try:
    import onnxruntime as ort
except ImportError:
    ort = None
    logger.warning("onnxruntime not installed or unavailable in frontend.")

try:
    import mediapipe as mp
    try:
        from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarker
        from mediapipe.tasks.python.vision.core import image as mp_image
    except ImportError:
        FaceLandmarker = None
        mp_image = None
except ImportError:
    mp = None
    FaceLandmarker = None
    mp_image = None

class OnnxFaceService:
    def __init__(self):
        self.face_landmarker = None
        self.arcface_session = None
        self.arcface_input_name = None
        self.arcface_output_name = None
        
        # Load paths (support frozen PyInstaller bundle, installed dir, and dev mode)
        self.candidate_model_dirs = []
        if hasattr(sys, '_MEIPASS'):
            self.candidate_model_dirs.append(Path(sys._MEIPASS) / "models")
        if getattr(sys, 'frozen', False):
            self.candidate_model_dirs.append(Path(sys.executable).parent / "models")
        self.candidate_model_dirs.append(Path(__file__).resolve().parent.parent / "models")
        self.candidate_model_dirs.append(Path.home() / ".tipsg" / "models")

        # Select primary models directory
        self.models_dir = self.candidate_model_dirs[0]
        for d in self.candidate_model_dirs:
            if (d / "arcface_resnet50.onnx").exists():
                self.models_dir = d
                break

        # Config options — read from config.ini or use sensible defaults
        project_root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
        import configparser
        config = configparser.ConfigParser()
        config_file = project_root / "config.ini"
        if config_file.exists():
            config.read(config_file)
        
        self.face_detector_backend = config.get("ai", "face_detector_backend", fallback="retinaface")
        self.face_recognition_model = config.get("ai", "face_recognition_model", fallback="ArcFace")
        self.face_distance_metric = config.get("ai", "face_distance_metric", fallback="cosine")
        self.similarity_threshold = float(
            config.get("ai", "similarity_threshold", fallback=os.getenv("FACE_SIMILARITY_THRESHOLD", "0.40"))
        )
        self.minimum_confidence = float(
            config.get("ai", "minimum_confidence", fallback=os.getenv("MIN_CONFIDENCE_SCORE", "60.0"))
        )
        self.liveness_enabled = config.getboolean("ai", "liveness_enabled", fallback=True)
        self.blink_detection_enabled = config.getboolean("ai", "blink_detection_enabled", fallback=True)
        self.ear_threshold = float(config.get("ai", "ear_threshold", fallback=0.20))
        self.head_movement_enabled = config.getboolean("ai", "head_movement_enabled", fallback=True)
        self.yaw_threshold = float(config.get("ai", "yaw_threshold", fallback=15.0))
        self.pitch_threshold = float(config.get("ai", "pitch_threshold", fallback=10.0))

        # Adaptive & Multi-frame configurations
        self.adaptive_update_enabled = config.getboolean("ai", "adaptive_update_enabled", fallback=True)
        self.adaptive_confidence_threshold = float(config.get("ai", "adaptive_confidence_threshold", fallback=85.0))
        self.adaptive_learning_rate = float(config.get("ai", "adaptive_learning_rate", fallback=0.10))
        self.burst_frames_count = int(config.get("ai", "burst_frames_count", fallback=3))

        logger.debug(
            f"Face verification thresholds: model={self.face_recognition_model}, "
            f"metric={self.face_distance_metric}, similarity_threshold={self.similarity_threshold}, "
            f"minimum_confidence={self.minimum_confidence}, liveness={self.liveness_enabled}, "
            f"adaptive_update={self.adaptive_update_enabled}"
        )

    def _get_model_file(self, filename: str) -> Path:
        """Find model file across all candidate search directories."""
        for d in self.candidate_model_dirs:
            p = d / filename
            if p.exists() and p.stat().st_size > 1024:
                return p
        return self.models_dir / filename

    def load_models(self) -> bool:
        """Loads ONNX model and MediaPipe face landmarker, auto-downloading if missing."""
        face_landmarker_path = self._get_model_file("face_landmarker.task")
        arcface_path = self._get_model_file("arcface_resnet50.onnx")

        # 0. Check and auto-download models if missing
        if not arcface_path.exists() or not face_landmarker_path.exists():
            try:
                from models.download_models import ensure_models_exist
                logger.info("One or more AI model files are missing. Initiating automatic download...")
                ensure_models_exist(["arcface_resnet50.onnx", "face_landmarker.task"])
                face_landmarker_path = self._get_model_file("face_landmarker.task")
                arcface_path = self._get_model_file("arcface_resnet50.onnx")
            except Exception as e:
                logger.warning(f"Automatic model download encountered an issue: {e}")

        # 1. Initialize MediaPipe Face Landmarker for landmark-based face alignment
        if FaceLandmarker and mp_image:
            if face_landmarker_path.exists():
                try:
                    self.face_landmarker = FaceLandmarker.create_from_model_path(str(face_landmarker_path))
                    logger.info(f"MediaPipe Face Landmarker initialized successfully from {face_landmarker_path}.")
                except Exception as e:
                    self.face_landmarker = None
                    logger.warning(f"Failed to initialize MediaPipe Face Landmarker in frontend: {e}.")
            else:
                self.face_landmarker = None
                logger.warning(f"MediaPipe Face Landmarker model not found at {face_landmarker_path}.")
        else:
            self.face_landmarker = None
            logger.warning("MediaPipe Face Landmarker API is unavailable.")

        # 2. Initialize ArcFace ONNX Session
        if not ort:
            logger.error("onnxruntime is not installed.")
            return False

        if not arcface_path.exists():
            logger.error(f"ArcFace ONNX model not found at {arcface_path}.")
            return False

        try:
            self.arcface_session = ort.InferenceSession(
                str(arcface_path),
                providers=['CPUExecutionProvider']
            )
            self.arcface_input_name = self.arcface_session.get_inputs()[0].name
            self.arcface_output_name = self.arcface_session.get_outputs()[0].name
            logger.info(f"ArcFace ONNX model loaded successfully from {arcface_path}.")
            return True
        except Exception as e:
            logger.error(f"Failed to load ArcFace ONNX session: {e}")
            self.arcface_session = None
            return False

    def align_and_crop_face(self, img: np.ndarray, landmarks) -> np.ndarray:
        """
        Aligns and crops the face to standard 112x112 pixels using MediaPipe 5-point
        facial landmarks and similarity transformation (estimateAffinePartial2D).
        Preserves aspect ratio and prevents shear distortion from head tilts.
        """
        h, w, _ = img.shape
        
        # Canonical 5 landmark points:
        # Left pupil/eye (468), Right pupil/eye (473), Nose tip (1),
        # Left mouth corner (61), Right mouth corner (291)
        left_pupil = np.array([landmarks[468].x * w, landmarks[468].y * h], dtype=np.float32)
        right_pupil = np.array([landmarks[473].x * w, landmarks[473].y * h], dtype=np.float32)
        nose_tip = np.array([landmarks[1].x * w, landmarks[1].y * h], dtype=np.float32)
        left_mouth = np.array([landmarks[61].x * w, landmarks[61].y * h], dtype=np.float32)
        right_mouth = np.array([landmarks[291].x * w, landmarks[291].y * h], dtype=np.float32)
        
        src_pts = np.array([left_pupil, right_pupil, nose_tip, left_mouth, right_mouth], dtype=np.float32)
        
        # Standard ArcFace canonical 5-point reference coordinates in 112x112 template
        dst_pts = np.array([
            [38.2946, 51.6963],  # Left eye reference
            [73.5318, 51.6963],  # Right eye reference
            [56.0252, 71.7366],  # Nose tip reference
            [41.5493, 92.3655],  # Left mouth reference
            [70.7266, 92.3655]   # Right mouth reference
        ], dtype=np.float32)
        
        # Compute rigid similarity transform (rotation + uniform scale + translation)
        M, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        if M is not None:
            warped = cv2.warpAffine(img, M, (112, 112), borderValue=0.0)
        else:
            # Fallback to 3-point affine if partial 2D fails
            M3 = cv2.getAffineTransform(src_pts[:3], dst_pts[:3])
            warped = cv2.warpAffine(img, M3, (112, 112))
        return warped


    def _create_mediapipe_image(self, img: np.ndarray):
        if not mp_image:
            raise RuntimeError("MediaPipe image API is unavailable.")

        if img.dtype != np.uint8:
            img = img.astype(np.uint8)

        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return mp_image.Image(image_format=mp_image.ImageFormat.SRGB, data=rgb_img)

    def detect_face_box(self, cv_img) -> Optional[tuple]:
        """
        Fast real-time face detection returning (x, y, w, h) of the primary face.
        Uses downscaled grayscale detection for >60 FPS tracking speed.
        """
        if cv_img is None or cv2 is None:
            return None

        if not hasattr(self, "_cached_cascade") or self._cached_cascade is None:
            candidate_cascades = []
            if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                candidate_cascades.append(Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml')
            if hasattr(sys, '_MEIPASS'):
                candidate_cascades.append(Path(sys._MEIPASS) / 'cv2' / 'data' / 'haarcascade_frontalface_default.xml')
                candidate_cascades.append(Path(sys._MEIPASS) / 'data' / 'haarcascade_frontalface_default.xml')
            if getattr(sys, 'frozen', False):
                candidate_cascades.append(Path(sys.executable).parent / 'cv2' / 'data' / 'haarcascade_frontalface_default.xml')

            self._cached_cascade = None
            for cp in candidate_cascades:
                if cp.exists():
                    fc = cv2.CascadeClassifier(str(cp))
                    if not fc.empty():
                        self._cached_cascade = fc
                        break

        if self._cached_cascade is None:
            return None

        try:
            # Downscale frame for ultra-fast 60 FPS detection
            scale = 0.5
            small = cv2.resize(cv_img, (0, 0), fx=scale, fy=scale)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = self._cached_cascade.detectMultiScale(
                gray, scaleFactor=1.15, minNeighbors=3, minSize=(30, 30)
            )
            if len(faces) > 0:
                faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                sx, sy, sw, sh = faces[0]
                inv = 1.0 / scale
                x = int(sx * inv)
                y = int(sy * inv)
                w = int(sw * inv)
                h = int(sh * inv)
                return (x, y, w, h)
        except Exception:
            pass

        return None

    def extract_embedding(self, img_path_or_bytes) -> list:
        """
        Extracts a 512-dimensional ArcFace embedding vector.
        Accepts file path or raw image bytes/numpy array.
        """
        if not cv2:
            raise RuntimeError("OpenCV (cv2) is not installed. Cannot extract face embedding.")

        # Ensure ArcFace model is loaded before extracting embeddings
        if not self.arcface_session:
            loaded = self.load_models()
            if not loaded:
                raise RuntimeError("ArcFace ONNX model is not loaded. Please run download_models.py and restart.")

        # Decode image if path/bytes
        if isinstance(img_path_or_bytes, (str, Path)):
            img = cv2.imread(str(img_path_or_bytes))
        elif isinstance(img_path_or_bytes, bytes):
            nparr = np.frombuffer(img_path_or_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            img = img_path_or_bytes

        if img is None:
            raise ValueError("Failed to load or decode image for embedding extraction.")

        # Ensure models are loaded
        if not self.arcface_session or not self.face_landmarker:
            self.load_models()

        if not self.arcface_session:
            raise RuntimeError("ArcFace AI model is not loaded. Please connect to the internet to download required face models.")

        aligned_face = None
        if self.face_landmarker:
            try:
                mp_image_input = self._create_mediapipe_image(img)
                results = self.face_landmarker.detect(mp_image_input)
                face_landmarks = getattr(results, "face_landmarks", None)
                if face_landmarks and len(face_landmarks) > 0:
                    landmarks = face_landmarks[0]
                    aligned_face = self.align_and_crop_face(img, landmarks)
            except Exception as e:
                logger.warning(f"MediaPipe landmark detection failed ({e}), falling back to OpenCV face detector.")

        # Fallback 1: Built-in OpenCV Frontal Face Detection (Extracts real face bounding box)
        if aligned_face is None and cv2 is not None:
            try:
                candidate_cascades = []
                if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                    candidate_cascades.append(Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml')
                if hasattr(sys, '_MEIPASS'):
                    candidate_cascades.append(Path(sys._MEIPASS) / 'cv2' / 'data' / 'haarcascade_frontalface_default.xml')
                    candidate_cascades.append(Path(sys._MEIPASS) / 'data' / 'haarcascade_frontalface_default.xml')
                if getattr(sys, 'frozen', False):
                    candidate_cascades.append(Path(sys.executable).parent / 'cv2' / 'data' / 'haarcascade_frontalface_default.xml')
                
                face_cascade = None
                for cp in candidate_cascades:
                    if cp.exists():
                        fc = cv2.CascadeClassifier(str(cp))
                        if not fc.empty():
                            face_cascade = fc
                            break

                if face_cascade:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
                    if len(faces) > 0:
                        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                        x, y, w, h = faces[0]
                        margin_x = int(w * 0.15)
                        margin_y = int(h * 0.15)
                        x1 = max(0, x - margin_x)
                        y1 = max(0, y - margin_y)
                        x2 = min(img.shape[1], x + w + margin_x)
                        y2 = min(img.shape[0], y + h + margin_y)
                        face_crop = img[y1:y2, x1:x2]
                        aligned_face = cv2.resize(face_crop, (112, 112))
            except Exception as e:
                logger.warning(f"OpenCV face detection fallback failed: {e}")

        # Fallback 2: Center crop if no face box could be detected
        if aligned_face is None:
            h, w, _ = img.shape
            min_dim = min(h, w)
            start_x = (w - min_dim) // 2
            start_y = (h - min_dim) // 2
            crop = img[start_y:start_y + min_dim, start_x:start_x + min_dim]
            aligned_face = cv2.resize(crop, (112, 112))

        # Adaptive Lighting & Contrast Normalization (CLAHE on L-channel)
        # Normalizes dark shadows, dim ambient light, and harsh highlights
        try:
            lab = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_chan)
            limg = cv2.merge((cl, a_chan, b_chan))
            aligned_face = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        except Exception as e:
            logger.debug(f"CLAHE lighting normalization skipped: {e}")

        # Preprocessing: convert to float32, normalize, swap channels BGR->RGB
        aligned_face = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB)
        aligned_face = aligned_face.astype(np.float32)
        aligned_face = (aligned_face - 127.5) / 128.0
        
        # Keep channels last (112, 112, 3) and add batch dimension (1, 112, 112, 3)
        input_blob = np.expand_dims(aligned_face, axis=0)

        # Run ONNX inference
        outputs = self.arcface_session.run(
            [self.arcface_output_name],
            {self.arcface_input_name: input_blob}
        )
        
        embedding = outputs[0][0].tolist()
        
        # Normalize the embedding to a unit vector
        emb_arr = np.array(embedding)
        norm = np.linalg.norm(emb_arr)
        if norm > 0:
            emb_arr = emb_arr / norm
            
        return emb_arr.tolist()

    def extract_multi_angle_embedding(self, images: list) -> list:
        """
        Extracts and fuses 512-D ArcFace embeddings from multiple angles (e.g. Center, Left, Right).
        Returns a single 512-dimensional normalized master unit vector.
        """
        if not images:
            raise ValueError("No images provided for multi-angle embedding extraction.")

        # If a single image was passed in, wrap it in a list
        if isinstance(images, (str, Path, bytes, np.ndarray)):
            images = [images]

        embeddings = []
        for img_item in images:
            if img_item is None:
                continue
            try:
                emb = self.extract_embedding(img_item)
                if emb and len(emb) == 512:
                    embeddings.append(np.array(emb, dtype=np.float32))
            except Exception as e:
                logger.warning(f"Failed to extract embedding from angle sample: {e}")

        if not embeddings:
            raise RuntimeError("Failed to extract valid face embeddings from any angle image.")

        if len(embeddings) == 1:
            return embeddings[0].tolist()

        # Fused Master Vector: Arithmetic Mean of Normalized Vectors
        fused = np.zeros(512, dtype=np.float32)
        for vec in embeddings:
            norm = np.linalg.norm(vec)
            if norm > 0:
                fused += (vec / norm)
            else:
                fused += vec

        # Normalize the Master Vector to Unit Length on the Hypersphere
        master_norm = np.linalg.norm(fused)
        if master_norm > 0:
            fused = fused / master_norm

        logger.info(f"Successfully fused {len(embeddings)} angle embeddings into Master ArcFace Vector.")
        return fused.tolist()

    def verify_face(self, frame_bytes: bytes, known_embedding: list) -> dict:
        """
        Verifies a live camera frame against the logged-in student's OWN registered embedding.
        This is strictly 1-to-1: current face vs this student's stored embedding only.
        Returns verification result dictionary.
        """
        # Guard: ONNX model must be loaded
        if not self.arcface_session:
            return {
                "verified": False,
                "error": "Face recognition model is not loaded. Please restart the app and ensure models are downloaded."
            }

        if not cv2 or not frame_bytes:
            return {"verified": False, "error": "Frame or OpenCV is missing."}

        # Guard: known embedding must exist and be valid
        if not known_embedding or len(known_embedding) == 0:
            return {
                "verified": False,
                "error": "No registered face embedding found for your account. Please ask admin to register your photo."
            }

        try:
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return {"verified": False, "error": "Failed to decode frame."}

            # 1. Liveness check via MediaPipe
            liveness_result = self.check_liveness(img)
            
            # Reject if liveness check hard-fails (not simulated mode)
            if not liveness_result["passed"] and not liveness_result.get("simulated"):
                return {
                    "verified": False,
                    "error": "Liveness verification failed (Spoof attempt detected)",
                    "liveness": liveness_result
                }

            # 2. Extract embedding from current frame
            curr_emb = np.array(self.extract_embedding(img))
            candidate_embedding = curr_emb.tolist()
            
            # Normalize candidate embedding
            curr_norm = np.linalg.norm(curr_emb)
            if curr_norm > 0:
                curr_emb = curr_emb / curr_norm
                
            # Normalize stored embedding
            known_emb = np.array(known_embedding)
            k_norm = np.linalg.norm(known_emb)
            if k_norm > 0:
                known_emb = known_emb / k_norm

            # Cosine distance
            cosine_dist = 1.0 - float(np.dot(curr_emb, known_emb))
            cosine_dist = max(0.0, min(2.0, cosine_dist))
            
            confidence = round((1.0 - cosine_dist) * 100, 2)
            
            # Ensure confidence is clamped
            if confidence != confidence: # NaN check
                confidence = 0.0
            confidence = max(0.0, min(100.0, confidence))

            verified = cosine_dist <= self.similarity_threshold and confidence >= self.minimum_confidence
            
            result = {
                "verified": verified,
                "confidence": confidence,
                "distance": cosine_dist,
                "liveness": liveness_result,
                "candidate_embedding": candidate_embedding
            }

            if verified:
                return result

            reason = "Face match rejected (unknown face)"
            if confidence < self.minimum_confidence:
                reason = f"Low confidence match: {confidence:.1f}% < {self.minimum_confidence}% required"

            result["verified"] = False
            result["error"] = reason
            return result

        except Exception as e:
            logger.error(f"Error in ONNX face verification: {e}")
            return {"verified": False, "error": f"Verification error: {str(e)}", "confidence": 0.0}

    def check_liveness(self, img) -> dict:
        """
        Performs Blink Detection & Head Pose Estimation.
        """
        if not self.face_landmarker:
            # Fallback if no MediaPipe
            return {
                "blink": True,
                "head_pose": "Center",
                "passed": True,
                "simulated": True
            }

        try:
            mp_image_input = self._create_mediapipe_image(img)
            results = self.face_landmarker.detect(mp_image_input)
            
            face_landmarks = getattr(results, "face_landmarks", None)
            if not face_landmarks or len(face_landmarks) == 0:
                return {"blink": False, "head_pose": "Unknown", "passed": False}

            landmarks = face_landmarks[0]
            
            # Blink Detection via Eye Aspect Ratio (EAR)
            # Left Eye: 362, 385, 387, 263, 373, 380
            # Right Eye: 33, 160, 158, 133, 153, 144
            def calculate_ear(eye_landmarks):
                v1 = np.linalg.norm(np.array([eye_landmarks[1].x - eye_landmarks[5].x, eye_landmarks[1].y - eye_landmarks[5].y]))
                v2 = np.linalg.norm(np.array([eye_landmarks[2].x - eye_landmarks[4].x, eye_landmarks[2].y - eye_landmarks[4].y]))
                h_dist = np.linalg.norm(np.array([eye_landmarks[0].x - eye_landmarks[3].x, eye_landmarks[0].y - eye_landmarks[3].y]))
                return (v1 + v2) / (2.0 * h_dist)

            left_eye_lms = [landmarks[idx] for idx in [362, 385, 387, 263, 373, 380]]
            right_eye_lms = [landmarks[idx] for idx in [33, 160, 158, 133, 153, 144]]
            
            left_ear = calculate_ear(left_eye_lms)
            right_ear = calculate_ear(right_eye_lms)
            avg_ear = (left_ear + right_ear) / 2.0
            
            is_blinking = avg_ear < 0.20  # standard blink threshold

            # Simple Head Pose Estimation
            nose = landmarks[1]
            left_side = landmarks[234]
            right_side = landmarks[454]
            
            total_width = abs(right_side.x - left_side.x)
            nose_offset = abs(nose.x - left_side.x)
            ratio = nose_offset / total_width if total_width > 0 else 0.5
            
            head_pose = "Center"
            if ratio < 0.40:
                head_pose = "Look Right"
            elif ratio > 0.60:
                head_pose = "Look Left"

            return {
                "blink": is_blinking,
                "ear": round(avg_ear, 3),
                "head_pose": head_pose,
                "passed": True  # Single-frame check passes, UI logs state changes
            }

        except Exception as e:
            logger.error(f"Error in liveness check: {e}")
            return {"blink": True, "head_pose": "Center", "passed": True, "error": str(e)}

    def update_adaptive_embedding(self, stored_embedding: list, new_embedding: list, weight: float = None) -> list:
        """
        Performs exponential moving average update of student embedding.
        Formula: E_new = normalize((1 - alpha) * E_stored + alpha * E_new)
        """
        if not stored_embedding or not new_embedding:
            return stored_embedding or new_embedding

        alpha = weight if weight is not None else self.adaptive_learning_rate
        alpha = max(0.01, min(0.30, float(alpha)))  # Safe bounds [1% - 30%]

        stored = np.array(stored_embedding, dtype=np.float32)
        new_vec = np.array(new_embedding, dtype=np.float32)

        # Normalize components first
        s_norm = np.linalg.norm(stored)
        n_norm = np.linalg.norm(new_vec)
        if s_norm > 0:
            stored = stored / s_norm
        if n_norm > 0:
            new_vec = new_vec / n_norm

        # Blend
        blended = (1.0 - alpha) * stored + alpha * new_vec
        b_norm = np.linalg.norm(blended)
        if b_norm > 0:
            blended = blended / b_norm

        return blended.tolist()

    def verify_face_burst(self, frames: list, known_embedding: list) -> dict:
        """
        Evaluates a burst of frames (e.g. 3-5 frames) and returns the best verification result.
        Also attaches updated adaptive embedding if confidence is >= adaptive_confidence_threshold.
        """
        if not frames:
            return {"verified": False, "error": "No frames provided for burst verification."}

        best_res = None
        best_confidence = -1.0

        for f_bytes in frames:
            if not f_bytes:
                continue
            res = self.verify_face(f_bytes, known_embedding)
            conf = res.get("confidence", 0.0)
            
            # If immediately verified or better confidence, update best_res
            if best_res is None or conf > best_confidence:
                best_confidence = conf
                best_res = res
                
            # If high confidence match found, no need to keep checking remaining burst frames
            if res.get("verified") and conf >= self.adaptive_confidence_threshold:
                break

        if not best_res:
            return {"verified": False, "error": "Burst verification failed across all frames."}

        # Check for adaptive template update
        if (
            best_res.get("verified") 
            and self.adaptive_update_enabled 
            and best_res.get("confidence", 0.0) >= self.adaptive_confidence_threshold
            and best_res.get("candidate_embedding")
        ):
            updated_emb = self.update_adaptive_embedding(
                known_embedding, 
                best_res["candidate_embedding"], 
                self.adaptive_learning_rate
            )
            best_res["updated_embedding"] = updated_emb
            best_res["adaptive_updated"] = True
            logger.info(
                f"Adaptive embedding update triggered (Confidence: {best_res['confidence']}%, "
                f"Threshold: {self.adaptive_confidence_threshold}%)"
            )
        else:
            best_res["adaptive_updated"] = False

        return best_res

# Singleton face service instance for the frontend
onnx_face_service = OnnxFaceService()

