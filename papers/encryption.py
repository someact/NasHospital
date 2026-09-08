import base64
import os
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken


def get_fernet():
    """Initializes and returns a Fernet cipher instance using MASTER_ENCRYPTION_KEY."""
    import hashlib
    raw_key = getattr(settings, 'MASTER_ENCRYPTION_KEY', None)
    if not raw_key:
        if not getattr(settings, 'DEBUG', True):
            from django.core.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured("MASTER_ENCRYPTION_KEY is required in production environment.")
        raw_key = 'L0KcPXqjlecnWbSoGJKb_fw0pKT2M4MBj4tDWdIcFxU='
    if isinstance(raw_key, str):
        raw_key = raw_key.encode('utf-8')
    try:
        return Fernet(raw_key)
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
        return Fernet(derived)


def is_encrypted(data: bytes) -> bool:
    """Checks whether the byte string is likely Fernet encrypted ciphertext."""
    if not data or len(data) < 16:
        return False
    # Fernet tokens start with base64 urlsafe encoded prefix 'gAAAAA'
    return data.startswith(b'gAAAAA')


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypts raw plaintext bytes using Fernet AES-128-CBC + HMAC-SHA256."""
    if not data:
        return b''
    if is_encrypted(data):
        return data  # Idempotent: do not re-encrypt
    fernet = get_fernet()
    return fernet.encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypts Fernet ciphertext back to plaintext. Falls back gracefully for legacy unencrypted data."""
    if not data:
        return b''
    if not is_encrypted(data):
        # Legacy or plaintext bytes
        return data
    fernet = get_fernet()
    try:
        return fernet.decrypt(data)
    except InvalidToken:
        # Fallback if decryption token doesn't match
        return data
