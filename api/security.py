import base64
import hashlib
import hmac
import re
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select
from .db import lock_key
from .models import RateBucket, now


def digest(settings, value):
    return hmac.new(settings.secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def cipher(settings):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.secret.encode()).digest()))


def normalize_phone(value):
    value = re.sub(r'[\s()\-]', '', value)
    if value.startswith('8') and len(value) == 11:
        value = '+7' + value[1:]
    if not re.fullmatch(r'\+7[67]\d{9}', value):
        raise HTTPException(422, 'Введите мобильный номер Казахстана в формате +7 7XX XXX XX XX')
    return value


def limit(db, settings, subject, maximum, seconds):
    stamp = now()
    key = digest(settings, subject) + ':' + str(stamp // seconds)
    lock_key(db, key)
    row = db.get(RateBucket, key)
    if row is None:
        row = RateBucket(id=key, count=0, expires_at=stamp + seconds)
        db.add(row)
    if row.count >= maximum:
        db.commit()
        raise HTTPException(429, 'Слишком много попыток. Попробуйте позже.', headers={'Retry-After': str(seconds)})
    row.count += 1
    db.flush()
