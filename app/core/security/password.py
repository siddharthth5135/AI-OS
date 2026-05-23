import re
import bcrypt

# Module-level dummy hash for timing-attack safety during login
# We use a pre-computed hash to avoid overhead on every import, but still provide timing safety
_dummy_hash = bcrypt.hashpw(b"DummyCheck1!", bcrypt.gensalt(rounds=12)).decode("utf-8")


def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt (rounds=12).
    """
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def validate_password_strength(password: str) -> None:
    """
    Validates that a password meets complexity requirements.
    Raises ValueError if requirements are not met.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if len(password) > 72:
        raise ValueError("Password cannot be longer than 72 characters (bcrypt limit)")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")


def get_dummy_hash() -> str:
    """
    Returns the module-level dummy hash for timing safety.
    """
    return _dummy_hash
