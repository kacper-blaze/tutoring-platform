"""
Serwis aplikacyjny modułu Rezerwacje i Płatności (UC-R01 - UC-R06).

Orkiestruje operacje biznesowe, komunikując się z modułem Planowania
wyłącznie przez SchedulingPort (RB1, RB3) i z modułem Użytkowników przez
UserPort. Płatności przechodzą przez PaymentGatewayAdapter.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.modules.booking.domain.models import Booking, BookingOutboxEvent, Cancellation, Payment, Refund
from app.modules.booking.infrastructure.ports import PaymentGatewayAdapter, UserPort
from app.modules.booking.infrastructure.repositories import (
    BookingRepository,
    CancellationRepository,
    PaymentRepository,
    RefundRepository,
)
from app.modules.planning.infrastructure.ports import SchedulingPort

# UC-R01: rezerwacja PENDING_PAYMENT wygasa po 15 minutach (timer(15min) / releaseSlot()).
BOOKING_EXPIRY_MINUTES = 15


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.bookings = BookingRepository(db)
        self.payments = PaymentRepository(db)
        self.refunds = RefundRepository(db)
        self.cancellations = CancellationRepository(db)
        self.scheduling = SchedulingPort(db)
        self.users = UserPort(db)
        self.gateway = PaymentGatewayAdapter()

    def _emit(self, booking_id: uuid.UUID, event_type: str, payload: dict) -> None:
        self.db.add(BookingOutboxEvent(aggregate_id=booking_id, event_type=event_type, payload=payload))

    # --- UC-R01: rezerwacja sesji korepetycji ---------------------------------

    def create_booking(self, student_id: uuid.UUID, slot_id: uuid.UUID) -> Booking:
        if not self.users.is_account_active(student_id):
            raise ForbiddenError("Konto zawieszone lub zablokowane", error_code="ACCOUNT_SUSPENDED")

        slot = self.scheduling.get_slot(slot_id)
        if slot is None or slot.status != "AVAILABLE":
            raise ConflictError("Wybrany termin jest niedostępny", error_code="SLOT_UNAVAILABLE")

        # Cena za termin - w pełnej wersji pobierana z aktualnej oferty korepetytora
        # (RB4: cena obowiązuje w momencie rezerwacji). Uproszczenie: stawka domyślna
        # 100.00 PLN/60 min, proporcjonalna do czasu trwania slotu.
        amount = round(100.0 * (slot.duration_minutes / 60), 2)

        booking = Booking(
            student_id=student_id,
            tutor_id=slot.tutor_id,
            slot_id=slot_id,
            status="PENDING_PAYMENT",
            amount=amount,
            currency="PLN",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=BOOKING_EXPIRY_MINUTES),
        )
        self.bookings.save(booking)

        # RB3 (wstępnie): natychmiastowa blokada terminu na czas płatności.
        reserved = self.scheduling.reserve_temporarily(slot_id, booking.id)
        if not reserved:
            raise ConflictError("Termin został właśnie zarezerwowany przez inną osobę", error_code="SLOT_UNAVAILABLE")

        self._emit(booking.id, "BookingCreatedEvent", {"bookingId": str(booking.id), "slotId": str(slot_id)})
        self.db.commit()
        self.db.refresh(booking)
        return booking

    # --- UC-R02: realizacja płatności (zasymulowana synchronicznie) ------------

    def pay_booking(self, student_id: uuid.UUID, booking_id: uuid.UUID, idempotency_key: str, method_token: str | None) -> Booking:
        existing_payment = self.payments.find_by_idempotency_key(idempotency_key)
        if existing_payment is not None:
            return self.bookings.find_by_id(existing_payment.booking_id)  # idempotencja

        booking = self.bookings.find_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Rezerwacja nie istnieje", error_code="BOOKING_NOT_FOUND")
        if booking.student_id != student_id:
            raise ForbiddenError("Rezerwacja nie należy do tego ucznia", error_code="NOT_OWNER")
        if booking.status != "PENDING_PAYMENT":
            raise ConflictError("Rezerwacja nie oczekuje na płatność", error_code="BOOKING_EXPIRED")
        if booking.expires_at and booking.expires_at < datetime.now(timezone.utc):
            self._expire_booking(booking)
            self.db.commit()
            raise ConflictError("Czas na opłacenie rezerwacji upłynął", error_code="BOOKING_EXPIRED")

        result = self.gateway.charge(float(booking.amount), booking.currency, method_token, idempotency_key)
        payment = Payment(
            booking_id=booking.id,
            external_id=result.external_id,
            status="SUCCEEDED" if result.succeeded else "FAILED",
            amount=booking.amount,
            method_token=method_token,
            idempotency_key=idempotency_key,
        )
        self.payments.save(payment)

        if result.succeeded:
            confirmed = self.scheduling.confirm_booking(booking.slot_id, booking.id)
            if not confirmed:
                raise ConflictError(
                    "Termin nie jest już dostępny (rezerwacja równoległa)",
                    error_code="SLOT_NO_LONGER_AVAILABLE",
                )
            booking.status = "CONFIRMED"
            self._emit(booking.id, "BookingConfirmedEvent", {"bookingId": str(booking.id)})
        else:
            self.scheduling.release_slot(booking.slot_id)
            booking.status = "EXPIRED"

        self.db.commit()
        self.db.refresh(booking)
        return booking

    def _expire_booking(self, booking: Booking) -> None:
        booking.status = "EXPIRED"
        self.scheduling.release_slot(booking.slot_id)
        self._emit(booking.id, "BookingExpiredEvent", {"bookingId": str(booking.id)})

    def expire_stale_bookings(self) -> int:
        """Odpowiednik wyzwalacza timer(15min) - w produkcji wywoływane przez scheduler/worker."""
        now = datetime.now(timezone.utc)
        expired = self.bookings.find_expired_pending(now)
        for booking in expired:
            self._expire_booking(booking)
        self.db.commit()
        return len(expired)

    # --- UC-R05: odwołanie rezerwacji przez ucznia ------------------------------

    def cancel_booking(self, student_id: uuid.UUID, booking_id: uuid.UUID, reason: str | None) -> tuple[Booking, Refund | None]:
        booking = self.bookings.find_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Rezerwacja nie istnieje", error_code="BOOKING_NOT_FOUND")
        if booking.student_id != student_id:
            raise ForbiddenError("Rezerwacja nie należy do tego ucznia", error_code="NOT_OWNER")
        if booking.status in ("CANCELLED_BY_STUDENT", "CANCELLED_BY_TUTOR", "COMPLETED", "EXPIRED"):
            raise ConflictError("Rezerwacja już zakończona lub anulowana", error_code="BOOKING_ALREADY_STARTED")

        was_paid = booking.status == "CONFIRMED"
        booking.status = "CANCELLED_BY_STUDENT"
        self.scheduling.release_slot(booking.slot_id)
        self.cancellations.save(
            Cancellation(booking_id=booking.id, cancelled_by="STUDENT", comment=reason)
        )

        refund = None
        if was_paid:
            # RB5: odrzucenie/anulowanie zawsze inicjuje pełny zwrot środków.
            result = self.gateway.refund(float(booking.amount), None)
            refund = Refund(
                booking_id=booking.id,
                amount=booking.amount,
                status="SUCCEEDED" if result.succeeded else "PENDING",
                reason=reason,
            )
            self.refunds.save(refund)
            if not result.succeeded:
                booking.status = "REFUND_PENDING"

        self._emit(booking.id, "BookingCancelledEvent", {"bookingId": str(booking.id), "by": "STUDENT"})
        self.db.commit()
        self.db.refresh(booking)
        return booking, refund

    # --- UC-R06: historia transakcji --------------------------------------------

    def list_transactions(
        self, user_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None, status: str | None
    ) -> list[Booking]:
        return self.bookings.list_for_user(user_id, date_from, date_to, status)

    def get_booking_for_user(self, user_id: uuid.UUID, booking_id: uuid.UUID) -> Booking:
        booking = self.bookings.find_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Rezerwacja nie istnieje", error_code="BOOKING_NOT_FOUND")
        if user_id not in (booking.student_id, booking.tutor_id):
            raise ForbiddenError("Brak dostępu do tej rezerwacji", error_code="NOT_OWNER")
        return booking
