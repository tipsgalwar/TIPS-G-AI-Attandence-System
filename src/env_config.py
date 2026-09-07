"""
Environment Configuration Loader
Loads environment variables from .env file and provides them to the application
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Load .env file from project root or current working directory if present
env_candidates = [
    Path.cwd() / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent / ".env"
]
for candidate in env_candidates:
    if candidate.is_file():
        load_dotenv(candidate, override=True)
        break

class EnvConfig:
    """Environment Configuration Manager"""
    
    @staticmethod
    def get(key: str, default: Any = None, var_type: type = str) -> Any:
        """
        Get environment variable with type casting
        
        Args:
            key: Environment variable name
            default: Default value if not found
            var_type: Type to cast to (str, int, bool, list)
        
        Returns:
            Environment variable value cast to specified type
        """
        value = os.getenv(key)
        
        if value is None:
            return default
        
        if var_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif var_type == int:
            return int(value)
        elif var_type == float:
            return float(value)
        elif var_type == list:
            # Parse comma-separated values or JSON array
            if isinstance(value, list):
                return value
            if value.startswith('['):
                import json
                return json.loads(value)
            return [v.strip() for v in value.split(',')]
        else:
            return str(value)

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        return EnvConfig.get(key, default, bool)

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        return EnvConfig.get(key, default, int)

    @staticmethod
    def get_float(key: str, default: float = 0.0) -> float:
        return EnvConfig.get(key, default, float)

    @staticmethod
    def get_list(key: str, default: list = None) -> list:
        if default is None:
            default = []
        return EnvConfig.get(key, default, list)


# ============================================================================
# ENVIRONMENT CONFIGURATION SCHEMA
# ============================================================================

class EnvironmentSettings:
    """All environment settings for the application"""
    
    # ======================= ENVIRONMENT =======================
    ENVIRONMENT: str = EnvConfig.get('ENVIRONMENT', 'development')
    DEBUG_MODE: bool = EnvConfig.get_bool('DEBUG_MODE', True)
    LOG_LEVEL: str = EnvConfig.get('LOG_LEVEL', 'INFO')
    
    # ======================= BACKEND =======================
    BACKEND_HOST: str = EnvConfig.get('BACKEND_HOST', '127.0.0.1')
    BACKEND_PORT: int = EnvConfig.get_int('BACKEND_PORT', 8000)
    BACKEND_URL: str = EnvConfig.get('BACKEND_URL', 'http://127.0.0.1:8000')
    
    # ======================= FRONTEND =======================
    FRONTEND_API_BASE_URL: str = EnvConfig.get('FRONTEND_API_BASE_URL', 'http://127.0.0.1:8000')
    FRONTEND_TIMEOUT: int = EnvConfig.get_int('FRONTEND_TIMEOUT', 30)
    APP_ICON_FILE: str = EnvConfig.get('APP_ICON_FILE', 'TIPS-G-ALWAR.ico')
    
    # ======================= DATABASE =======================
    DATABASE_TYPE: str = EnvConfig.get('DATABASE_TYPE', 'postgresql')
    DATABASE_URL: str = EnvConfig.get('DATABASE_URL', 'postgresql://postgres.fwyoktxjfuhbrruvyzkf:Tipsgalwar%40@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres')
    SQLITE_DB_PATH: str = EnvConfig.get('SQLITE_DB_PATH', '')
    POSTGRES_HOST: str = EnvConfig.get('POSTGRES_HOST', 'aws-0-ap-southeast-1.pooler.supabase.com')
    POSTGRES_PORT: int = EnvConfig.get_int('POSTGRES_PORT', 6543)
    POSTGRES_DB: str = EnvConfig.get('POSTGRES_DB', 'postgres')
    POSTGRES_USER: str = EnvConfig.get('POSTGRES_USER', 'postgres.fwyoktxjfuhbrruvyzkf')
    POSTGRES_PASSWORD: str = EnvConfig.get('POSTGRES_PASSWORD', 'Tipsgalwar@')
    
    # ======================= AUTHENTICATION =======================
    JWT_SECRET: str = EnvConfig.get('JWT_SECRET', 'supersecretkeychangeinproduction')
    JWT_ALGORITHM: str = EnvConfig.get('JWT_ALGORITHM', 'HS256')
    ACCESS_TOKEN_EXPIRE_MINUTES: int = EnvConfig.get_int('ACCESS_TOKEN_EXPIRE_MINUTES', 1440)
    
    # ======================= STORAGE =======================
    STORAGE_DIR: str = EnvConfig.get('STORAGE_DIR', 'storage')
    STUDENTS_STORAGE_DIR: str = EnvConfig.get('STUDENTS_STORAGE_DIR', 'storage/students')
    DOCUMENTS_STORAGE_DIR: str = EnvConfig.get('DOCUMENTS_STORAGE_DIR', 'storage/documents')
    
    # ======================= SUPABASE =======================
    SUPABASE_URL: str = EnvConfig.get('SUPABASE_URL', '')
    SUPABASE_KEY: str = EnvConfig.get('SUPABASE_KEY', '')
    SUPABASE_STORAGE_BUCKET: str = EnvConfig.get('SUPABASE_STORAGE_BUCKET', 'student-photos')
    
    # ======================= AI MODELS =======================
    FACE_DETECTOR_BACKEND: str = EnvConfig.get('FACE_DETECTOR_BACKEND', 'retinaface')
    FACE_RECOGNITION_MODEL: str = EnvConfig.get('FACE_RECOGNITION_MODEL', 'ArcFace')
    FACE_DISTANCE_METRIC: str = EnvConfig.get('FACE_DISTANCE_METRIC', 'cosine')
    FACE_SIMILARITY_THRESHOLD: float = EnvConfig.get_float('FACE_SIMILARITY_THRESHOLD', 0.40)
    MIN_CONFIDENCE_SCORE: float = EnvConfig.get_float('MIN_CONFIDENCE_SCORE', 65.0)
    
    # Liveness Detection
    LIVENESS_ENABLED: bool = EnvConfig.get_bool('LIVENESS_ENABLED', True)
    BLINK_DETECTION_ENABLED: bool = EnvConfig.get_bool('BLINK_DETECTION_ENABLED', True)
    EAR_THRESHOLD: float = EnvConfig.get_float('EAR_THRESHOLD', 0.20)
    HEAD_MOVEMENT_ENABLED: bool = EnvConfig.get_bool('HEAD_MOVEMENT_ENABLED', True)
    YAW_THRESHOLD: float = EnvConfig.get_float('YAW_THRESHOLD', 15.0)
    PITCH_THRESHOLD: float = EnvConfig.get_float('PITCH_THRESHOLD', 10.0)
    
    # ======================= NOTIFICATIONS =======================
    NOTIFICATIONS_ENABLED: bool = EnvConfig.get_bool('NOTIFICATIONS_ENABLED', True)
    
    # Email
    EMAIL_ENABLED: bool = EnvConfig.get_bool('EMAIL_ENABLED', False)
    EMAIL_PROVIDER: str = EnvConfig.get('EMAIL_PROVIDER', 'smtp')
    EMAIL_HOST: str = EnvConfig.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT: int = EnvConfig.get_int('EMAIL_PORT', 587)
    EMAIL_USERNAME: str = EnvConfig.get('EMAIL_USERNAME', '')
    EMAIL_PASSWORD: str = EnvConfig.get('EMAIL_PASSWORD', '')
    EMAIL_FROM: str = EnvConfig.get('EMAIL_FROM', 'attendance@tips-g.edu.in')
    
    # WhatsApp
    WHATSAPP_ENABLED: bool = EnvConfig.get_bool('WHATSAPP_ENABLED', False)
    WHATSAPP_API_URL: str = EnvConfig.get('WHATSAPP_API_URL', '')
    WHATSAPP_ACCOUNT_SID: str = EnvConfig.get('WHATSAPP_ACCOUNT_SID', '')
    WHATSAPP_AUTH_TOKEN: str = EnvConfig.get('WHATSAPP_AUTH_TOKEN', '')
    
    # SMS
    SMS_ENABLED: bool = EnvConfig.get_bool('SMS_ENABLED', False)
    SMS_PROVIDER: str = EnvConfig.get('SMS_PROVIDER', 'twilio')
    SMS_API_KEY: str = EnvConfig.get('SMS_API_KEY', '')
    
    # ======================= WIFI VALIDATION =======================
    WIFI_VALIDATION_ENABLED: bool = EnvConfig.get_bool('WIFI_VALIDATION_ENABLED', True)
    ALLOWED_WIFI_SSID: str = EnvConfig.get('ALLOWED_WIFI_SSID', 'TIPS-G-NETWORK')
    ALLOWED_WIFI_BSSID: str = EnvConfig.get('ALLOWED_WIFI_BSSID', '')
    
    # ======================= CORS =======================
    CORS_ORIGINS: list = EnvConfig.get_list('CORS_ORIGINS', ["http://127.0.0.1:8000"])
    CORS_CREDENTIALS: bool = EnvConfig.get_bool('CORS_CREDENTIALS', True)
    CORS_METHODS: list = EnvConfig.get_list('CORS_METHODS', ["GET", "POST", "PUT", "DELETE"])
    CORS_HEADERS: list = EnvConfig.get_list('CORS_HEADERS', ["*"])
    
    # ======================= LOGGING =======================
    LOG_TO_FILE: bool = EnvConfig.get_bool('LOG_TO_FILE', True)
    LOG_FILE_PATH: str = EnvConfig.get('LOG_FILE_PATH', 'logs/attendance_system.log')
    LOG_MAX_SIZE: int = EnvConfig.get_int('LOG_MAX_SIZE', 10485760)  # 10MB
    LOG_BACKUP_COUNT: int = EnvConfig.get_int('LOG_BACKUP_COUNT', 5)
    
    # ======================= FEATURE FLAGS =======================
    FEATURE_FACE_RECOGNITION: bool = EnvConfig.get_bool('FEATURE_FACE_RECOGNITION', True)
    FEATURE_LIVENESS_DETECTION: bool = EnvConfig.get_bool('FEATURE_LIVENESS_DETECTION', True)
    FEATURE_LEAVE_MANAGEMENT: bool = EnvConfig.get_bool('FEATURE_LEAVE_MANAGEMENT', True)
    FEATURE_HOLIDAY_MANAGEMENT: bool = EnvConfig.get_bool('FEATURE_HOLIDAY_MANAGEMENT', True)
    FEATURE_NOTIFICATIONS: bool = EnvConfig.get_bool('FEATURE_NOTIFICATIONS', True)
    FEATURE_REPORTS: bool = EnvConfig.get_bool('FEATURE_REPORTS', True)
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and key.isupper()
        }
    
    @classmethod
    def validate(cls) -> bool:
        """Validate critical environment settings"""
        errors = []
        
        # Check JWT Secret in production
        if cls.ENVIRONMENT == 'production':
            if cls.JWT_SECRET == 'supersecretkeychangeinproduction':
                errors.append("❌ JWT_SECRET must be changed for production!")
            
            if cls.DATABASE_TYPE == 'postgresql' and cls.POSTGRES_PASSWORD == 'password':
                errors.append("❌ POSTGRES_PASSWORD must be changed for production!")
        
        # Check database configuration
        if cls.DATABASE_TYPE == 'sqlite':
            if not cls.SQLITE_DB_PATH:
                errors.append("❌ SQLITE_DB_PATH is required for SQLite database!")
        elif cls.DATABASE_TYPE == 'postgresql':
            if not (cls.DATABASE_URL or all([cls.POSTGRES_HOST, cls.POSTGRES_DB, cls.POSTGRES_USER])):
                errors.append("❌ PostgreSQL configuration incomplete! Set DATABASE_URL or provide POSTGRES_HOST, POSTGRES_DB, and POSTGRES_USER.")
        
        if errors:
            print("\n🔴 CONFIGURATION VALIDATION ERRORS:")
            for error in errors:
                print(f"  {error}")
            return False
        
        print("\n✅ Configuration validation passed!")
        return True
    
    @classmethod
    def print_settings(cls):
        """Print current settings (hide sensitive values)"""
        print("\n" + "="*70)
        print("CURRENT ENVIRONMENT SETTINGS")
        print("="*70)
        
        settings_dict = cls.to_dict()
        sensitive_keys = {'JWT_SECRET', 'POSTGRES_PASSWORD', 'EMAIL_PASSWORD', 
                         'WHATSAPP_AUTH_TOKEN', 'SMS_API_KEY', 'SUPABASE_KEY'}
        
        for key, value in sorted(settings_dict.items()):
            if key in sensitive_keys:
                display_value = "***REDACTED***" if value else "NOT SET"
            else:
                display_value = value
            print(f"  {key:35s} = {display_value}")
        
        print("="*70 + "\n")


# Export settings instance
env_config = EnvironmentSettings()

if __name__ == "__main__":
    print("\n✅ Environment Configuration Loaded Successfully!")
    env_config.print_settings()
    env_config.validate()
