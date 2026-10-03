"""
Modele ORM modułu Katalog i Wyszukiwanie Ofert Korepetycji (specyfikacja, sekcja 4.4).

Uwaga o granicach modułów: tabela `tutors` ze specyfikacji przechowuje
`bio` i `average_rating` dla korepetytora. `bio` jest de facto własnością
modułu Użytkowników (tutor_profiles.bio) - żeby uniknąć duplikacji i
niespójności danych, ten szkielet przechowuje w module Katalogu jedynie
dane, których ten moduł jest właścicielem: statystyki wyliczane z opinii
(`tutor_catalog_stats` - odpowiednik pola `tutors.average_rating`),
oferty, opinie i ulubione. Dane profilowe (bio, imię, przedmioty)
pobierane są przez TutorProfilePort z modułu Użytkowników (patrz
infrastructure/ports.py) - zgodnie z zasadą "żadne bezpośrednie
zapytanie SQL spoza modułu nie jest dozwolone" z dokumentu.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BOOLEAN,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import GUID, AwareDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


ReviewStatus = Enum("PENDING", "APPROVED", "HIDDEN", "DELETED", name="review_status")


class TutorCatalogStats(Base):
    """
    Odpowiednik pól tutors.bio/average_rating ze specyfikacji, ograniczony
    do danych będących własnością modułu Katalogu (średnia ocen, liczba
    opinii). Wiersz tworzony automatycznie przy pierwszej ofercie
    korepetytora.
    """

    __tablename__ = "tutor_catalog_stats"

    tutor_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    average_rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    offers: Mapped[list["Offer"]] = relationship(back_populates="tutor_stats")


class Offer(Base):
    """Oferta korepetycji - jeden przedmiot nauczany przez korepetytora (sekcja 4.4)."""

    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("hourly_rate > 0", name="chk_offer_hourly_rate_positive"),
        Index("idx_offers_tutor", "tutor_id"),
        Index("idx_offers_subject", "subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tutor_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tutor_catalog_stats.tutor_id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False)
    hourly_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    tutor_stats: Mapped["TutorCatalogStats"] = relationship(back_populates="offers")


class Review(Base):
    """Opinia ucznia o korepetytorze po odbytej lekcji (UC-K08, UC-K09)."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_review_rating_range"),
        UniqueConstraint("lesson_id", name="uq_review_lesson"),
        Index("idx_reviews_tutor_status", "tutor_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tutor_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    lesson_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(ReviewStatus, nullable=False, default="APPROVED")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class Favorite(Base):
    """Korepetytor dodany do ulubionych przez ucznia (UC-K10)."""

    __tablename__ = "favorites"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    tutor_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
