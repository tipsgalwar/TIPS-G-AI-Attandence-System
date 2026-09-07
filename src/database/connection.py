import os
from urllib.parse import quote_plus, unquote
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger
from src.env_config import EnvironmentSettings
from src.database.models import Base


def _env_or_config(key: str, default=None):
    value = os.getenv(key)
    if value is not None:
        return value
    return getattr(EnvironmentSettings, key, default)


def sanitize_db_url(url_str: str) -> str:
    """Sanitize database URL by auto-encoding special characters in username/password."""
    if not url_str:
        return ""
    url_str = url_str.strip().strip("'\"").strip()
    
    # Strip accidental duplicate variable names like DATABASE_URL=postgresql://
    while url_str.upper().startswith("DATABASE_URL="):
        url_str = url_str[len("DATABASE_URL="):].strip().strip("'\"").strip()
    
    # Auto-prepend postgresql:// if user pasted without the scheme prefix
    if "://" not in url_str:
        url_str = f"postgresql://{url_str}"
    elif url_str.startswith("postgres://"):
        url_str = url_str.replace("postgres://", "postgresql://", 1)
    
    try:
        u = make_url(url_str)
        logger.info(f"Database target: {u.host}:{u.port}/{u.database} (user: {u.username})")
        return url_str
    except Exception:
        pass

    try:
        proto, rest = url_str.split("://", 1)
        slash_pos = rest.find("/")
        path_part = rest[slash_pos:] if slash_pos != -1 else "/postgres"
        netloc = rest[:slash_pos] if slash_pos != -1 else rest
        
        if "@" in netloc:
            userpass, hostport = netloc.rsplit("@", 1)
            if ":" in userpass:
                user, pwd = userpass.split(":", 1)
                user = quote_plus(unquote(user))
                pwd = quote_plus(unquote(pwd))
                userpass = f"{user}:{pwd}"
            else:
                userpass = quote_plus(unquote(userpass))
            netloc = f"{userpass}@{hostport}"
        
        sanitized = f"{proto}://{netloc}{path_part}"
        u = make_url(sanitized)
        logger.info(f"Database target (sanitized): {u.host}:{u.port}/{u.database} (user: {u.username})")
        return sanitized
    except Exception as e:
        logger.error(f"Could not parse DATABASE_URL ('{url_str[:25]}...'): {e}")
    
    return url_str

DEFAULT_SUPABASE_URL = "postgresql://postgres.fwyoktxjfuhbrruvyzkf:Tipsgalwar%40@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
raw_database_url = sanitize_db_url(_env_or_config("DATABASE_URL", DEFAULT_SUPABASE_URL))
db_type = _env_or_config("DATABASE_TYPE", "postgresql").lower()

if raw_database_url:
    DATABASE_URL = raw_database_url
else:
    postgres_host = _env_or_config("POSTGRES_HOST", "aws-0-ap-southeast-1.pooler.supabase.com").strip()
    postgres_port = int(_env_or_config("POSTGRES_PORT", 6543))
    postgres_db = _env_or_config("POSTGRES_DB", "postgres").strip()
    postgres_user = _env_or_config("POSTGRES_USER", "postgres.fwyoktxjfuhbrruvyzkf").strip()
    postgres_password = _env_or_config("POSTGRES_PASSWORD", "Tipsgalwar@").strip()

    DATABASE_URL = (
        f"postgresql://{postgres_user}:{quote_plus(postgres_password)}@{postgres_host}:{postgres_port}/{postgres_db}"
    )

if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"sslmode": "require"} if "sslmode" not in DATABASE_URL else {},
    )

# Setup SessionLocal factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes the database schema in the configured Postgres database."""
    Base.metadata.create_all(bind=engine)
