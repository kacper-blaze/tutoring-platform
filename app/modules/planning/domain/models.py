"""
Modele ORM modułu Planowanie i Dostępność (specyfikacja, sekcja 5.9).

Właściciel trzech tabel: schedules, availabilities, time_slots. Żaden
inny moduł nie odwołuje się do nich bezpośrednio - komunikacja
wyłącznie przez SchedulingPort (patrz infrastructure/ports.py).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, SmallInteger, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import GUID, AwareDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


SlotStatus = Enum(
    "AVAILABLE", "TEMPORARILY_BLOCKED", "BOOKED", "BLOCKED_BY_TUTOR", "COMPLETED", "CANCELLED",
    name="slot_status",
)


class Schedule(Base):
    """Jeden grafik na korepetytora (relacja logiczna 1:1 z user_accounts, sekcja 5.9)."""

    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tutor_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)

    availabilities: Mapped[list["Availability"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")
    time_slots: Mapped[list["TimeSlot"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")


class Availability(Base):
    """Reguła cykliczna dostępności - jeden przedział godzinowy w danym dniu tygodnia (Tabela 30)."""

    __tablename__ = "availabilities"
    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="chk_availability_day_of_week"),
        Index("idx_availabilities_schedule", "schedule_id"),
        Index("idx_availabilities_day", "schedule_id", "day_of_week"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time = mapped_column(Time, nullable=False)
    end_time = mapped_column(Time, nullable=False)
    valid_from = mapped_column(Date, nullable=False)
    valid_until = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    schedule: Mapped["Schedule"] = relationship(back_populates="availabilities")


class TimeSlot(Base):
    """Zmaterializowana instancja terminu - centralny artefakt modułu (Tabela 31)."""

    __tablename__ = "time_slots"
    __table_args__ = (
        # RB6 (format czasowy sesji): 30-180 minut, wielokrotność 15. Warunek "wielokrotność
        # 15" pominięty na poziomie CHECK (operator % w CheckConstraint powoduje konflikt
        # z escapingiem parametrów psycopg2) - egzekwowany w PlanningService przy tworzeniu slotu.
        CheckConstraint("duration_minutes >= 30 AND duration_minutes <= 180", name="chk_slot_duration_rb6"),
        Index("idx_slots_schedule_status", "schedule_id", "status"),
        Index("idx_slots_start_time", "start_time"),
        Index("idx_slots_locked_until", "locked_until"),
        Index("idx_slots_booking_id", "booking_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    availability_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("availabilities.id", ondelete="SET NULL"), nullable=True
    )
    start_time: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=60)
    status: Mapped[str] = mapped_column(SlotStatus, nullable=False, default="AVAILABLE")
    booking_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    schedule: Mapped["Schedule"] = relationship(back_populates="time_slots")
