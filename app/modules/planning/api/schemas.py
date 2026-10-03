"""Schematy Pydantic modułu Planowanie i Dostępność (sekcja 5.10)."""
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator


class AvailabilityRuleRequest(BaseModel):
    dayOfWeek: int = Field(ge=0, le=6)
    startTime: time
    endTime: time
    validFrom: date
    validUntil: date | None = None


class SetAvailabilityRequest(BaseModel):
    rules: list[AvailabilityRuleRequest] = Field(min_length=1)


class SetAvailabilityResponse(BaseModel):
    scheduleId: uuid.UUID
    generatedSlots: int
    horizon: str


class SlotResponse(BaseModel):
    slotId: uuid.UUID
    status: str


class PublicSlotItem(BaseModel):
    slotId: uuid.UUID
    startTime: datetime
    durationMinutes: int


class PublicSlotsResponse(BaseModel):
    tutorId: uuid.UUID
    slots: list[PublicSlotItem]
