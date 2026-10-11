"""Salted scrypt passwords; bounded memory/CPU for the small free API instance."""
import hashlib
import hmac
import secrets
from threading import BoundedSemaphore

from fastapi import HTTPException

# OWASP's 32 MiB profile. At most one expensive hash per API process at a time.
_slot = BoundedSemaphore(1)
_prefix = 'scrypt:32768:8:3'


def _derive(password, salt):
    if not _slot.acquire(blocking=False):
        raise HTTPException(429, 'Сервис входа занят. Повторите через несколько секунд.', headers={'Retry-After': '3'})
    try:
        return hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=3, maxmem=64 * 1024 * 1024, dklen=32)
    finally:
        _slot.release()


def hash_password(password):
    salt = secrets.token_bytes(16)
    return f'{_prefix}${salt.hex()}${_derive(password, salt).hex()}'


def verify_password(password, stored):
    # Missing / legacy accounts still incur the same hashing work.
    salt, expected, valid = b'roadscan-dummy-16', bytes(32), False
    if stored:
        try:
            profile, salt_hex, hash_hex = stored.split('$')
            parsed_salt, parsed_hash = bytes.fromhex(salt_hex), bytes.fromhex(hash_hex)
            if profile == _prefix and len(parsed_salt) == 16 and len(parsed_hash) == 32:
                salt, expected, valid = parsed_salt, parsed_hash, True
        except ValueError:
            pass
    return hmac.compare_digest(_derive(password, salt), expected) and valid
