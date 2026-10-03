"""Repozytoria modułu Planowanie i Dostępność (sekcja 5.9)."""
import uuid
from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.planning.domain.models import Availability, Schedule, TimeSlot


class ScheduleRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_tutor(self, tutor_id: uuid.UUID) -> Schedule | None:
        stmt = select(Schedule).where(Schedule.tutor_id == tutor_id, Schedule.deleted_at.is_(None))
        return self.db.scalar(stmt)

    def get_or_create(self, tutor_id: uuid.UUID) -> Schedule:
        schedule = self.find_by_tutor(tutor_id)
        if schedule is None:
            schedule = Schedule(tutor_id=tutor_id)
            self.db.add(schedule)
            self.db.flush()
        return schedule

    def find_by_id(self, schedule_id: uuid.UUID) -> Schedule | None:
        return self.db.get(Schedule, schedule_id)


class AvailabilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def replace_rules(self, schedule_id: uuid.UUID, rules: list[dict]) -> list[Availability]:
        # Zastąpienie zestawu reguł (UC-P01/UC-P02): usuwamy stare, tworzymy nowe.
        existing = self.db.scalars(select(Availability).where(Availability.schedule_id == schedule_id)).all()
        for rule in existing:
            self.db.delete(rule)
        self.db.flush()

        created = []
        for rule in rules:
            availability = Availability(schedule_id=schedule_id, **rule)
            self.db.add(availability)
            created.append(availability)
        self.db.flush()
        return created

    def list_for_schedule(self, schedule_id: uuid.UUID) -> list[Availability]:
        stmt = select(Availability).where(Availability.schedule_id == schedule_id)
        return list(self.db.scalars(stmt).all())


class TimeSlotRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, slot: TimeSlot) -> TimeSlot:
        self.db.add(slot)
        self.db.flush()
        return slot

    def find_by_id(self, slot_id: uuid.UUID) -> TimeSlot | None:
        return self.db.get(TimeSlot, slot_id)

    def find_booked_conflicts(self, schedule_id: uuid.UUID, start: datetime, end: datetime) -> list[TimeSlot]:
        """RB2: sprawdza, czy w danym oknie istnieją sloty BOOKED, zanim grafik zostanie nadpisany."""
        stmt = select(TimeSlot).where(
            TimeSlot.schedule_id == schedule_id,
            TimeSlot.status == "BOOKED",
            TimeSlot.start_time >= start,
            TimeSlot.start_time < end,
        )
        return list(self.db.scalars(stmt).all())

    def list_public_slots(self, schedule_id: uuid.UUID, date_from: date, date_to: date) -> list[TimeSlot]:
        stmt = (
            select(TimeSlot)
            .where(
                TimeSlot.schedule_id == schedule_id,
                TimeSlot.status == "AVAILABLE",
                TimeSlot.start_time >= datetime.combine(date_from, datetime.min.time()),
                TimeSlot.start_time <= datetime.combine(date_to, datetime.max.time()),
            )
            .order_by(TimeSlot.start_time.asc())
        )
        return list(self.db.scalars(stmt).all())

    def try_reserve(
        self, slot_id: uuid.UUID, expected_status: str, new_status: str, booking_id: uuid.UUID | None = None
    ) -> bool:
        """
        Optimistic locking (sekcja 5, decyzja projektowa): atomowy UPDATE warunkowy
        `WHERE status = expected_status`. Jeśli 0 wierszy trafionych, ktoś inny
        zmienił stan w międzyczasie - zwracamy False zamiast rzucać wyjątek,
        żeby wywołujący (BookingService) mógł obsłużyć konflikt (409).
        """
        stmt = (
            update(TimeSlot)
            .where(TimeSlot.id == slot_id, TimeSlot.status == expected_status)
            .values(status=new_status, booking_id=booking_id)
        )
        result = self.db.execute(stmt)
        self.db.flush()
        return result.rowcount == 1
