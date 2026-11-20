"""Encryption for broker secrets. If you already have this code in another
file, keep that file and change the imports instead of duplicating it."""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings


def _legacy_key() -> Fernet:
    digest = hashlib.sha256(
        ("broker-token:" + settings.jwt_secret_key).encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@lru_cache
def _fernet() -> MultiFernet:
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
        raise ValueError("Stored broker secret cannot be decrypted")(exc)


def reencrypt_secret(ciphertext: str) -> str:
    return _fernet().rotate(ciphertext.encode("utf-8")).decode("utf-8")
