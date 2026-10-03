"""
Modele ORM modułu Administracja i System (specyfikacja, sekcja 7.9).

Zaimplementowany podzbiór dziewięciu tabel ze specyfikacji:
user_admin_metadata, admin_actions, audit_log, reports.
Pominięte w tym szkielecie (TODO): dispute_cases, platform_config,
notification_templates, notification_log, outbox_events (ten moduł
może reużyć wzorca z app/modules/users/domain/models.py::OutboxEvent).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy import JSON as SA_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import GUID, AwareDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


AdminActionType = Enum(
    "USER_EDIT", "USER_SUSPEND", "USER_BLOCK", "USER_UNBLOCK", "USER_DELETE",
    "REVIEW_HIDE", "REVIEW_DELETE", "REPORT_ASSIGN", "REPORT_RESOLVE", "REPORT_REJECT",
    name="admin_action_type",
)

EntityType = Enum("USER", "REVIEW", "BOOKING", "OFFER", name="entity_type")

ReportCategory = Enum(
    "REGULATIONS_VIOLATION", "TECHNICAL_ISSUE", "FINANCIAL_DISPUTE", "INAPPROPRIATE_CONTENT", "OTHER",
    name="report_category",
)

ReportPriority = Enum("LOW", "NORMAL", "HIGH", "URGENT", name="report_priority")

ReportStatus = Enum(
    "NEW", "IN_PROGRESS", "AWAITING_RESPONSE", "ESCALATED", "RESOLVED", "REJECTED",
    name="report_status",
)


class UserAdminMetadata(Base):
    """Rozszerzenie user_accounts o pola widoczne wyłącznie dla administratora (Tabela 43)."""

    __tablename__ = "user_admin_metadata"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    suspended_until: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    block_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    blocked_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    last_admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class AdminAction(Base):
    """Rejestr każdej akcji administracyjnej - append-only (Tabela 44, RB-A1)."""

    __tablename__ = "admin_actions"
    __table_args__ = (
        Index("idx_admin_actions_admin", "admin_id", "performed_at"),
        Index("idx_admin_actions_target", "target_user_id", "performed_at"),
        Index("idx_admin_actions_type", "action_type", "performed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    action_type: Mapped[str] = mapped_column(AdminActionType, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_metadata: Mapped[dict] = mapped_column(SA_JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)


class AuditLog(Base):
    """Globalny, nieusuwalny dziennik zdarzeń systemowych (Tabela 45, RB-A1). Celowo bez FK do user_accounts."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_actor", "actor_id", "occurred_at"),
        Index("idx_audit_aggregate", "aggregate_type", "aggregate_id", "occurred_at"),
        Index("idx_audit_event_type", "event_type", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    payload: Mapped[dict] = mapped_column(SA_JSON, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)


class Report(Base):
    """Zgłoszenie użytkownika wymagające reakcji administratora (Tabela 46)."""

    __tablename__ = "reports"
    __table_args__ = (
        Index("idx_reports_status_priority", "status", "priority", "created_at"),
        Index("idx_reports_assigned", "assigned_admin_id", "status"),
        Index("idx_reports_reporter", "reporter_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    reported_entity_type: Mapped[str] = mapped_column(EntityType, nullable=False)
    reported_entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    category: Mapped[str] = mapped_column(ReportCategory, nullable=False)
    priority: Mapped[str] = mapped_column(ReportPriority, nullable=False, default="NORMAL")
    status: Mapped[str] = mapped_column(ReportStatus, nullable=False, default="NEW")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_admin_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
