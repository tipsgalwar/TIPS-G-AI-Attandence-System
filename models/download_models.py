"""
TIPS-G ALWAR Student Attendance System — AI Model Downloader
Downloads required ONNX face recognition and MediaPipe models on-demand.
"""
import os
import sys
import requests
from pathlib import Path
try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger("model_downloader")

MODELS = {
    "retinaface_resnet50.onnx": {
        "url": "https://huggingface.co/TheEeeeLin/HivisionIDPhotos_matting/resolve/main/retinaface-resnet50.onnx",
        "min_size_bytes": 80 * 1024 * 1024,  # ~109 MB
        "description": "RetinaFace ResNet50 Face Detection Model"
    },
    "arcface_resnet50.onnx": {
        "url": "https://huggingface.co/garavv/arcface-onnx/resolve/main/arc.onnx",
        "min_size_bytes": 100 * 1024 * 1024,  # ~136 MB
        "description": "ArcFace ResNet50 Face Recognition/Embedding Model"
    },
    "face_landmarker.task": {
        "url": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "min_size_bytes": 2 * 1024 * 1024,  # ~3.75 MB
        "description": "MediaPipe Face Landmarker & Alignment Model"
    }
}


def download_file(url: str, dest_path: Path, timeout: int = 120) -> bool:
    """
    Downloads a model file atomically using a temporary .tmp file.
    Prevents corrupt files if download is interrupted.
    """
    temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading {dest_path.name} from {url}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(url, stream=True, timeout=timeout, headers=headers)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024 * 1024  # 1MB buffer
        downloaded = 0

        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(
                            f"Progress: {percent:.1f}% ({downloaded / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB)",
                            end='\r'
                        )
                    else:
                        print(f"Downloaded: {downloaded / (1024*1024):.1f}MB", end='\r')

        print()  # Newline after progress
        
        # Atomic rename once completely downloaded
        if temp_path.exists():
            if dest_path.exists():
                dest_path.unlink()
            temp_path.replace(dest_path)
            
        print(f"✓ Successfully saved {dest_path.name} ({dest_path.stat().st_size / (1024*1024):.1f} MB)\n")
        return True

    except Exception as e:
        print(f"\n❌ Error downloading {dest_path.name}: {e}", file=sys.stderr)
        logger.error(f"Download failed for {url}: {e}")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        return False


def ensure_models_exist(models_to_check=None, verbose=True) -> bool:
    """
    Checks if required model files exist and are valid.
    Downloads any missing model files automatically.
    
    :param models_to_check: Optional list of model filenames (e.g. ['arcface_resnet50.onnx'])
    :param verbose: Whether to print progress information
    :return: True if all models are present and valid, False otherwise.
    """
    if getattr(sys, 'frozen', False):
        project_root = Path(sys.executable).parent
    else:
        project_root = Path(__file__).resolve().parent.parent
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    target_models = models_to_check if models_to_check is not None else list(MODELS.keys())
    all_success = True
    
    for filename in target_models:
        if filename not in MODELS:
            logger.warning(f"Unknown model requested: {filename}")
            continue
            
        meta = MODELS[filename]
        dest = models_dir / filename
        min_size = meta.get("min_size_bytes", 1024 * 1024)
        
        # Check if already present and not truncated
        if dest.exists() and dest.stat().st_size >= min_size:
            if verbose:
                print(f"[OK] {filename} is ready ({dest.stat().st_size / (1024*1024):.1f} MB)")
            continue
            
        # File is missing or corrupted/truncated
        if dest.exists() and dest.stat().st_size < min_size:
            if verbose:
                print(f"[WARN] {filename} appears incomplete ({dest.stat().st_size} bytes). Re-downloading...")
            try:
                dest.unlink()
            except OSError:
                pass
                
        if verbose:
            print(f"[AUTO-DOWNLOAD] Fetching missing model: {filename} ({meta['description']})...")
            
        success = download_file(meta["url"], dest)
        if not success:
            all_success = False
            
    return all_success


def main():
    print("==========================================================")
    print("  TIPS-G ALWAR Face Recognition ONNX Model Downloader     ")
    print("==========================================================\n")
    
    success = ensure_models_exist(verbose=True)
    if success:
        print("All models verified and ready for face verification!")
    else:
        print("❌ Some models could not be downloaded. Please check your network connection.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
