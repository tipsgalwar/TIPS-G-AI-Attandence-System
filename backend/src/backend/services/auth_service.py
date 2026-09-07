import bcrypt
from datetime import datetime, timedelta
from typing import Union, Any
import jwt
from src.config_loader import settings

SECRET_KEY = settings.system.get("jwt_secret", "supersecretkeychangeinproduction")
ALGORITHM = settings.system.get("jwt_algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = settings.system.get("access_token_expire_minutes", 1440)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hashes a plain password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def create_access_token(
    subject: Union[str, Any],
    role: str,
    expires_delta: timedelta = None,
    session_id: str = None,
) -> str:
    """Generates a JWT access token for a given user subject and role."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role
    }
    if session_id:
        to_encode["sid"] = session_id
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    Decodes the JWT access token.
    Returns the payload dict if valid, or raises PyJWTError.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return {}
