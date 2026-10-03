"""Schematy Pydantic modułu Katalog (sekcja 4.5.2)."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateOfferRequest(BaseModel):
    subject: str = Field(min_length=2, max_length=50)
    hourlyRate: float = Field(gt=0)


class OfferSummaryResponse(BaseModel):
    offerId: uuid.UUID
    tutorId: uuid.UUID
    subject: str
    hourlyRate: float
    tutorName: str
    avatarUrl: str | None
    averageRating: float
    reviewCount: int


class OfferSearchResponse(BaseModel):
    items: list[OfferSummaryResponse]
    total: int
    page: int
    pageSize: int


class OfferBrief(BaseModel):
    id: uuid.UUID
    subject: str
    hourlyRate: float


class TutorProfilePublicResponse(BaseModel):
    tutorId: uuid.UUID
    firstName: str
    lastName: str
    bio: str | None
    avatarUrl: str | None
    averageRating: float
    reviewCount: int
    offers: list[OfferBrief]


class CreateReviewRequest(BaseModel):
    tutorId: uuid.UUID
    lessonId: uuid.UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    id: uuid.UUID
    tutorId: uuid.UUID = Field(validation_alias="tutor_id")
    studentId: uuid.UUID = Field(validation_alias="student_id")
    rating: int
    comment: str | None
    status: str
    createdAt: datetime = Field(validation_alias="created_at")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int


class AddFavoriteRequest(BaseModel):
    tutorId: uuid.UUID


class FavoriteResponse(BaseModel):
    tutorId: uuid.UUID
    tutorName: str
    averageRating: float
