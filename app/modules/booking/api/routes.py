"""
Router modułu Rezerwacje i Płatności (sekcja 6.13).

Wszystkie endpointy wymagają JWT; autoryzacja na poziomie zasobu
(uczeń widzi/anuluje wyłącznie swoje rezerwacje).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.booking.api.schemas import (
    BookingResponse,
    CancelBookingRequest,
    CancelBookingResponse,
    CreateBookingRequest,
    MoneyResponse,
    PayBookingRequest,
    RefundResponse,
    TransactionHistoryResponse,
    TransactionItem,
)
from app.modules.booking.application.booking_service import BookingService
from app.modules.users.api.dependencies import require_role
from app.modules.users.domain.models import UserAccount

router = APIRouter(prefix="/bookings", tags=["Rezerwacje i Płatności"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: CreateBookingRequest,
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-R01 - utworzenie rezerwacji (status PENDING_PAYMENT, wygasa po 15 min)."""
    booking = BookingService(db).create_booking(student.id, payload.slotId)
    return BookingResponse(
        bookingId=booking.id,
        status=booking.status,
        amount=MoneyResponse(value=float(booking.amount), currency=booking.currency),
        expiresAt=booking.expires_at,
    )


@router.post("/{booking_id}/payments", response_model=BookingResponse)
def pay_booking(
    booking_id: uuid.UUID,
    payload: PayBookingRequest,
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-R02 - realizacja płatności (zasymulowana synchronicznie; idempotentna po idempotencyKey)."""
    booking = BookingService(db).pay_booking(
        student.id, booking_id, payload.idempotencyKey, str(payload.paymentMethodId) if payload.paymentMethodId else None
    )
    return BookingResponse(
        bookingId=booking.id,
        status=booking.status,
        amount=MoneyResponse(value=float(booking.amount), currency=booking.currency),
        expiresAt=booking.expires_at,
    )


@router.delete("/{booking_id}", response_model=CancelBookingResponse)
def cancel_booking(
    booking_id: uuid.UUID,
    payload: CancelBookingRequest,
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-R05 - odwołanie rezerwacji przez ucznia (RB5: zawsze inicjuje pełny zwrot, jeśli opłacona)."""
    booking, refund = BookingService(db).cancel_booking(student.id, booking_id, payload.reason)
    refund_dto = None
    if refund is not None:
        refund_dto = RefundResponse(
            refundId=refund.id,
            amount=MoneyResponse(value=float(refund.amount), currency=booking.currency),
            status=refund.status,
        )
    return CancelBookingResponse(bookingId=booking.id, status=booking.status, refund=refund_dto)


@router.get("/transactions", response_model=TransactionHistoryResponse)
def list_transactions(
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    booking_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_role("STUDENT", "TUTOR")),
):
    """UC-R06 - historia transakcji bieżącego użytkownika (ucznia lub korepetytora)."""
    bookings = BookingService(db).list_transactions(user.id, date_from, date_to, booking_status)
    return TransactionHistoryResponse(
        items=[
            TransactionItem(
                bookingId=b.id,
                status=b.status,
                amount=MoneyResponse(value=float(b.amount), currency=b.currency),
                createdAt=b.created_at,
            )
            for b in bookings
        ]
    )


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_role("STUDENT", "TUTOR")),
):
    booking = BookingService(db).get_booking_for_user(user.id, booking_id)
    return BookingResponse(
        bookingId=booking.id,
        status=booking.status,
        amount=MoneyResponse(value=float(booking.amount), currency=booking.currency),
        expiresAt=booking.expires_at,
    )
