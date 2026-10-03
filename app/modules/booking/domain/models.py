"""
Modele ORM modułu Rezerwacje i Płatności (specyfikacja, sekcja 6.12).

BookingStatus (sekcja 6.6.4) - siedem stanów cyklu życia rezerwacji:
PENDING_PAYMENT, CONFIRMED, COMPLETED, EXPIRED, CANCELLED_BY_STUDENT,
CANCELLED_BY_TUTOR, REFUND_PENDING.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BOOLEAN,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy import JSON as SA_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import GUID, AwareDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


BookingStatus = Enum(
    "PENDING_PAYMENT", "CONFIRMED", "COMPLETED", "EXPIRED",
    "CANCELLED_BY_STUDENT", "CANCELLED_BY_TUTOR", "REFUND_PENDING",
    name="booking_status",
)

PaymentStatus = Enum("PENDING", "SUCCEEDED", "FAILED", name="payment_status")

RefundStatus = Enum("PENDING", "SUCCEEDED", "FAILED", name="refund_status")


class Booking(Base):
    """Encja centralna modułu - rezerwacja sesji korepetycji (UC-R01)."""

    __tablename__ = "bookings"
    __table_args__ = (
        Index("idx_bookings_student", "student_id"),
        Index("idx_bookings_tutor", "tutor_id"),
        Index("idx_bookings_status_expires", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    tutor_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    slot_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    status: Mapped[str] = mapped_column(BookingStatus, nullable=False, default="PENDING_PAYMENT")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PLN")
    expires_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    payments: Mapped[list["Payment"]] = relationship(back_populates="booking")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="booking")
    cancellation: Mapped["Cancellation | None"] = relationship(back_populates="booking", uselist=False)


class Payment(Base):
    """Próba pobrania płatności za rezerwację (UC-R02)."""

    __tablename__ = "payments"
    __table_args__ = (Index("idx_payments_booking", "booking_id"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(PaymentStatus, nullable=False, default="PENDING")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    method_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)

    booking: Mapped["Booking"] = relationship(back_populates="payments")


class Refund(Base):
    """Zwrot środków (UC-R03), z licznikiem prób do mechanizmu ponowień w adapterze płatniczym."""

    __tablename__ = "refunds"
    __table_args__ = (Index("idx_refunds_status_retry", "status", "retry_count"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("payments.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(RefundStatus, nullable=False, default="PENDING")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)

    booking: Mapped["Booking"] = relationship(back_populates="refunds")


class Cancellation(Base):
    """Anulowanie rezerwacji - jedna rezerwacja = jedno anulowanie (UNIQUE booking_id)."""

    __tablename__ = "cancellations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    cancelled_by: Mapped[str] = mapped_column(String(16), nullable=False)  # 'STUDENT' | 'TUTOR' | 'SYSTEM'
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)

    booking: Mapped["Booking"] = relationship(back_populates="cancellation")


class BookingOutboxEvent(Base):
    """Transactional Outbox modułu Rezerwacji (domain_events - sekcja 6.12)."""

    __tablename__ = "booking_domain_events"
    __table_args__ = (Index("idx_booking_outbox_unpublished", "published", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(SA_JSON, nullable=False)
    published: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    occurred_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
