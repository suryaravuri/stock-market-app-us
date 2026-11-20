"""Symmetric encryption for broker secrets and access tokens stored in the database.

The primary key is BROKER_ENCRYPTION_KEY (from Secret Manager / .env), independent
of JWT_SECRET_KEY. The old JWT-derived key is kept as a decrypt-only fallback
until existing rows are re-encrypted with reencrypt_secret().
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings


def _legacy_key() -> Fernet:
    # Old JWT-derived key: decrypt-only, remove after migration
    digest = hashlib.sha256(
        ("broker-token:" + settings.jwt_secret_key).encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@lru_cache
def _fernet() -> MultiFernet:
    # First key encrypts; all keys are tried when decrypting
    keys = [Fernet(settings.broker_encryption_key)]
    if settings.legacy_jwt_key_fallback:
        keys.append(_legacy_key())
    return MultiFernet(keys)


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored broker secret cannot be decrypted") from exc


def reencrypt_secret(ciphertext: str) -> str:
    # Re-encrypts old values with the current primary key
    return _fernet().rotate(ciphertext.encode("utf-8")).decode("utf-8")


# Old names, still used by zerodha_auth_service.py
encrypt_token = encrypt_secret
decrypt_token = decrypt_secret