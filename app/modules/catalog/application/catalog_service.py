"""
Serwis aplikacyjny modułu Katalog i Wyszukiwanie (UC-K01 - UC-K11).

Implementuje:
  - wyszukiwanie/filtrowanie/sortowanie ofert (UC-K01 - UC-K05, UC-K11),
  - przeglądanie profilu korepetytora i jego opinii (UC-K06, UC-K07),
  - dodawanie/edycję/usuwanie opinii z atomowym przeliczeniem średniej
    i ochroną przed review bombing (UC-K08, UC-K09, sekcja 4.10.1),
  - ulubieni korepetytorzy (UC-K10).
"""
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.modules.catalog.domain.models import Offer, Review
from app.modules.catalog.infrastructure.ports import TutorProfilePort, TutorProfileView
from app.modules.catalog.infrastructure.repositories import (
    FavoriteRepository,
    OfferRepository,
    ReviewRepository,
    TutorStatsRepository,
)

# Sekcja 4.10.1: próg ochrony przed manipulacją ocenami.
REVIEW_BOMBING_EXTREME_THRESHOLD = 3


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.offers = OfferRepository(db)
        self.reviews = ReviewRepository(db)
        self.favorites = FavoriteRepository(db)
        self.stats = TutorStatsRepository(db)
        self.tutor_port = TutorProfilePort(db)

    # --- UC-K01 - UC-K05, UC-K11: wyszukiwanie i filtrowanie ofert -----------

    def search_offers(
        self,
        subject: str | None,
        price_min: float | None,
        price_max: float | None,
        keyword: str | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        items, total = self.offers.search(subject, price_min, price_max, keyword, sort, page, page_size)
        results = []
        for offer in items:
            profile = self.tutor_port.get_tutor_profile(offer.tutor_id)
            stats = self.stats.find(offer.tutor_id)
            results.append(self._offer_to_dict(offer, profile, stats))
        return results, total  # total==0 sygnalizuje UC-K11 (brak wyników) na poziomie API

    @staticmethod
    def _offer_to_dict(offer: Offer, profile: TutorProfileView | None, stats) -> dict:
        return {
            "offerId": offer.id,
            "tutorId": offer.tutor_id,
            "subject": offer.subject,
            "hourlyRate": float(offer.hourly_rate),
            "tutorName": f"{profile.first_name} {profile.last_name}" if profile else "Korepetytor",
            "avatarUrl": profile.avatar_url if profile else None,
            "averageRating": float(stats.average_rating) if stats else 0.0,
            "reviewCount": stats.review_count if stats else 0,
        }

    # --- UC-K06: profil korepetytora ------------------------------------------

    def get_tutor_profile(self, tutor_id: uuid.UUID) -> dict:
        profile = self.tutor_port.get_tutor_profile(tutor_id)
        if profile is None:
            raise NotFoundError("Korepetytor nie istnieje", error_code="TUTOR_NOT_FOUND")
        stats = self.stats.get_or_create(tutor_id)
        offers, _ = self.offers.search(None, None, None, None, "newest", 1, 100)
        tutor_offers = [o for o in offers if o.tutor_id == tutor_id]
        return {
            "tutorId": profile.tutor_id,
            "firstName": profile.first_name,
            "lastName": profile.last_name,
            "bio": profile.bio,
            "avatarUrl": profile.avatar_url,
            "averageRating": float(stats.average_rating),
            "reviewCount": stats.review_count,
            "offers": [
                {"id": o.id, "subject": o.subject, "hourlyRate": float(o.hourly_rate)} for o in tutor_offers
            ],
        }

    # --- Zarządzanie ofertami (korepetytor) -----------------------------------

    def create_offer(self, tutor_id: uuid.UUID, subject: str, hourly_rate: float) -> Offer:
        self.stats.get_or_create(tutor_id)
        offer = Offer(tutor_id=tutor_id, subject=subject.upper(), hourly_rate=hourly_rate)
        self.offers.save(offer)
        self.db.commit()
        self.db.refresh(offer)
        return offer

    # --- UC-K07: opinie o korepetytorze ----------------------------------------

    def list_reviews(self, tutor_id: uuid.UUID, page: int, page_size: int) -> tuple[list[Review], int]:
        return self.reviews.list_for_tutor(tutor_id, page, page_size)

    # --- UC-K08: dodanie opinii (z ochroną review bombing, sekcja 4.10.1) -----

    def add_review(
        self,
        student_id: uuid.UUID,
        tutor_id: uuid.UUID,
        lesson_id: uuid.UUID,
        rating: int,
        comment: str | None,
        ip_address: str | None,
    ) -> Review:
        if self.reviews.find_by_lesson(lesson_id) is not None:
            raise ConflictError("Opinia dla tej lekcji już istnieje", error_code="REVIEW_ALREADY_EXISTS")

        # Sekcja 4.10.1: >3 skrajne oceny (1 lub 5) z jednego konta/IP w ciągu 1h -> zamrożenie (PENDING).
        extreme_count = self.reviews.count_recent_extreme_ratings(student_id, ip_address)
        status = "PENDING" if (rating in (1, 5) and extreme_count >= REVIEW_BOMBING_EXTREME_THRESHOLD) else "APPROVED"

        review = Review(
            tutor_id=tutor_id,
            student_id=student_id,
            lesson_id=lesson_id,
            rating=rating,
            comment=comment,
            status=status,
            ip_address=ip_address,
        )
        self.reviews.save(review)

        if status == "APPROVED":
            self._recalculate_and_persist(tutor_id)

        self.db.commit()
        self.db.refresh(review)
        return review

    # --- UC-K09: edycja/usunięcie opinii ---------------------------------------

    def delete_review(self, student_id: uuid.UUID, review_id: uuid.UUID) -> None:
        review = self.reviews.find_by_id(review_id)
        if review is None:
            raise NotFoundError("Opinia nie istnieje", error_code="REVIEW_NOT_FOUND")
        if review.student_id != student_id:
            raise ForbiddenError("Można usuwać wyłącznie własne opinie", error_code="NOT_OWNER")

        was_approved = review.status == "APPROVED"
        tutor_id = review.tutor_id
        review.status = "DELETED"
        if was_approved:
            self._recalculate_and_persist(tutor_id)
        self.db.commit()

    def _recalculate_and_persist(self, tutor_id: uuid.UUID) -> None:
        """calculateAverageRating() - sekcja 4.10.1, wywoływana wyłącznie po zmianie stanu na/z APPROVED."""
        avg, count = self.reviews.recalculate_average(tutor_id)
        stats = self.stats.get_or_create(tutor_id)
        stats.average_rating = round(avg, 2)
        stats.review_count = count

    # --- UC-K10: ulubieni -------------------------------------------------------

    def add_favorite(self, student_id: uuid.UUID, tutor_id: uuid.UUID) -> None:
        if not self.tutor_port.tutor_exists(tutor_id):
            raise NotFoundError("Korepetytor nie istnieje", error_code="TUTOR_NOT_FOUND")
        self.favorites.add(student_id, tutor_id)
        self.db.commit()

    def remove_favorite(self, student_id: uuid.UUID, tutor_id: uuid.UUID) -> None:
        if not self.favorites.remove(student_id, tutor_id):
            raise NotFoundError("Korepetytor nie jest w ulubionych", error_code="FAVORITE_NOT_FOUND")
        self.db.commit()

    def list_favorites(self, student_id: uuid.UUID) -> list[dict]:
        favorites = self.favorites.list_for_student(student_id)
        result = []
        for fav in favorites:
            profile = self.tutor_port.get_tutor_profile(fav.tutor_id)
            stats = self.stats.find(fav.tutor_id)
            result.append(
                {
                    "tutorId": fav.tutor_id,
                    "tutorName": f"{profile.first_name} {profile.last_name}" if profile else "Korepetytor",
                    "averageRating": float(stats.average_rating) if stats else 0.0,
                }
            )
        return result
