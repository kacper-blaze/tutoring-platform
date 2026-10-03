"""
Router modułu Administracja i System (sekcja 7.10).

Wszystkie endpointy /admin/* wymagają JWT z rolą ADMIN lub SUPER_ADMIN.
Zgłoszenia (reports) mogą tworzyć dowolni zalogowani użytkownicy.
"""
import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.api.schemas import (
    BlockUserRequest,
    BlockUserResponse,
    CascadeEffects,
    CreateReportRequest,
    EditUserRequest,
    EditUserResponse,
    ModerateReviewRequest,
    ModerateReviewResponse,
    ReportResponse,
    ResolveReportRequest,
)
from app.modules.admin.application.admin_service import AdminService
from app.modules.users.api.dependencies import get_current_user, require_role
from app.modules.users.domain.models import UserAccount

router = APIRouter(prefix="/admin", tags=["Administracja i System"])


@router.patch("/users/{user_id}", response_model=EditUserResponse)
def edit_user(
    user_id: uuid.UUID,
    payload: EditUserRequest,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_role("ADMIN", "SUPER_ADMIN")),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    """UC-A01 - edycja konta użytkownika (ADMIN: STUDENT/TUTOR; SUPER_ADMIN: również ADMIN)."""
    target = AdminService(db).edit_user(
        admin.id, admin.role, user_id, payload.email, payload.role, payload.reason, idempotency_key
    )
    return EditUserResponse(userId=target.id, email=target.email, role=target.role, status=target.status)


@router.post("/users/{user_id}/block", response_model=BlockUserResponse)
def block_user(
    user_id: uuid.UUID,
    payload: BlockUserRequest,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_role("ADMIN", "SUPER_ADMIN")),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    UC-A02 - blokowanie konta użytkownika (permanentnie lub tymczasowo).

    Uwaga: kaskadowe anulowanie aktywnych rezerwacji (autoCancelBookings)
    nie jest zaimplementowane w tym szkielecie - patrz TODO w AdminService.
    Zwracane cancelledBookings jest zawsze 0.
    """
    target, meta, revoked = AdminService(db).block_user(
        admin.id, admin.role, user_id, payload.type, payload.reason, payload.suspendedUntil, idempotency_key
    )
    return BlockUserResponse(
        userId=target.id,
        status=target.status,
        blockedAt=meta.blocked_at,
        blockedBy=meta.blocked_by,
        cascadeEffects=CascadeEffects(cancelledBookings=0, revokedTokens=revoked),
    )


@router.post("/users/{user_id}/unblock", response_model=EditUserResponse)
def unblock_user(
    user_id: uuid.UUID,
    reason: str = Query(min_length=3, max_length=500),
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_role("ADMIN", "SUPER_ADMIN")),
):
    target = AdminService(db).unblock_user(admin.id, admin.role, user_id, reason)
    return EditUserResponse(userId=target.id, email=target.email, role=target.role, status=target.status)


@router.post("/reviews/{review_id}/moderate", response_model=ModerateReviewResponse)
def moderate_review(
    review_id: uuid.UUID,
    payload: ModerateReviewRequest,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_role("ADMIN", "SUPER_ADMIN")),
):
    """UC-A03 - moderacja opinii (APPROVE/HIDE/DELETE) z atomowym przeliczeniem średniej."""
    result = AdminService(db).moderate_review(admin.id, admin.role, review_id, payload.action, payload.reason)
    return ModerateReviewResponse(**result)


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: CreateReportRequest,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    """Zgłoszenie treści/konta/rezerwacji do moderacji - dostępne dla każdego zalogowanego użytkownika."""
    report = AdminService(db).create_report(
        user.id, payload.entityType, payload.entityId, payload.category, payload.description
    )
    return ReportResponse.model_validate(report)


@router.get("/reports", response_model=list[ReportResponse])
def list_reports(
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_role("ADMIN", "SUPER_ADMIN")),
):
    """Kolejka moderacji - lista zgłoszeń posortowana wg priorytetu i daty."""
    reports = AdminService(db).list_reports(status_filter, priority)
    return [ReportResponse.model_validate(r) for r in reports]


@router.patch("/reports/{report_id}", response_model=ReportResponse)
def resolve_report(
    report_id: uuid.UUID,
    payload: ResolveReportRequest,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_role("ADMIN", "SUPER_ADMIN")),
):
    """Przypisanie / rozstrzygnięcie / odrzucenie zgłoszenia."""
    report = AdminService(db).resolve_report(admin.id, admin.role, report_id, payload.action, payload.resolution)
    return ReportResponse.model_validate(report)
