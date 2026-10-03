"""Repozytoria modułu Rezerwacje i Płatności (sekcja 6.9/6.12)."""
import uuid
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.booking.domain.models import Booking, Cancellation, Payment, Refund


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, booking: Booking) -> Booking:
        self.db.add(booking)
        self.db.flush()
        return booking

    def find_by_id(self, booking_id: uuid.UUID) -> Booking | None:
        return self.db.get(Booking, booking_id)

    def list_for_user(
        self, user_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None, status: str | None
    ) -> list[Booking]:
        stmt = select(Booking).where(or_(Booking.student_id == user_id, Booking.tutor_id == user_id))
        if status:
            stmt = stmt.where(Booking.status == status)
        if date_from:
            stmt = stmt.where(Booking.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Booking.created_at <= date_to)
        stmt = stmt.order_by(Booking.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def find_expired_pending(self, now: datetime) -> list[Booking]:
        stmt = select(Booking).where(Booking.status == "PENDING_PAYMENT", Booking.expires_at < now)
        return list(self.db.scalars(stmt).all())


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def find_by_idempotency_key(self, key: str) -> Payment | None:
        stmt = select(Payment).where(Payment.idempotency_key == key)
        return self.db.scalar(stmt)


class RefundRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, refund: Refund) -> Refund:
        self.db.add(refund)
        self.db.flush()
        return refund


class CancellationRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, cancellation: Cancellation) -> Cancellation:
        self.db.add(cancellation)
        self.db.flush()
        return cancellation
