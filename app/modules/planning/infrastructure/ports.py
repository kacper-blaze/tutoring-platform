"""
SchedulingPort - jedyny dozwolony punkt integracji modułu Rezerwacji
z modułem Planowania (sekcja 6.6.5, "moduł Rezerwacji jest odbiorcą
informacji o dostępności terminów przez SchedulingPort").

Moduł Rezerwacji NIGDY nie modyfikuje bezpośrednio tabeli time_slots -
wyłącznie przez metody tego portu, które hermetyzują optimistic locking
(RB3 z modułu Planowania).
"""
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.planning.infrastructure.repositories import TimeSlotRepository


@dataclass
class SlotView:
    slot_id: uuid.UUID
    tutor_id: uuid.UUID
    start_time: datetime
    duration_minutes: int
    status: str


class SchedulingPort:
    def __init__(self, db: Session):
        self.db = db
        self._slots = TimeSlotRepository(db)

    def get_slot(self, slot_id: uuid.UUID) -> SlotView | None:
        slot = self._slots.find_by_id(slot_id)
        if slot is None:
            return None
        return SlotView(
            slot_id=slot.id,
            tutor_id=slot.schedule.tutor_id,
            start_time=slot.start_time,
            duration_minutes=slot.duration_minutes,
            status=slot.status,
        )

    def reserve_temporarily(self, slot_id: uuid.UUID, booking_id: uuid.UUID) -> bool:
        """UC-R01: rezerwacja wstępna (PENDING_PAYMENT) blokuje termin (TEMPORARILY_BLOCKED)."""
        return self._slots.try_reserve(slot_id, "AVAILABLE", "TEMPORARILY_BLOCKED", booking_id)

    def confirm_booking(self, slot_id: uuid.UUID, booking_id: uuid.UUID) -> bool:
        """RB3: zaakceptowana/opłacona rezerwacja blokuje termin trwale (BOOKED)."""
        return self._slots.try_reserve(slot_id, "TEMPORARILY_BLOCKED", "BOOKED", booking_id)

    def release_slot(self, slot_id: uuid.UUID) -> bool:
        """Zwolnienie terminu przy wygaśnięciu/anulowaniu rezerwacji -> z powrotem AVAILABLE."""
        slot = self._slots.find_by_id(slot_id)
        if slot is None:
            return False
        slot.status = "AVAILABLE"
        slot.booking_id = None
        slot.locked_until = None
        self.db.flush()
        return True

    def mark_cancelled(self, slot_id: uuid.UUID) -> bool:
        """Anulowanie po stronie korepetytora - termin nie wraca do puli (CANCELLED)."""
        slot = self._slots.find_by_id(slot_id)
        if slot is None:
            return False
        slot.status = "CANCELLED"
        self.db.flush()
        return True
