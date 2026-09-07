import os
import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance.load_all()
        return cls._instance

    def load_all(self):
        project_root = Path(__file__).resolve().parent.parent
        config_dir = project_root / "config"
        
        # Load default/template values if files are missing or incomplete
        self._config = {
            "system": {},
            "database": {},
            "attendance": {},
            "notifications": {},
            "ai_models": {}
        }

        config_files = ["system.yaml", "database.yaml", "attendance.yaml", "notifications.yaml", "ai_models.yaml"]
        for file in config_files:
            name = file.split(".")[0]
            path = config_dir / file
            if path.exists():
                with open(path, "r") as f:
                    try:
                        content = yaml.safe_load(f) or {}
                        # Extract the key name (e.g. 'system:') from file if present, else use raw dict
                        if name in content:
                            self._config[name] = content[name]
                        else:
                            self._config[name] = content
                    except Exception as e:
                        print(f"Error loading configuration file {file}: {e}")
            else:
                print(f"Config file not found: {path}. Using defaults.")

        # Ensure required directories exist
        storage_dir = Path(self._config["system"].get("storage_dir", "storage"))
        if not storage_dir.is_absolute():
            storage_dir = project_root / storage_dir

        # Expand system storage path to absolute
        self._config["system"]["storage_dir"] = str(storage_dir)
        self._config["system"]["students_dir"] = str(storage_dir / "students")
        self._config["system"]["documents_dir"] = str(storage_dir / "documents")

        os.makedirs(self._config["system"]["storage_dir"], exist_ok=True)
        os.makedirs(self._config["system"]["students_dir"], exist_ok=True)
        os.makedirs(self._config["system"]["documents_dir"], exist_ok=True)

    @property
    def system(self) -> Dict[str, Any]:
        return self._config.get("system", {})

    @property
    def database(self) -> Dict[str, Any]:
        return self._config.get("database", {})

    @property
    def attendance(self) -> Dict[str, Any]:
        return self._config.get("attendance", {})

    @property
    def notifications(self) -> Dict[str, Any]:
        return self._config.get("notifications", {})

    @property
    def ai_models(self) -> Dict[str, Any]:
        return self._config.get("ai_models", {})

# Singleton instance
settings = ConfigLoader()
