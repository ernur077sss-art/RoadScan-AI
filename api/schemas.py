from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from .passwords import is_pin

Category = Literal['pothole', 'surface', 'manhole', 'other']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)


class PhoneRequest(Strict):
    phone: str = Field(max_length=30)
    consent: Literal[True]


class VerifyRequest(Strict):
    challenge_id: UUID
    code: str = Field(pattern=r'^\d{6}$')


class PasswordLogin(Strict):
    # Whitespace is part of a password; never silently trim it.
    model_config = ConfigDict(str_strip_whitespace=False)
    phone: str = Field(max_length=30)
    password: str = Field(min_length=1, max_length=128)


class PasswordRegistration(PasswordLogin):
    password: str = Field(min_length=4, max_length=128)
    consent: Literal[True]

    @field_validator('password')
    @classmethod
    def valid_password(cls, value):
        if not is_pin(value) and len(value) < 15:
            raise ValueError('Используйте PIN из 4 цифр или пароль от 15 символов.')
        return value


class Coordinates(Strict):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode='after')
    def pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Укажите обе координаты')
        return self


class ReportRequest(Coordinates):
    event_id: UUID
    category: Category
    description: str = Field(min_length=5, max_length=3000)
    address: str = Field(min_length=3, max_length=500)
    location_source: Literal['manual', 'gps', 'unknown'] = 'unknown'
    device_accuracy: float | None = Field(default=None, ge=0, le=100000)
    media_ids: list[UUID] = Field(min_length=1, max_length=4)

    @model_validator(mode='after')
    def consistent(self):
        if len(set(self.media_ids)) != len(self.media_ids):
            raise ValueError('Повторяющиеся вложения')
        if self.location_source != 'unknown' and self.latitude is None:
            raise ValueError('Для выбранного источника необходима точка')
        if self.latitude is not None and self.location_source == 'unknown':
            raise ValueError('Укажите источник точки')
        return self


class Decision(Coordinates):
    version: int = Field(ge=1)
    status: Literal['confirmed', 'needs_info', 'rejected']
    note: str = Field(min_length=3, max_length=3000)
    incident_id: UUID | None = None
    location_verified: bool = False

    @model_validator(mode='after')
    def location(self):
        if self.location_verified and self.latitude is None:
            raise ValueError('Для проверки местоположения укажите точку')
        if self.status != 'confirmed' and (self.incident_id or self.location_verified):
            raise ValueError('Связь с дефектом доступна при подтверждении')
        return self


class Clarification(Coordinates):
    version: int = Field(ge=1)
    note: str = Field(min_length=3, max_length=3000)
    address: str = Field(min_length=3, max_length=500)


class RoleRequest(Strict):
    role: Literal['citizen', 'inspector', 'admin']


class LocationUpdate(Coordinates):
    version: int = Field(ge=1)
    location_verified: bool
    note: str = Field(min_length=3, max_length=3000)

    @model_validator(mode='after')
    def valid_location(self):
        if self.location_verified and self.latitude is None:
            raise ValueError('Нельзя подтвердить отсутствующую точку')
        return self
