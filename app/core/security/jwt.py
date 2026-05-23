import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, ExpiredSignatureError, jwt
from fastapi import HTTPException, status

from app.core.config.settings import settings


def create_access_token(user_id: str, role: str) -> str:
    """
    Creates a JWT access token.
    Payload: sub, role, type="access", exp, iat, jti
    """
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.jwt_access_expire_minutes)
    
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4())
    }
    
    return jwt.encode(
        payload, 
        settings.jwt_secret_key.get_secret_value(), 
        algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: str) -> str:
    """
    Creates a JWT refresh token.
    Payload: sub, type="refresh", exp, iat, jti
    """
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(days=settings.jwt_refresh_expire_days)
    
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4())
    }
    
    return jwt.encode(
        payload, 
        settings.jwt_secret_key.get_secret_value(), 
        algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes a JWT token.
    Raises ExpiredSignatureError or JWTError.
    """
    return jwt.decode(
        token, 
        settings.jwt_secret_key.get_secret_value(), 
        algorithms=[settings.jwt_algorithm]
    )
