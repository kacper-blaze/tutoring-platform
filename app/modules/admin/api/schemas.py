"""Schematy Pydantic modułu Administracja i System (sekcja 7.10)."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EditUserRequest(BaseModel):
    email: str | None = None
    role: Literal["STUDENT", "TUTOR", "ADMIN"] | None = None
    reason: str = Field(min_length=3, max_length=500)


class EditUserResponse(BaseModel):
    userId: uuid.UUID
    email: str
    role: str
    status: str


class BlockUserRequest(BaseModel):
    type: Literal["PERMANENT", "TEMPORARY"]
    reason: str = Field(min_length=3, max_length=500)
    suspendedUntil: datetime | None = None
    notifyUser: bool = True


class CascadeEffects(BaseModel):
    cancelledBookings: int = 0
    revokedTokens: int = 0


class BlockUserResponse(BaseModel):
    userId: uuid.UUID
    status: str
    blockedAt: datetime
    blockedBy: uuid.UUID
    cascadeEffects: CascadeEffects


class ModerateReviewRequest(BaseModel):
    action: Literal["APPROVE", "HIDE", "DELETE"]
    reason: str | None = Field(default=None, max_length=500)
    notifyAuthor: bool = True


class ModerateReviewResponse(BaseModel):
    reviewId: uuid.UUID
    newStatus: str
    tutorAverageRecalculated: bool = True
    newTutorAverage: float


class CreateReportRequest(BaseModel):
    entityType: Literal["USER", "REVIEW", "BOOKING", "OFFER"]
    entityId: uuid.UUID
    category: Literal["REGULATIONS_VIOLATION", "TECHNICAL_ISSUE", "FINANCIAL_DISPUTE", "INAPPROPRIATE_CONTENT", "OTHER"]
    description: str = Field(min_length=5, max_length=2000)


class ReportResponse(BaseModel):
    id: uuid.UUID
    reporterId: uuid.UUID = Field(validation_alias="reporter_id")
    reportedEntityType: str = Field(validation_alias="reported_entity_type")
    reportedEntityId: uuid.UUID = Field(validation_alias="reported_entity_id")
    category: str
    priority: str
    status: str
    description: str
    createdAt: datetime = Field(validation_alias="created_at")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ResolveReportRequest(BaseModel):
    action: Literal["ASSIGN", "RESOLVE", "REJECT"]
    resolution: str | None = Field(default=None, max_length=2000)
