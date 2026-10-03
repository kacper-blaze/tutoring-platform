"""
Router modułu Katalog i Wyszukiwanie (sekcja 4.5 - kontrakty API REST).

Przeglądanie katalogu i profili jest publiczne (aktor Gość, A1).
Dodawanie opinii i ulubionych wymaga roli STUDENT (aktor Uczeń, A2).
"""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.catalog.api.schemas import (
    AddFavoriteRequest,
    CreateOfferRequest,
    CreateReviewRequest,
    FavoriteResponse,
    OfferSearchResponse,
    OfferSummaryResponse,
    ReviewListResponse,
    ReviewResponse,
    TutorProfilePublicResponse,
)
from app.modules.catalog.application.catalog_service import CatalogService
from app.modules.users.api.dependencies import require_role
from app.modules.users.domain.models import UserAccount

router = APIRouter(tags=["Katalog i Wyszukiwanie"])


@router.get("/offers", response_model=OfferSearchResponse)
def search_offers(
    subject: str | None = Query(default=None, description="UC-K03: filtr przedmiotu"),
    priceMin: float | None = Query(default=None, description="UC-K04: cena minimalna"),
    priceMax: float | None = Query(default=None, description="UC-K04: cena maksymalna"),
    keyword: str | None = Query(default=None, description="UC-K02: wyszukiwanie słowem kluczowym"),
    sort: Literal["newest", "price_asc", "price_desc", "rating_desc"] = Query(
        default="newest", description="UC-K05: sortowanie wyników"
    ),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """UC-K01/K02/K03/K04/K05/K11 - przeglądanie, wyszukiwanie i filtrowanie katalogu ofert."""
    service = CatalogService(db)
    items, total = service.search_offers(subject, priceMin, priceMax, keyword, sort, page, pageSize)
    return OfferSearchResponse(
        items=[OfferSummaryResponse(**item) for item in items], total=total, page=page, pageSize=pageSize
    )


@router.post("/tutors/me/offers", response_model=OfferSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: CreateOfferRequest,
    db: Session = Depends(get_db),
    tutor: UserAccount = Depends(require_role("TUTOR")),
):
    """Publikacja oferty przez korepetytora (warunek wstępny dla UC-K01 - bez ofert katalog jest pusty)."""
    service = CatalogService(db)
    offer = service.create_offer(tutor.id, payload.subject, payload.hourlyRate)
    profile = service.tutor_port.get_tutor_profile(tutor.id)
    stats = service.stats.find(tutor.id)
    return OfferSummaryResponse(**CatalogService._offer_to_dict(offer, profile, stats))


@router.get("/tutors/{tutor_id}", response_model=TutorProfilePublicResponse)
def get_tutor_profile(tutor_id: uuid.UUID, db: Session = Depends(get_db)):
    """UC-K06 - pełny profil korepetytora z aktywnymi ofertami."""
    service = CatalogService(db)
    data = service.get_tutor_profile(tutor_id)
    return TutorProfilePublicResponse(**data)


@router.get("/tutors/{tutor_id}/reviews", response_model=ReviewListResponse)
def list_tutor_reviews(
    tutor_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """UC-K07 - lista zatwierdzonych (APPROVED) opinii o korepetytorze."""
    service = CatalogService(db)
    items, total = service.list_reviews(tutor_id, page, pageSize)
    return ReviewListResponse(items=[ReviewResponse.model_validate(r) for r in items], total=total)


@router.post("/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def add_review(
    payload: CreateReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-K08 - dodanie opinii i oceny (chronione przed review bombing, sekcja 4.10.1)."""
    service = CatalogService(db)
    review = service.add_review(
        student_id=student.id,
        tutor_id=payload.tutorId,
        lesson_id=payload.lessonId,
        rating=payload.rating,
        comment=payload.comment,
        ip_address=request.client.host if request.client else None,
    )
    return ReviewResponse.model_validate(review)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-K09 - usunięcie własnej opinii (soft-delete + przeliczenie średniej)."""
    CatalogService(db).delete_review(student.id, review_id)


@router.post("/favorites", response_model=FavoriteResponse)
def add_favorite(
    payload: AddFavoriteRequest,
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-K10 - dodanie korepetytora do ulubionych."""
    service = CatalogService(db)
    service.add_favorite(student.id, payload.tutorId)
    profile = service.tutor_port.get_tutor_profile(payload.tutorId)
    stats = service.stats.find(payload.tutorId)
    return FavoriteResponse(
        tutorId=payload.tutorId,
        tutorName=f"{profile.first_name} {profile.last_name}" if profile else "Korepetytor",
        averageRating=float(stats.average_rating) if stats else 0.0,
    )


@router.delete("/favorites/{tutor_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    tutor_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-K10 - usunięcie korepetytora z ulubionych."""
    CatalogService(db).remove_favorite(student.id, tutor_id)


@router.get("/favorites/me", response_model=list[FavoriteResponse])
def list_my_favorites(
    db: Session = Depends(get_db),
    student: UserAccount = Depends(require_role("STUDENT")),
):
    """UC-K10 - lista ulubionych korepetytorów bieżącego ucznia."""
    service = CatalogService(db)
    return [FavoriteResponse(**item) for item in service.list_favorites(student.id)]
