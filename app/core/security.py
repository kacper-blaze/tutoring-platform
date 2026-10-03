"""
Narzędzia bezpieczeństwa: hashowanie haseł (bcrypt) oraz tokeny JWT.

Zgodnie ze specyfikacją (sekcja 3.8 - user_accounts.password_hash,
sekcja 3.9 - konwencje wspólne API):
  - hasła są hashowane algorytmem bcrypt,
  - access token przesyłany jest w nagłówku Authorization: Bearer,
  - refresh token przesyłany jest wyłącznie w ciele żądania POST /auth/refresh.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Hasła ------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


# --- Access token (JWT) -------------------------------------------------

def create_access_token(subject: str, role: str) -> str:
    """Tworzy krótkotrwały access token JWT (domyślnie 15 min - sekcja 3.9)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("TOKEN_INVALID_OR_EXPIRED") from exc
    if payload.get("type") != "access":
        raise ValueError("TOKEN_WRONG_TYPE")
    return payload


# --- Refresh token (losowy, opaque - przechowywany jako hash w DB) -----

def generate_refresh_token() -> str:
    """Losowy, nieprzewidywalny token (nie JWT) - por. tabela refresh_tokens."""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """SHA-256 tokenu do przechowania w refresh_tokens.token_hash (append-only)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- Tokeny jednorazowe (aktywacja konta, reset hasła) ------------------

def generate_one_time_token() -> str:
    return secrets.token_urlsafe(32)
