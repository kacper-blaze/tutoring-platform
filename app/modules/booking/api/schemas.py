"""Schematy Pydantic modułu Rezerwacje i Płatności (sekcja 6.13)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateBookingRequest(BaseModel):
    slotId: uuid.UUID


class MoneyResponse(BaseModel):
    value: float
    currency: str = "PLN"


class BookingResponse(BaseModel):
    bookingId: uuid.UUID
    status: str
    amount: MoneyResponse
    expiresAt: datetime | None = None


class PayBookingRequest(BaseModel):
    paymentMethodId: uuid.UUID | None = None
    idempotencyKey: str = Field(min_length=4, max_length=128)


class RefundResponse(BaseModel):
    refundId: uuid.UUID
    amount: MoneyResponse
    status: str


class CancelBookingRequest(BaseModel):
    reason: str | None = None


class CancelBookingResponse(BaseModel):
    bookingId: uuid.UUID
    status: str
    refund: RefundResponse | None = None


class TransactionItem(BaseModel):
    bookingId: uuid.UUID
    status: str
    amount: MoneyResponse
    createdAt: datetime


class TransactionHistoryResponse(BaseModel):
    items: list[TransactionItem]
