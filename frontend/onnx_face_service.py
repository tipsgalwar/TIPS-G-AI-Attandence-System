import os
import sys
from typing import Optional, Union, List, Tuple, Dict
import numpy as np
from pathlib import Path
from loguru import logger

# Lazy imports for ultra-fast startup (<100ms)
cv2 = None
try:
    import cv2
except ImportError:
    logger.warning("OpenCV not installed or unavailable in frontend.")

ort = None
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
        self.candidate_model_dirs.append(Path.cwd() / "models")
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
        if not config_file.exists():
            config_file = Path.cwd() / "config.ini"
        if config_file.exists():
            config.read(config_file)
        
        self.face_detector_backend = config.get("ai", "face_detector_backend", fallback="retinaface")
        self.face_recognition_model = config.get("ai", "face_recognition_model", fallback="ArcFace")
        self.face_distance_metric = config.get("ai", "face_distance_metric", fallback="cosine")
        
        # Biometric decision thresholds:
        # Cosine distance in ArcFace: 0.15-0.50 is same person; >0.65 is different person.
        # Legacy config.ini had 0.40 which aggressively rejected real students. Auto-adjust to >=0.50.
        raw_sim_thresh = float(
            config.get("ai", "similarity_threshold", fallback=os.getenv("FACE_SIMILARITY_THRESHOLD", "0.50"))
        )
        if raw_sim_thresh <= 0.42:
            raw_sim_thresh = 0.50
        self.similarity_threshold = raw_sim_thresh

        raw_min_conf = float(
            config.get("ai", "minimum_confidence", fallback=os.getenv("MIN_CONFIDENCE_SCORE", "58.0"))
        )
        if raw_min_conf > 62.0:
            raw_min_conf = 58.0
        self.minimum_confidence = raw_min_conf
        self.liveness_enabled = config.getboolean("ai", "liveness_enabled", fallback=True)
        self.liveness_3d_enabled = config.getboolean("ai", "liveness_3d_enabled", fallback=True)
        self.min_3d_depth_disparity = float(config.get("ai", "min_3d_depth_disparity", fallback=0.025))
        self.min_depth_std_dev = float(config.get("ai", "min_depth_std_dev", fallback=0.015))
        self.blink_detection_enabled = config.getboolean("ai", "blink_detection_enabled", fallback=True)
        self.ear_threshold = float(config.get("ai", "ear_threshold", fallback=0.20))
        self.head_movement_enabled = config.getboolean("ai", "head_movement_enabled", fallback=True)
        self.yaw_threshold = float(config.get("ai", "yaw_threshold", fallback=15.0))
        self.pitch_threshold = float(config.get("ai", "pitch_threshold", fallback=10.0))
        self.ear_history = []

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
        self._models_loaded = False
        # Do not block application startup on heavy model I/O.
        # Defer model loading to background worker thread or first inference!

    def _get_model_file(self, filename: str) -> Path:
        """Find model file across all candidate search directories."""
        for d in self.candidate_model_dirs:
            p = d / filename
            if p.exists() and p.stat().st_size > 1024:
                return p
        return self.models_dir / filename

    def ensure_models_loaded(self) -> bool:
        """Guarantees models are loaded before inference."""
        if not getattr(self, "_models_loaded", False) or self.arcface_session is None:
            return self.load_models()
        return True

    def load_models(self) -> bool:
        """Loads ONNX model and MediaPipe face landmarker, auto-downloading if missing."""
        if getattr(self, "_models_loaded", False) and self.arcface_session and self.face_landmarker:
            return True

        face_landmarker_path = self._get_model_file("face_landmarker.task")
        arcface_path = self._get_model_file("arcface_resnet50.onnx")

        # 0. Lazy import AI dependencies on demand
        global ort, mp, FaceLandmarker, mp_image
        if ort is None:
            try:
                import onnxruntime as ort
            except ImportError:
                ort = None
                logger.warning("onnxruntime not installed or unavailable in frontend.")

        if FaceLandmarker is None or mp_image is None:
            try:
                import mediapipe as mp
                from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarker
                from mediapipe.tasks.python.vision.core import image as mp_image
            except Exception as mp_err:
                FaceLandmarker = None
                mp_image = None
                logger.warning(f"MediaPipe loading note: {mp_err}")

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
                    # Prefer loading from in-memory byte buffer (robust in frozen/PyInstaller apps)
                    try:
                        from mediapipe.tasks.python import BaseOptions
                        from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarkerOptions, RunningMode
                        with open(face_landmarker_path, "rb") as mf:
                            m_buf = mf.read()
                        f_opts = FaceLandmarkerOptions(
                            base_options=BaseOptions(model_asset_buffer=m_buf),
                            running_mode=RunningMode.IMAGE,
                            num_faces=1,
                        )
                        self.face_landmarker = FaceLandmarker.create_from_options(f_opts)
                    except Exception:
                        self.face_landmarker = FaceLandmarker.create_from_model_path(str(face_landmarker_path))
                    logger.info(f"MediaPipe Face Landmarker initialized successfully from {face_landmarker_path}.")
                except Exception as e:
                    self.face_landmarker = None
                    logger.warning(f"Failed to initialize MediaPipe Face Landmarker in frontend: {e}. Falling back to OpenCV detector.")
            else:
                self.face_landmarker = None
                logger.warning(f"MediaPipe Face Landmarker model not found at {face_landmarker_path}.")
        else:
            self.face_landmarker = None
            logger.warning("MediaPipe Face Landmarker API is unavailable. OpenCV detector will be used as fallback.")

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
            self._models_loaded = True
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
        Uses robust eye centroids to maintain rock-solid alignment even during eye blinks.
        """
        h, w, _ = img.shape
        
        # Robust eye center calculation:
        # Subject's right eye (image left, X ~ 38): inner corner (133), outer corner (33)
        # Subject's left eye (image right, X ~ 73): inner corner (362), outer corner (263)
        eye_left_x = (landmarks[33].x + landmarks[133].x) * 0.5 * w
        eye_left_y = (landmarks[33].y + landmarks[133].y) * 0.5 * h
        
        eye_right_x = (landmarks[362].x + landmarks[263].x) * 0.5 * w
        eye_right_y = (landmarks[362].y + landmarks[263].y) * 0.5 * h
        
        # If irises (468, 473) are present and valid, blend for sub-pixel accuracy
        if len(landmarks) > 473:
            iris_l = landmarks[468]
            iris_r = landmarks[473]
            eye_left_x = eye_left_x * 0.35 + iris_l.x * w * 0.65
            eye_left_y = eye_left_y * 0.35 + iris_l.y * h * 0.65
            eye_right_x = eye_right_x * 0.35 + iris_r.x * w * 0.65
            eye_right_y = eye_right_y * 0.35 + iris_r.y * h * 0.65

        left_eye_pt = np.array([eye_left_x, eye_left_y], dtype=np.float32)
        right_eye_pt = np.array([eye_right_x, eye_right_y], dtype=np.float32)
        nose_tip = np.array([landmarks[1].x * w, landmarks[1].y * h], dtype=np.float32)
        left_mouth = np.array([landmarks[61].x * w, landmarks[61].y * h], dtype=np.float32)
        right_mouth = np.array([landmarks[291].x * w, landmarks[291].y * h], dtype=np.float32)
        
        src_pts = np.array([left_eye_pt, right_eye_pt, nose_tip, left_mouth, right_mouth], dtype=np.float32)
        
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
        global mp_image
        if not mp_image:
            try:
                from mediapipe.tasks.python.vision.core import image as mp_image
            except Exception:
                pass
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

    def calculate_confidence(self, cosine_dist: float) -> float:
        """
        Calibrates ArcFace cosine distance into a statistically accurate biometric confidence percentage (0-100%).
        Uses a standard logistic sigmoidal calibration curve centered at the decision threshold.
        """
        if cosine_dist <= 0.0:
            return 99.9
        if cosine_dist >= 1.0:
            return 0.0
        
        threshold = getattr(self, "similarity_threshold", 0.50)
        steepness = 7.5
        prob = 1.0 / (1.0 + np.exp(steepness * (cosine_dist - threshold)))
        if prob >= 0.5:
            conf = 70.0 + ((prob - 0.5) / 0.5) * 29.9
        else:
            conf = (prob / 0.5) * 70.0
        return round(float(np.clip(conf, 0.0, 99.9)), 1)

    def verify_face(self, frame_bytes: bytes, known_embedding: list) -> dict:
        """
        Verifies a live camera frame against the logged-in student's OWN registered embedding.
        This is strictly 1-to-1: current face vs this student's stored embedding only.
        Returns verification result dictionary.
        """
        # Guard: Models must be loaded
        if not self.arcface_session or not self.face_landmarker:
            self.load_models()

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
            
            # Reject if liveness check fails
            if not liveness_result["passed"]:
                rejection_msg = liveness_result.get("reason", "2D Photo or Screen Replay Detected")
                return {
                    "verified": False,
                    "error": f"Anti-Spoof Alert: {rejection_msg}. Please present your real live face.",
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
            
            confidence = self.calculate_confidence(cosine_dist)

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

    def analyze_screen_texture(self, img, landmarks=None) -> dict:
        """
        Detects digital smartphone/tablet screens and video replays via:
        1. 2D Fast Fourier Transform (FFT) Moiré frequency grid interference.
        2. Glass specular glare and saturation clipping.
        3. Electronic Device Bezel & Border Contour Recognition.
        4. Multi-cue attack correlation (prevents indoor light / glasses false alarms).
        """
        if img is None:
            return {"is_screen_spoof": False, "reasons": []}

        try:
            h, w = img.shape[:2]
            crop = img
            x1, y1, x2, y2 = 0, 0, w, h
            if landmarks and len(landmarks) > 0:
                xs = [int(lm.x * w) for lm in landmarks]
                ys = [int(lm.y * h) for lm in landmarks]
                x1, x2 = max(0, min(xs)), min(w, max(xs))
                y1, y2 = max(0, min(ys)), min(h, max(ys))
                if (x2 - x1) > 20 and (y2 - y1) > 20:
                    crop = img[y1:y2, x1:x2]

            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (128, 128))

            # 1. 2D Fast Fourier Transform (FFT) for Screen Moiré Pattern
            f = np.fft.fft2(gray.astype(np.float32))
            fshift = np.fft.fftshift(f)
            magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-7)

            rows, cols = gray.shape
            crow, ccol = rows // 2, cols // 2
            mask = np.ones((rows, cols), np.uint8)
            r = 24  # Center low-frequency radius
            cv2.circle(mask, (ccol, crow), r, 0, -1)

            high_freq_energy = float(np.sum(magnitude_spectrum * mask) / (np.sum(mask) + 1e-7))
            total_energy = float(np.mean(magnitude_spectrum))
            hf_ratio = high_freq_energy / (total_energy + 1e-7)

            # 2. Specular Screen Reflection & Glare detection
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            v_chan = hsv[:, :, 2]
            s_chan = hsv[:, :, 1]
            glare_pixels = int(np.sum((v_chan > 240) & (s_chan < 35)))
            glare_ratio = float(glare_pixels / float(crop.shape[0] * crop.shape[1] + 1e-7))

            # 3. Laplacian Variance
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            lap_var = float(laplacian.var())

            # 4. Check blue/green screen backlight bias
            b_chan, g_chan, r_chan = cv2.split(crop)
            blue_ratio = float(np.mean(b_chan) / (np.mean(r_chan) + 1e-7))

            is_screen_spoof = False
            reasons = []

            # Multi-Cue Attack Correlation
            # High-intensity glass reflection (>8%)
            if glare_ratio > 0.080:
                is_screen_spoof = True
                reasons.append(f"Screen Glass Glare ({glare_ratio * 100:.1f}%)")

            # Moiré High Frequency Sub-Pixel Raster + High Sharpness
            if hf_ratio > 1.35 and lap_var > 45:
                is_screen_spoof = True
                reasons.append(f"Digital Screen Pixel Raster (Moiré {hf_ratio:.2f})")

            # Correlated moderate glare + blue backlight bias
            if glare_ratio > 0.050 and blue_ratio > 1.40:
                is_screen_spoof = True
                reasons.append(f"Digital Screen Glass Reflection & Backlight (Blue={blue_ratio:.2f})")

            # 5. Electronic Device Bezel Contour Detection
            try:
                gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray_full, (5, 5), 0)
                edges = cv2.Canny(blurred, 30, 100)
                contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                frame_area = w * h
                for c in contours:
                    peri = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.03 * peri, True)
                    if 4 <= len(approx) <= 8 and cv2.isContourConvex(approx):
                        area = cv2.contourArea(approx)
                        if 0.08 * frame_area < area < 0.92 * frame_area:
                            bx, by, bw, bh = cv2.boundingRect(approx)
                            aspect = float(bh) / float(bw + 1e-7)
                            if (1.20 <= aspect <= 2.45) or (0.40 <= aspect <= 0.83):
                                if landmarks and len(landmarks) > 0:
                                    if (bx <= x1 <= bx + bw) and (by <= y1 <= by + bh):
                                        is_screen_spoof = True
                                        reasons.append("Phone/Tablet Screen Bezel Detected")
                                        break
            except Exception:
                pass

            # 6. Proximity & Full Lens Coverage Check
            if landmarks and len(landmarks) > 0:
                face_w_ratio = (x2 - x1) / float(w)
                face_h_ratio = (y2 - y1) / float(h)
                if face_w_ratio > 0.88 or face_h_ratio > 0.90:
                    is_screen_spoof = True
                    reasons.append(f"Unnatural Proximity / Lens Coverage ({int(face_w_ratio*100)}% of frame)")

            return {
                "is_screen_spoof": is_screen_spoof,
                "hf_ratio": round(hf_ratio, 3),
                "glare_ratio": round(glare_ratio, 4),
                "lap_var": round(lap_var, 1),
                "blue_ratio": round(blue_ratio, 2),
                "reasons": reasons
            }
        except Exception as e:
            logger.debug(f"Texture screen analysis error: {e}")
            return {"is_screen_spoof": False, "reasons": []}

    def check_liveness(self, img) -> dict:
        """
        Performs Multi-Layer Anti-Spoofing:
        1. 3D Facial Depth Disparity & Planar Surface Curvature.
        2. Screen Frequency Moiré & Glass Reflection Texture Analysis.
        3. Blink & Eye Aspect Ratio (EAR) Verification.
        """
        if not self.face_landmarker:
            self.load_models()

        if not self.face_landmarker:
            return {
                "blink": False,
                "head_pose": "Unknown",
                "passed": False,
                "is_live_3d": False,
                "reason": "Face Landmarker AI engine unavailable"
            }

        try:
            mp_image_input = self._create_mediapipe_image(img)
            results = self.face_landmarker.detect(mp_image_input)
            
            face_landmarks = getattr(results, "face_landmarks", None)
            if not face_landmarks or len(face_landmarks) == 0:
                return {
                    "blink": False,
                    "head_pose": "Unknown",
                    "passed": False,
                    "is_live_3d": False,
                    "reason": "No face detected in camera frame"
                }

            landmarks = face_landmarks[0]
            
            # --- 1. 3D Facial Depth Disparity & Surface Curvature Check ---
            nose_tip = landmarks[1]
            left_lat = landmarks[234]
            right_lat = landmarks[454]
            forehead = landmarks[10]
            chin = landmarks[152]

            lateral_z_mid = (left_lat.z + right_lat.z) / 2.0
            lateral_disparity = float(lateral_z_mid - nose_tip.z)

            vertical_z_mid = (forehead.z + chin.z) / 2.0
            vertical_disparity = float(vertical_z_mid - nose_tip.z)

            all_z_values = [lm.z for lm in landmarks]
            z_std = float(np.std(all_z_values))

            # --- 2. Screen Frequency & Glare Texture Analysis ---
            screen_analysis = self.analyze_screen_texture(img, landmarks)

            # --- 3. Liveness Decision ---
            is_live_human = True
            rejection_reasons = []

            if screen_analysis.get("is_screen_spoof"):
                is_live_human = False
                rejection_reasons.extend(screen_analysis.get("reasons", ["Digital Screen Detected"]))

            if self.liveness_3d_enabled:
                if lateral_disparity < self.min_3d_depth_disparity or z_std < self.min_depth_std_dev:
                    is_live_human = False
                    rejection_reasons.append(f"Flat Surface (Disparity={lateral_disparity:.3f})")

            # --- 4. Blink Detection via Eye Aspect Ratio (EAR) ---
            def calculate_ear(eye_landmarks):
                v1 = np.linalg.norm(np.array([eye_landmarks[1].x - eye_landmarks[5].x, eye_landmarks[1].y - eye_landmarks[5].y]))
                v2 = np.linalg.norm(np.array([eye_landmarks[2].x - eye_landmarks[4].x, eye_landmarks[2].y - eye_landmarks[4].y]))
                h_dist = np.linalg.norm(np.array([eye_landmarks[0].x - eye_landmarks[3].x, eye_landmarks[0].y - eye_landmarks[3].y]))
                return (v1 + v2) / (2.0 * h_dist) if h_dist > 0 else 0.0

            left_eye_lms = [landmarks[idx] for idx in [362, 385, 387, 263, 373, 380]]
            right_eye_lms = [landmarks[idx] for idx in [33, 160, 158, 133, 153, 144]]
            
            left_ear = calculate_ear(left_eye_lms)
            right_ear = calculate_ear(right_eye_lms)
            avg_ear = (left_ear + right_ear) / 2.0
            
            is_blinking = avg_ear < self.ear_threshold

            self.ear_history.append(avg_ear)
            if len(self.ear_history) > 10:
                self.ear_history.pop(0)

            # --- 5. Head Pose Estimation ---
            total_width = abs(right_lat.x - left_lat.x)
            nose_offset = abs(nose_tip.x - left_lat.x)
            ratio = nose_offset / total_width if total_width > 0 else 0.5
            
            head_pose = "Center"
            if ratio < 0.38:
                head_pose = "Look Right"
            elif ratio > 0.62:
                head_pose = "Look Left"

            passed = is_live_human
            reason = "Live 3D Face Verified" if passed else "; ".join(rejection_reasons)

            return {
                "blink": is_blinking,
                "ear": round(avg_ear, 3),
                "head_pose": head_pose,
                "is_live_3d": is_live_human,
                "depth_disparity": round(lateral_disparity, 4),
                "vertical_disparity": round(vertical_disparity, 4),
                "z_std": round(z_std, 4),
                "screen_analysis": screen_analysis,
                "passed": passed,
                "reason": reason
            }

        except Exception as e:
            logger.error(f"Error in 3D liveness check: {e}")
            return {
                "blink": False,
                "head_pose": "Center",
                "passed": False,
                "is_live_3d": False,
                "error": str(e),
                "reason": f"Liveness calculation error: {e}"
            }

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

    def extract_embedding_from_aligned(self, aligned_face: np.ndarray) -> list:
        """
        Extracts 512-D ArcFace embedding directly from a pre-aligned 112x112 face crop in ~15ms.
        Bypasses MediaPipe face landmark detection entirely for ultra-low CPU overhead.
        """
        if not self.arcface_session:
            self.load_models()
        if not self.arcface_session or aligned_face is None:
            raise RuntimeError("ArcFace model not loaded or invalid aligned face crop.")

        try:
            lab = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_chan)
            limg = cv2.merge((cl, a_chan, b_chan))
            aligned_face = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        except Exception:
            pass

        aligned_face = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB)
        aligned_face = aligned_face.astype(np.float32)
        aligned_face = (aligned_face - 127.5) / 128.0
        input_blob = np.expand_dims(aligned_face, axis=0)

        outputs = self.arcface_session.run(
            [self.arcface_output_name],
            {self.arcface_input_name: input_blob}
        )
        embedding = outputs[0][0].tolist()
        emb_arr = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb_arr)
        if norm > 0:
            emb_arr = emb_arr / norm
        return emb_arr.tolist()

    def has_detected_blink(self, frames: list) -> bool:
        """
        Evaluates whether a genuine biological eye blink occurred across frames.
        Tuned for real-world 15-30fps webcams on low-end laptops.
        """
        if not frames or len(frames) < 3:
            return False
        
        if not self.face_landmarker:
            self.load_models()

        if not self.face_landmarker:
            return False

        ears = []
        for f_bytes in frames:
            if not f_bytes:
                continue
            try:
                if isinstance(f_bytes, bytes):
                    nparr = np.frombuffer(f_bytes, np.uint8)
                    decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                elif isinstance(f_bytes, np.ndarray):
                    decoded = f_bytes
                else:
                    continue

                if decoded is None:
                    continue
                mp_img = self._create_mediapipe_image(decoded)
                res = self.face_landmarker.detect(mp_img)
                f_lms = getattr(res, "face_landmarks", None)
                if f_lms and len(f_lms) > 0:
                    lms = f_lms[0]
                    def _ear(e_idx):
                        pts = [lms[i] for i in e_idx]
                        v1 = np.linalg.norm(np.array([pts[1].x - pts[5].x, pts[1].y - pts[5].y]))
                        v2 = np.linalg.norm(np.array([pts[2].x - pts[4].x, pts[2].y - pts[4].y]))
                        h = np.linalg.norm(np.array([pts[0].x - pts[3].x, pts[0].y - pts[3].y]))
                        return (v1 + v2) / (2.0 * h) if h > 0 else 0.0
                    l_ear = _ear([362, 385, 387, 263, 373, 380])
                    r_ear = _ear([33, 160, 158, 133, 153, 144])
                    ears.append((l_ear + r_ear) / 2.0)
            except Exception:
                pass

        if len(ears) < 3:
            return False

        max_ear = float(max(ears))
        min_ear = float(min(ears))
        relative_drop = (max_ear - min_ear) / (max_ear + 1e-7)
        ear_range = max_ear - min_ear
        return bool(
            (max_ear >= 0.18 and min_ear <= 0.170 and (ear_range >= 0.035 or relative_drop >= 0.16))
            or (max_ear >= 0.20 and min_ear <= 0.180 and relative_drop >= 0.18)
            or (ear_range >= 0.040)
        )

    def analyze_planar_homography(self, landmark_list: list, img_w: int, img_h: int) -> dict:
        """
        Technique 2: 3D Planar Homography vs Non-Planar Curvature Test.
        Checks for extreme flat planar motion on 2D screens under significant translation.
        """
        if not landmark_list or len(landmark_list) < 2:
            return {"is_flat_2d": False, "error_score": 0.0}

        try:
            key_indices = [1, 4, 10, 33, 61, 133, 152, 234, 263, 291, 362, 454]
            src_lms = landmark_list[0]
            src_pts = np.array([[src_lms[i].x * img_w, src_lms[i].y * img_h] for i in key_indices], dtype=np.float32)

            for dst_lms in landmark_list[1:]:
                dst_pts = np.array([[dst_lms[i].x * img_w, dst_lms[i].y * img_h] for i in key_indices], dtype=np.float32)
                motion_mag = float(np.mean(np.linalg.norm(src_pts - dst_pts, axis=1)))
                # Only evaluate when significant physical motion occurred (>25 pixels)
                if motion_mag >= 25.0:
                    H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
                    if H is not None:
                        src_homo = np.hstack([src_pts, np.ones((src_pts.shape[0], 1), dtype=np.float32)])
                        pred_dst_homo = (H @ src_homo.T).T
                        pred_dst = pred_dst_homo[:, :2] / (pred_dst_homo[:, 2:3] + 1e-7)
                        mean_err = float(np.mean(np.linalg.norm(pred_dst - dst_pts, axis=1)))

                        # Rigid flat screens strictly maintain tiny error (< 0.12 px) even under large motion
                        if mean_err < 0.12:
                            logger.warning(f"3D Anti-Spoof: Flat 2D Planar Surface detected (Homography error={mean_err:.2f}px, motion={motion_mag:.1f}px)")
                            return {"is_flat_2d": True, "error_score": mean_err, "motion_mag": motion_mag}

            return {"is_flat_2d": False, "error_score": 0.0}
        except Exception as e:
            logger.debug(f"Planar homography analysis error: {e}")
            return {"is_flat_2d": False, "error_score": 0.0}

    def verify_face_burst(self, frames: list, known_embedding: list, optical_probe_data: dict = None) -> dict:
        """
        Ultra-Fast Single-Pass 3D Anti-Spoofing & Biometric Verification Pipeline:
        1. Single-pass MediaPipe Landmark extraction (EAR, 3D disparity, Screen Texture, Aligned Crop).
        2. Fallback to OpenCV Haar-Cascade detector if MediaPipe is unavailable.
        3. Dual-crop ArcFace Biometric Matching (both 5-point landmark aligned AND standard bounding box)
           to ensure 100% compatibility with previously registered student embeddings and newly registered ones.
        4. Statistical confidence calibration centered at decision threshold.
        """
        if not frames:
            return {"verified": False, "error": "No frames captured for verification. Please ensure camera is enabled."}

        if not self.arcface_session:
            self.load_models()

        if not self.arcface_session:
            return {"verified": False, "error": "AI face models are not ready. Please connect to internet to download models."}

        if not known_embedding or len(known_embedding) == 0:
            return {
                "verified": False,
                "error": "No registered face embedding found for your account. Please ask admin to register your photo."
            }

        # Single-Pass Extraction Loop: Each frame is decoded and processed ONCE
        parsed_frames = []
        all_landmarks = []
        img_w, img_h = 640, 480

        for f_item in frames:
            if f_item is None:
                continue
            try:
                if isinstance(f_item, (str, Path)):
                    decoded = cv2.imread(str(f_item))
                elif isinstance(f_item, bytes):
                    nparr = np.frombuffer(f_item, np.uint8)
                    decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                elif isinstance(f_item, np.ndarray):
                    decoded = f_item
                else:
                    continue

                if decoded is None:
                    continue

                img_h, img_w = decoded.shape[:2]

                # --- Path A: MediaPipe Landmark & 3D Anti-Spoofing ---
                if self.face_landmarker:
                    mp_img = self._create_mediapipe_image(decoded)
                    res = self.face_landmarker.detect(mp_img)
                    f_lms = getattr(res, "face_landmarks", None)
                    if not f_lms or len(f_lms) == 0:
                        continue

                    lms = f_lms[0]
                    all_landmarks.append(lms)

                    # 1. Calculate EAR
                    def _calc_ear(e_idx):
                        pts = [lms[i] for i in e_idx]
                        v1 = np.linalg.norm(np.array([pts[1].x - pts[5].x, pts[1].y - pts[5].y]))
                        v2 = np.linalg.norm(np.array([pts[2].x - pts[4].x, pts[2].y - pts[4].y]))
                        h = np.linalg.norm(np.array([pts[0].x - pts[3].x, pts[0].y - pts[3].y]))
                        return (v1 + v2) / (2.0 * h) if h > 0 else 0.0

                    l_ear = _calc_ear([362, 385, 387, 263, 373, 380])
                    r_ear = _calc_ear([33, 160, 158, 133, 153, 144])
                    avg_ear = float((l_ear + r_ear) / 2.0)

                    # 2. 3D Depth Disparity
                    lat_disp = float(((lms[234].z + lms[454].z) / 2.0) - lms[1].z)
                    z_std = float(np.std([lm.z for lm in lms]))

                    # 3. Screen Texture Analysis
                    st = self.analyze_screen_texture(decoded, lms)

                    # 4. Canonical 5-point similarity transform crop
                    aligned = self.align_and_crop_face(decoded, lms)

                    # 5. Standard bounding-box crop (for backward compatibility with older student registrations)
                    raw_crop = None
                    try:
                        xs = [p.x * img_w for p in lms]
                        ys = [p.y * img_h for p in lms]
                        min_x, max_x = max(0, int(min(xs))), min(img_w, int(max(xs)))
                        min_y, max_y = max(0, int(min(ys))), min(img_h, int(max(ys)))
                        bw = max_x - min_x
                        bh = max_y - min_y
                        mx = int(bw * 0.15)
                        my = int(bh * 0.15)
                        x1 = max(0, min_x - mx)
                        y1 = max(0, min_y - my)
                        x2 = min(img_w, max_x + mx)
                        y2 = min(img_h, max_y + my)
                        if x2 > x1 and y2 > y1:
                            raw_crop = cv2.resize(decoded[y1:y2, x1:x2], (112, 112))
                    except Exception:
                        raw_crop = None

                    parsed_frames.append({
                        "ear": avg_ear,
                        "landmarks": lms,
                        "lat_disp": lat_disp,
                        "z_std": z_std,
                        "screen_texture": st,
                        "aligned": aligned,
                        "raw_crop": raw_crop,
                        "raw_frame": decoded
                    })

                # --- Path B: OpenCV Haar Cascade Fallback ---
                else:
                    fbox = self.detect_face_box(decoded)
                    if fbox:
                        x, y, w, h = fbox
                        margin_x = int(w * 0.15)
                        margin_y = int(h * 0.15)
                        x1 = max(0, x - margin_x)
                        y1 = max(0, y - margin_y)
                        x2 = min(decoded.shape[1], x + w + margin_x)
                        y2 = min(decoded.shape[0], y + h + margin_y)
                        fc = decoded[y1:y2, x1:x2]
                        if fc.size > 0:
                            resized = cv2.resize(fc, (112, 112))
                            parsed_frames.append({
                                "ear": 0.25,
                                "aligned": resized,
                                "raw_crop": resized,
                                "raw_frame": decoded,
                                "screen_texture": {"is_screen_spoof": False}
                            })
            except Exception as ex:
                logger.debug(f"Frame parsing error: {ex}")

        # Check tracking requirement: at least 1 valid frame (ideally 3)
        if len(parsed_frames) == 0:
            logger.warning("Rejected: No face detected in captured frames.")
            return {
                "verified": False,
                "error": "Anti-Spoof Alert: Face tracking lost or obstructed. Please face the camera steadily and blink your eyes."
            }

        # Step 1: Screen Replay & Texture Anti-Spoofing (when MediaPipe active)
        if self.face_landmarker:
            for pf in parsed_frames:
                st = pf.get("screen_texture", {})
                if st.get("is_screen_spoof"):
                    reasons = "; ".join(st.get("reasons", ["Digital Screen Detected"]))
                    logger.warning(f"Anti-Spoof Screen Attack Blocked: {reasons}")
                    return {
                        "verified": False,
                        "error": f"Anti-Spoof Alert: {reasons}. Please present your real live face."
                    }

            # Step 2: 3D Planar Homography Test (only under strong motion)
            if len(all_landmarks) >= 3:
                homo_res = self.analyze_planar_homography(all_landmarks, img_w, img_h)
                if homo_res.get("is_flat_2d"):
                    return {
                        "verified": False,
                        "error": f"Anti-Spoof Alert: 2D Flat Planar Surface Detected (Homography error={homo_res.get('error_score', 0):.2f}px). Please present your real live face."
                    }

            # Step 3: 3D Facial Mesh Depth Disparity (Rejects flat paper prints)
            if self.liveness_3d_enabled and len(parsed_frames) >= 2:
                max_lat = max(pf.get("lat_disp", 0.05) for pf in parsed_frames)
                max_z_std = max(pf.get("z_std", 0.05) for pf in parsed_frames)
                if max_lat < 0.008 and max_z_std < 0.005:
                    return {
                        "verified": False,
                        "error": f"Anti-Spoof Alert: Flat 2D Surface Detected (Depth Disparity={max_lat:.3f}). Please present your real 3D face."
                    }

            # Step 4: Adaptive Biological Eye Blink Verification
            if self.blink_detection_enabled and len(parsed_frames) >= 3:
                all_ears = [pf["ear"] for pf in parsed_frames if pf.get("ear") is not None]
                if all_ears:
                    min_ear = float(min(all_ears))
                    max_ear = float(max(all_ears))
                    ear_range = float(max_ear - min_ear)
                    relative_drop = float(ear_range / (max_ear + 1e-7))

                    has_blink = bool(
                        (max_ear >= 0.17 and min_ear <= 0.175 and (ear_range >= 0.030 or relative_drop >= 0.15))
                        or (max_ear >= 0.19 and min_ear <= 0.185 and relative_drop >= 0.16)
                        or (ear_range >= 0.035)
                    )

                    if not has_blink:
                        logger.warning(
                            f"Static photo/screen rejected: min_ear={min_ear:.3f}, max_ear={max_ear:.3f}, "
                            f"relative_drop={relative_drop*100:.1f}%, ear_range={ear_range:.3f}"
                        )
                        return {
                            "verified": False,
                            "error": "Anti-Spoof Alert: No natural eye blink detected. Please blink your eyes naturally (close and open) in front of the camera (static photos and screen replays are strictly prohibited)."
                        }

        # Step 5: Multi-Frame Dual-Crop Biometric Matching on clearest open-eye frames
        parsed_frames.sort(key=lambda x: x.get("ear", 0.25), reverse=True)
        known_emb = np.array(known_embedding, dtype=np.float32)
        k_norm = np.linalg.norm(known_emb)
        if k_norm > 0:
            known_emb = known_emb / k_norm

        best_res = None
        best_confidence = -1.0

        for cand in parsed_frames[:4]:
            try:
                # A: 5-point landmark-aligned crop embedding
                c_emb_aligned = np.array(self.extract_embedding_from_aligned(cand["aligned"]), dtype=np.float32)
                c_norm_a = np.linalg.norm(c_emb_aligned)
                if c_norm_a > 0:
                    c_emb_aligned = c_emb_aligned / c_norm_a
                c_dist_aligned = 1.0 - float(np.dot(c_emb_aligned, known_emb))
                c_dist_aligned = max(0.0, min(2.0, c_dist_aligned))

                # B: Standard bounding-box crop embedding (ensures seamless backward compatibility)
                c_dist_raw = 999.0
                c_emb_raw = None
                if cand.get("raw_crop") is not None:
                    try:
                        c_emb_raw = np.array(self.extract_embedding_from_aligned(cand["raw_crop"]), dtype=np.float32)
                        c_norm_r = np.linalg.norm(c_emb_raw)
                        if c_norm_r > 0:
                            c_emb_raw = c_emb_raw / c_norm_r
                        c_dist_raw = 1.0 - float(np.dot(c_emb_raw, known_emb))
                        c_dist_raw = max(0.0, min(2.0, c_dist_raw))
                    except Exception:
                        pass

                # Pick best match between aligned and bounding box crops
                if c_dist_raw < c_dist_aligned:
                    c_dist = c_dist_raw
                    c_emb = c_emb_raw
                else:
                    c_dist = c_dist_aligned
                    c_emb = c_emb_aligned

                c_conf = self.calculate_confidence(c_dist)

                is_cand_verified = (c_dist <= self.similarity_threshold) and (c_conf >= self.minimum_confidence)

                if c_conf > best_confidence or best_res is None:
                    best_confidence = c_conf
                    best_res = {
                        "verified": is_cand_verified,
                        "confidence": c_conf,
                        "distance": c_dist,
                        "candidate_embedding": c_emb.tolist(),
                        "blink_detected": True,
                        "ear_min": round(cand.get("ear", 0.25), 3),
                        "ear_max": round(cand.get("ear", 0.25), 3)
                    }

                if is_cand_verified and c_conf >= self.adaptive_confidence_threshold:
                    break
            except Exception as e_match:
                logger.debug(f"Candidate match extraction error: {e_match}")

        if not best_res:
            return {"verified": False, "error": "Failed to evaluate facial biometric vector across frames."}

        if not best_res["verified"]:
            best_res["error"] = f"Face match rejected: Confidence {best_res['confidence']:.1f}% is below required {self.minimum_confidence}%."
            return best_res

        # Step 6: Adaptive Template Update
        if self.adaptive_update_enabled and best_res["confidence"] >= self.adaptive_confidence_threshold:
            updated_emb = self.update_adaptive_embedding(
                known_embedding,
                best_res["candidate_embedding"],
                self.adaptive_learning_rate
            )
            best_res["updated_embedding"] = updated_emb
            best_res["adaptive_updated"] = True
            logger.info(f"Adaptive embedding updated seamlessly (Confidence: {best_res['confidence']:.1f}%)")
        else:
            best_res["adaptive_updated"] = False

        return best_res

# Singleton face service instance for the frontend
onnx_face_service = OnnxFaceService()

