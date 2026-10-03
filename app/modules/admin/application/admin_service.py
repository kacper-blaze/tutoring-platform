"""
Serwis aplikacyjny modułu Administracja i System.

Implementuje UC-A01 (edycja konta), UC-A02 (blokowanie konta),
UC-A03 (moderacja opinii) oraz zarządzanie kolejką zgłoszeń (reports).
RB-A1: każda akcja administratora wymaga uzasadnienia (reason) i jest
utrwalana w admin_actions + audit_log w tej samej transakcji.

Moduł integruje się z Użytkownikami (zmiana roli/statusu konta,
unieważnienie tokenów) i Katalogiem (moderacja opinii, przeliczenie
średniej) wyłącznie przez ich serwisy/repozytoria - zgodnie z zasadą
braku bezpośrednich zapytań SQL między modułami.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.modules.admin.domain.models import AdminAction, AuditLog, Report
from app.modules.admin.infrastructure.repositories import (
    AdminActionRepository,
    AdminMetadataRepository,
    AuditLogRepository,
    ReportRepository,
)
from app.modules.catalog.infrastructure.repositories import ReviewRepository, TutorStatsRepository
from app.modules.users.infrastructure.repositories import TokenRepository, UserRepository

# Hierarchia ról: ADMIN może zarządzać STUDENT/TUTOR; konta ADMIN wymagają SUPER_ADMIN.
_PROTECTED_ROLE = "ADMIN"


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.tokens = TokenRepository(db)
        self.admin_meta = AdminMetadataRepository(db)
        self.actions = AdminActionRepository(db)
        self.audit = AuditLogRepository(db)
        self.reports = ReportRepository(db)
        self.review_repo = ReviewRepository(db)
        self.tutor_stats = TutorStatsRepository(db)

    # --- Zapis audytowy (RB-A1) ------------------------------------------------

    def _record(
        self,
        admin_id: uuid.UUID,
        admin_role: str,
        action_type: str,
        target_user_id: uuid.UUID | None,
        reason: str,
        metadata: dict,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> None:
        self.actions.save(
            AdminAction(
                admin_id=admin_id,
                target_user_id=target_user_id,
                action_type=action_type,
                reason=reason,
                action_metadata=metadata,
                idempotency_key=idempotency_key,
            )
        )
        self.audit.save(
            AuditLog(
                actor_id=admin_id,
                actor_role=admin_role,
                event_type=action_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=metadata,
            )
        )

    def _check_idempotency(self, key: str | None) -> bool:
        """Zwraca True, jeśli żądanie z tym kluczem zostało już wykonane (RB-A1 - konwencje)."""
        if key is None:
            return False
        return self.actions.find_by_idempotency_key(key) is not None

    # --- UC-A01: edycja konta użytkownika ---------------------------------------

    def edit_user(
        self,
        admin_id: uuid.UUID,
        admin_role: str,
        user_id: uuid.UUID,
        email: str | None,
        role: str | None,
        reason: str,
        idempotency_key: str | None,
    ):
        if self._check_idempotency(idempotency_key):
            return self.users.find_by_id(user_id)

        target = self.users.find_by_id(user_id)
        if target is None:
            raise NotFoundError("Użytkownik nie istnieje", error_code="USER_NOT_FOUND")

        self._assert_can_manage(admin_role, target.role)
        if role == "ADMIN" and admin_role != "SUPER_ADMIN":
            raise ForbiddenError(
                "Modyfikacja konta na rolę ADMIN wymaga roli SUPER_ADMIN", error_code="INSUFFICIENT_ROLE"
            )

        if email and email.lower() != target.email:
            if self.users.find_by_email(email.lower()) is not None:
                raise ConflictError("Adres e-mail jest już używany", error_code="EMAIL_ALREADY_USED")
            target.email = email.lower()
        if role:
            target.role = role

        self._record(
            admin_id, admin_role, "USER_EDIT", target.id, reason,
            {"email": email, "role": role}, "UserAccount", target.id, idempotency_key,
        )
        self.db.commit()
        self.db.refresh(target)
        return target

    # --- UC-A02: blokowanie konta użytkownika -----------------------------------

    def block_user(
        self,
        admin_id: uuid.UUID,
        admin_role: str,
        user_id: uuid.UUID,
        block_type: str,
        reason: str,
        suspended_until: datetime | None,
        idempotency_key: str | None,
    ):
        if self._check_idempotency(idempotency_key):
            return self.users.find_by_id(user_id), self.admin_meta.get_or_create(user_id)

        target = self.users.find_by_id(user_id)
        if target is None:
            raise NotFoundError("Użytkownik nie istnieje", error_code="USER_NOT_FOUND")
        self._assert_can_manage(admin_role, target.role)

        if block_type == "TEMPORARY" and suspended_until is None:
            raise ValidationFailedError(
                "suspendedUntil jest wymagane dla blokady tymczasowej",
                error_code="VALIDATION_FAILED",
                details=[{"field": "suspendedUntil", "code": "REQUIRED_WHEN_TYPE_TEMPORARY"}],
            )

        target.status = "BLOCKED" if block_type == "PERMANENT" else "SUSPENDED"
        meta = self.admin_meta.get_or_create(target.id)
        meta.block_reason = reason[:500]
        meta.blocked_by = admin_id
        meta.blocked_at = datetime.now(timezone.utc)
        meta.suspended_until = suspended_until if block_type == "TEMPORARY" else None

        revoked = self.tokens.revoke_all_for_user(target.id, reason="ADMIN_BLOCK")

        action_type = "USER_SUSPEND" if block_type == "TEMPORARY" else "USER_BLOCK"
        self._record(
            admin_id, admin_role, action_type, target.id, reason,
            {"blockType": block_type, "revokedTokens": revoked}, "UserAccount", target.id, idempotency_key,
        )
        self.db.commit()
        self.db.refresh(target)
        self.db.refresh(meta)
        return target, meta, revoked

    def unblock_user(self, admin_id: uuid.UUID, admin_role: str, user_id: uuid.UUID, reason: str):
        target = self.users.find_by_id(user_id)
        if target is None:
            raise NotFoundError("Użytkownik nie istnieje", error_code="USER_NOT_FOUND")
        self._assert_can_manage(admin_role, target.role)

        target.status = "ACTIVE"
        meta = self.admin_meta.get_or_create(target.id)
        meta.suspended_until = None

        self._record(admin_id, admin_role, "USER_UNBLOCK", target.id, reason, {}, "UserAccount", target.id)
        self.db.commit()
        self.db.refresh(target)
        return target

    @staticmethod
    def _assert_can_manage(admin_role: str, target_role: str) -> None:
        if target_role in (_PROTECTED_ROLE, "SUPER_ADMIN") and admin_role != "SUPER_ADMIN":
            raise ForbiddenError(
                "Zarządzanie kontem administratora wymaga roli SUPER_ADMIN", error_code="INSUFFICIENT_ROLE"
            )

    # --- UC-A03: moderacja opinii ------------------------------------------------

    def moderate_review(
        self, admin_id: uuid.UUID, admin_role: str, review_id: uuid.UUID, action: str, reason: str | None
    ) -> dict:
        review = self.review_repo.find_by_id(review_id)
        if review is None:
            raise NotFoundError("Opinia nie istnieje", error_code="REVIEW_NOT_FOUND")

        status_map = {"APPROVE": "APPROVED", "HIDE": "HIDDEN", "DELETE": "DELETED"}
        if action not in status_map:
            raise ValidationFailedError("Nieprawidłowa akcja moderacji", error_code="INVALID_ACTION")
        if action in ("HIDE", "DELETE") and not reason:
            raise ValidationFailedError(
                "Uzasadnienie jest wymagane dla HIDE/DELETE",
                error_code="VALIDATION_FAILED",
                details=[{"field": "reason", "code": "REQUIRED"}],
            )

        review.status = status_map[action]
        avg, count = self.review_repo.recalculate_average(review.tutor_id)
        stats = self.tutor_stats.get_or_create(review.tutor_id)
        stats.average_rating = round(avg, 2)
        stats.review_count = count

        action_type = "REVIEW_HIDE" if action == "HIDE" else "REVIEW_DELETE" if action == "DELETE" else "USER_EDIT"
        self._record(
            admin_id, admin_role, action_type, review.student_id, reason or "Zatwierdzenie opinii",
            {"reviewId": str(review.id), "newStatus": review.status}, "Review", review.id,
        )
        self.db.commit()
        return {"reviewId": review.id, "newStatus": review.status, "newTutorAverage": float(stats.average_rating)}

    # --- Zgłoszenia (reports) -----------------------------------------------------

    def create_report(
        self, reporter_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID, category: str, description: str
    ) -> Report:
        priority = "HIGH" if category == "FINANCIAL_DISPUTE" else "NORMAL"
        report = Report(
            reporter_id=reporter_id,
            reported_entity_type=entity_type,
            reported_entity_id=entity_id,
            category=category,
            priority=priority,
            description=description,
        )
        self.reports.save(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def list_reports(self, status: str | None, priority: str | None) -> list[Report]:
        return self.reports.list_queue(status, priority)

    def resolve_report(
        self, admin_id: uuid.UUID, admin_role: str, report_id: uuid.UUID, action: str, resolution: str | None
    ) -> Report:
        report = self.reports.find_by_id(report_id)
        if report is None:
            raise NotFoundError("Zgłoszenie nie istnieje", error_code="REPORT_NOT_FOUND")

        if action == "ASSIGN":
            report.status = "IN_PROGRESS"
            report.assigned_admin_id = admin_id
            action_type = "REPORT_ASSIGN"
        elif action == "RESOLVE":
            report.status = "RESOLVED"
            report.resolution = resolution
            report.resolved_at = datetime.now(timezone.utc)
            action_type = "REPORT_RESOLVE"
        elif action == "REJECT":
            report.status = "REJECTED"
            report.resolution = resolution
            report.resolved_at = datetime.now(timezone.utc)
            action_type = "REPORT_REJECT"
        else:
            raise ValidationFailedError("Nieprawidłowa akcja", error_code="INVALID_ACTION")

        self._record(
            admin_id, admin_role, action_type, report.reporter_id, resolution or f"Akcja {action} na zgłoszeniu",
            {"reportId": str(report.id)}, "Report", report.id,
        )
        self.db.commit()
        self.db.refresh(report)
        return report
