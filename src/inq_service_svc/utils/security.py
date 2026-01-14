from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from inq_service_svc import config

_logger = logging.getLogger(__name__)

# Module level CryptContext using bcrypt as required by the action item
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Raises ValueError for invalid inputs. Returns True when verified, False
    on mismatch or unexpected errors (errors are logged with exc_info).
    """
    if not isinstance(plain_password, str) or not plain_password:
        raise ValueError("plain_password must be a non-empty string")
    if not isinstance(hashed_password, str) or not hashed_password:
        raise ValueError("hashed_password must be a non-empty string")

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        _logger.error(e, exc_info=True)
        return False


def get_password_hash(password: str) -> str:
    """Return a secure hash for the provided password using bcrypt.

    Raises ValueError for invalid input. Unexpected errors are logged and re-raised.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    try:
        return pwd_context.hash(password)
    except Exception as e:
        _logger.error(e, exc_info=True)
        raise


def create_access_token(data: Dict[str, object], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token with expiration embedded.

    data must be a non-empty dict. Returns encoded JWT string.
    """
    if not isinstance(data, dict) or not data:
        raise ValueError("data must be a non-empty dict")

    to_encode = data.copy()
    try:
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta if expires_delta is not None else timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
        return encoded_jwt
    except Exception as e:
        _logger.error(e, exc_info=True)
        raise


def decode_access_token(token: str) -> Optional[Dict[str, object]]:
    """Decode a JWT and return the payload dict or None on failure/expiration.

    Safe for callers: returns None when token is invalid or expired.
    """
    if not isinstance(token, str) or not token:
        return None

    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return dict(payload)
    except ExpiredSignatureError as e:
        _logger.error(e, exc_info=True)
        return None
    except JWTError as e:
        _logger.error(e, exc_info=True)
        return None
    except Exception as e:
        _logger.error(e, exc_info=True)
        return None
