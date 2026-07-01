"""
Fernet symmetric encryption for Plaid access tokens stored in SQLite.
The encryption key lives only in the ENCRYPTION_KEY env var / Replit Secret.
Without the key, stored tokens are unreadable.
"""

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


def _cipher() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Run python scripts/generate_key.py "
            "and add the result to Replit Secrets."
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt token — ENCRYPTION_KEY may have changed.") from exc
