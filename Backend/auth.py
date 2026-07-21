"""
Autenticación simple: hash de contraseñas (PBKDF2, sin dependencias externas) + tokens de
sesión opacos guardados en SQLite. No usa JWT a propósito, para no añadir dependencias nuevas.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

SESSION_DAYS = 30


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Devuelve (salt, hash). Si no se pasa salt, genera uno nuevo (para registro)."""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return salt, digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, computed = hash_password(password, salt)
    return secrets.compare_digest(computed, expected_hash)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def session_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()


def is_expired(expires_at_iso: str) -> bool:
    return datetime.fromisoformat(expires_at_iso) < datetime.now(timezone.utc)
