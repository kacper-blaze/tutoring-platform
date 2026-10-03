"""Repozytoria modułu Katalog i Wyszukiwanie (sekcja 4.4)."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.catalog.domain.models import Favorite, Offer, Review, TutorCatalogStats


class TutorStatsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, tutor_id: uuid.UUID) -> TutorCatalogStats:
        stats = self.db.get(TutorCatalogStats, tutor_id)
        if stats is None:
            stats = TutorCatalogStats(tutor_id=tutor_id, average_rating=0, review_count=0)
            self.db.add(stats)
            self.db.flush()
        return stats

    def find(self, tutor_id: uuid.UUID) -> TutorCatalogStats | None:
        return self.db.get(TutorCatalogStats, tutor_id)


class OfferRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, offer: Offer) -> Offer:
        self.db.add(offer)
        self.db.flush()
        return offer

    def find_by_id(self, offer_id: uuid.UUID) -> Offer | None:
        return self.db.get(Offer, offer_id)

    def search(
        self,
        subject: str | None,
        price_min: float | None,
        price_max: float | None,
        keyword: str | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Offer], int]:
        stmt = select(Offer).where(Offer.is_active.is_(True))

        if subject:
            stmt = stmt.where(Offer.subject == subject)
        if price_min is not None:
            stmt = stmt.where(Offer.hourly_rate >= price_min)
        if price_max is not None:
            stmt = stmt.where(Offer.hourly_rate <= price_max)
        if keyword:
            # Uproszczona wersja UC-K02: ILIKE po przedmiocie. Docelowo (sekcja 4.10)
            # tsvector/tsquery + indeks GIN po tutor_stats/offers - poza zakresem szkieletu.
            like = f"%{keyword}%"
            stmt = stmt.where(Offer.subject.ilike(like))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        if sort == "price_asc":
            stmt = stmt.order_by(Offer.hourly_rate.asc())
        elif sort == "price_desc":
            stmt = stmt.order_by(Offer.hourly_rate.desc())
        elif sort == "rating_desc":
            stmt = stmt.join(TutorCatalogStats, Offer.tutor_id == TutorCatalogStats.tutor_id).order_by(
                TutorCatalogStats.average_rating.desc()
            )
        else:
            stmt = stmt.order_by(Offer.created_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return items, total


class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, review: Review) -> Review:
        self.db.add(review)
        self.db.flush()
        return review

    def find_by_id(self, review_id: uuid.UUID) -> Review | None:
        return self.db.get(Review, review_id)

    def find_by_lesson(self, lesson_id: uuid.UUID) -> Review | None:
        stmt = select(Review).where(Review.lesson_id == lesson_id)
        return self.db.scalar(stmt)

    def list_for_tutor(self, tutor_id: uuid.UUID, page: int, page_size: int) -> tuple[list[Review], int]:
        stmt = select(Review).where(Review.tutor_id == tutor_id, Review.status == "APPROVED")
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(Review.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(self.db.scalars(stmt).all()), total

    def recalculate_average(self, tutor_id: uuid.UUID) -> tuple[float, int]:
        """RB / sekcja 4.10.1: średnia liczona WYŁĄCZNIE z opinii w stanie APPROVED."""
        stmt = select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.tutor_id == tutor_id, Review.status == "APPROVED"
        )
        avg, count = self.db.execute(stmt).one()
        return float(avg or 0), int(count or 0)

    def count_recent_extreme_ratings(self, student_id: uuid.UUID, ip_address: str | None, minutes: int = 60) -> int:
        """Sekcja 4.10.1 - ochrona przed review bombing: >3 skrajne oceny (1 lub 5) / godzinę."""
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        conditions = [Review.created_at >= since, or_(Review.rating == 1, Review.rating == 5)]
        stmt = select(func.count(Review.id)).where(Review.student_id == student_id, *conditions)
        count = self.db.scalar(stmt) or 0
        if ip_address:
            ip_stmt = select(func.count(Review.id)).where(Review.ip_address == ip_address, *conditions)
            count = max(count, self.db.scalar(ip_stmt) or 0)
        return count


class FavoriteRepository:
    def __init__(self, db: Session):
        self.db = db

    def find(self, student_id: uuid.UUID, tutor_id: uuid.UUID) -> Favorite | None:
        return self.db.get(Favorite, {"student_id": student_id, "tutor_id": tutor_id})

    def add(self, student_id: uuid.UUID, tutor_id: uuid.UUID) -> Favorite:
        existing = self.find(student_id, tutor_id)
        if existing:
            return existing
        favorite = Favorite(student_id=student_id, tutor_id=tutor_id)
        self.db.add(favorite)
        self.db.flush()
        return favorite

    def remove(self, student_id: uuid.UUID, tutor_id: uuid.UUID) -> bool:
        favorite = self.find(student_id, tutor_id)
        if favorite is None:
            return False
        self.db.delete(favorite)
        self.db.flush()
        return True

    def list_for_student(self, student_id: uuid.UUID) -> list[Favorite]:
        stmt = select(Favorite).where(Favorite.student_id == student_id)
        return list(self.db.scalars(stmt).all())
