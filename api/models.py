import time
import uuid
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def now():
    return int(time.time())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    phone_key: Mapped[str] = mapped_column(String(64), unique=True)
    phone_encrypted: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default='citizen')
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    consent_version: Mapped[str] = mapped_column(String(40), default='pilot-v1')
    consent_at: Mapped[int] = mapped_column(Integer, default=now)


class Challenge(Base):
    __tablename__ = 'otp_challenges'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    phone_key: Mapped[str] = mapped_column(String(64), index=True)
    phone_encrypted: Mapped[str] = mapped_column(Text)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[int] = mapped_column(Integer)


class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[int] = mapped_column(Integer)


class Media(Base):
    __tablename__ = 'media'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    upload_key: Mapped[str] = mapped_column(String(36))
    report_id: Mapped[str | None] = mapped_column(ForeignKey('observations.id'), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(12))
    mime: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    __table_args__ = (UniqueConstraint('owner_id', 'upload_key'),)


class Incident(Base):
    __tablename__ = 'incidents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    category: Mapped[str] = mapped_column(String(32))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=now, index=True)
    first_received_at: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint('(latitude IS NULL) = (longitude IS NULL)', name='paired_coordinates'),
        CheckConstraint('NOT location_verified OR latitude IS NOT NULL', name='verified_has_point'),
        CheckConstraint('latitude BETWEEN -90 AND 90', name='incident_lat_range'),
        CheckConstraint('longitude BETWEEN -180 AND 180', name='incident_lon_range'),
    )


class Observation(Base):
    __tablename__ = 'observations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(String(500))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_source: Mapped[str] = mapped_column(String(16))
    device_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey('incidents.id'), nullable=True, index=True)
    response: Mapped[str] = mapped_column(Text, default='')
    received_at: Mapped[int] = mapped_column(Integer, default=now, index=True)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint('author_id', 'event_id'),)


class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey('observations.id'), nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(Text)
    details: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class Outbox(Base):
    __tablename__ = 'outbox'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey('incidents.id'), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[int] = mapped_column(Integer, default=now)
    external_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
