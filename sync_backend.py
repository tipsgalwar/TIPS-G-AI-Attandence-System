import shutil
from pathlib import Path

def sync_backend():
    """Synchronizes all VPS backend files into the dedicated 'backend/' deployment folder."""
    root = Path(__file__).resolve().parent
    backend = root / "backend"
    backend.mkdir(exist_ok=True)

    items = ["src", "config", ".env"]
    for item in items:
        src_path = root / item
        dst_path = backend / item
        if src_path.exists():
            if src_path.is_dir():
                if dst_path.exists():
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
            elif src_path.is_file():
                shutil.copy2(src_path, dst_path)
    print("[SUCCESS] Backend deployment package synchronized successfully into 'backend/' folder.")

if __name__ == "__main__":
    sync_backend()
