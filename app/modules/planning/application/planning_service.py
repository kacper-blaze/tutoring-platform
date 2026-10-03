"""
Serwis aplikacyjny modułu Planowanie i Dostępność.

Implementuje UC-P01/UC-P02 (definiowanie/modyfikacja grafiku z
materializacją slotów) oraz UC-P03 (ręczne blokowanie terminu).
Reguły biznesowe: RB1 (brak konfliktów), RB2 (ochrona BOOKED), RB6
(format czasowy sesji).
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.modules.planning.domain.models import TimeSlot
from app.modules.planning.infrastructure.repositories import (
    AvailabilityRepository,
    ScheduleRepository,
    TimeSlotRepository,
)

# Horyzont materializacji slotów po zapisaniu grafiku (decyzja projektowa, sekcja 5).
MATERIALIZATION_HORIZON_DAYS = 28
DEFAULT_SLOT_DURATION_MINUTES = 60


class PlanningService:
    def __init__(self, db: Session):
        self.db = db
        self.schedules = ScheduleRepository(db)
        self.availabilities = AvailabilityRepository(db)
        self.slots = TimeSlotRepository(db)

    # --- UC-P01/UC-P02: definiowanie i modyfikacja grafiku ------------------

    def set_availability(self, tutor_id: uuid.UUID, rules: list[dict]) -> dict:
        self._validate_no_overlaps(rules)

        schedule = self.schedules.get_or_create(tutor_id)
        horizon_start = datetime.now(timezone.utc)
        horizon_end = horizon_start + timedelta(days=MATERIALIZATION_HORIZON_DAYS)

        # RB2: modyfikacja grafiku nie może naruszać już zmaterializowanych slotów BOOKED.
        conflicts = self.slots.find_booked_conflicts(schedule.id, horizon_start, horizon_end)
        if conflicts:
            raise ConflictError(
                "Zmiana grafiku koliduje z już opłaconymi rezerwacjami",
                error_code="BOOKED_SLOTS_CONFLICT",
                details=[{"field": "rules", "code": "BOOKED_SLOTS_CONFLICT", "message": str(c.id)} for c in conflicts],
            )

        self.availabilities.replace_rules(schedule.id, rules)

        # Usuwamy niezmaterializowane dotąd sloty AVAILABLE i generujemy je od nowa wg nowych reguł.
        stale = [
            s for s in schedule.time_slots
            if s.status == "AVAILABLE" and s.start_time >= horizon_start
        ]
        for slot in stale:
            self.db.delete(slot)
        self.db.flush()

        generated = self._materialize_slots(schedule.id, rules, horizon_start.date(), horizon_end.date())
        self.db.commit()
        return {"scheduleId": schedule.id, "generatedSlots": generated, "horizon": horizon_end.date().isoformat()}

    @staticmethod
    def _validate_no_overlaps(rules: list[dict]) -> None:
        by_day: dict[int, list[tuple[time, time]]] = {}
        for idx, rule in enumerate(rules):
            day = rule["day_of_week"]
            start, end = rule["start_time"], rule["end_time"]
            if start >= end:
                raise ValidationFailedError(
                    f"Reguła {idx}: godzina początkowa musi być wcześniejsza niż końcowa",
                    error_code="OVERLAPPING_RULES",
                )
            for other_start, other_end in by_day.get(day, []):
                if start < other_end and other_start < end:
                    raise ValidationFailedError(
                        f"Reguły nakładają się na siebie w dayOfWeek={day}",
                        error_code="OVERLAPPING_RULES",
                    )
            by_day.setdefault(day, []).append((start, end))

    def _materialize_slots(
        self, schedule_id: uuid.UUID, rules: list[dict], date_from: date, date_to: date
    ) -> int:
        generated = 0
        current = date_from
        while current <= date_to:
            weekday = current.weekday()  # 0=Pon ... 6=Nie, zgodne z konwencją dokumentu
            for rule in rules:
                if rule["day_of_week"] != weekday:
                    continue
                if current < rule["valid_from"]:
                    continue
                if rule.get("valid_until") and current > rule["valid_until"]:
                    continue

                slot_start = datetime.combine(current, rule["start_time"], tzinfo=timezone.utc)
                slot_end = datetime.combine(current, rule["end_time"], tzinfo=timezone.utc)
                cursor = slot_start
                while cursor + timedelta(minutes=DEFAULT_SLOT_DURATION_MINUTES) <= slot_end:
                    self.slots.save(
                        TimeSlot(
                            schedule_id=schedule_id,
                            start_time=cursor,
                            duration_minutes=DEFAULT_SLOT_DURATION_MINUTES,
                            status="AVAILABLE",
                        )
                    )
                    generated += 1
                    cursor += timedelta(minutes=DEFAULT_SLOT_DURATION_MINUTES)
            current += timedelta(days=1)
        return generated

    # --- UC-P03: blokowanie terminu przez korepetytora -----------------------

    def block_slot(self, tutor_id: uuid.UUID, slot_id: uuid.UUID) -> TimeSlot:
        slot = self.slots.find_by_id(slot_id)
        if slot is None:
            raise NotFoundError("Termin nie istnieje", error_code="SLOT_NOT_FOUND")
        if slot.schedule.tutor_id != tutor_id:
            raise ForbiddenError("Termin nie należy do tego korepetytora", error_code="NOT_OWNER")
        if slot.status == "BOOKED":
            raise ConflictError(
                "Slot ma już aktywną rezerwację - użyj procesu anulowania",
                error_code="SLOT_ALREADY_BOOKED",
            )
        if slot.status == "TEMPORARILY_BLOCKED":
            raise ConflictError(
                "Slot jest tymczasowo zablokowany oczekującą płatnością",
                error_code="SLOT_PENDING_PAYMENT",
            )
        if slot.status != "AVAILABLE":
            raise ConflictError(f"Nie można zablokować slotu w stanie {slot.status}", error_code="SLOT_NOT_AVAILABLE")

        slot.status = "BLOCKED_BY_TUTOR"
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def unblock_slot(self, tutor_id: uuid.UUID, slot_id: uuid.UUID) -> TimeSlot:
        slot = self.slots.find_by_id(slot_id)
        if slot is None:
            raise NotFoundError("Termin nie istnieje", error_code="SLOT_NOT_FOUND")
        if slot.schedule.tutor_id != tutor_id:
            raise ForbiddenError("Termin nie należy do tego korepetytora", error_code="NOT_OWNER")
        if slot.status != "BLOCKED_BY_TUTOR":
            raise ConflictError("Slot nie jest zablokowany ręcznie", error_code="SLOT_NOT_BLOCKED")

        slot.status = "AVAILABLE"
        self.db.commit()
        self.db.refresh(slot)
        return slot

    # --- Endpoint publiczny: wolne terminy korepetytora ------------------------

    def get_public_slots(self, tutor_id: uuid.UUID, date_from: date, date_to: date) -> list[TimeSlot]:
        schedule = self.schedules.find_by_tutor(tutor_id)
        if schedule is None:
            return []
        return self.slots.list_public_slots(schedule.id, date_from, date_to)
