"""Repozytoria modułu Administracja i System (sekcja 7.9)."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.admin.domain.models import AdminAction, AuditLog, Report, UserAdminMetadata


class AdminMetadataRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, user_id: uuid.UUID) -> UserAdminMetadata:
        meta = self.db.get(UserAdminMetadata, user_id)
        if meta is None:
            meta = UserAdminMetadata(user_id=user_id)
            self.db.add(meta)
            self.db.flush()
        return meta


class AdminActionRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_idempotency_key(self, key: str) -> AdminAction | None:
        stmt = select(AdminAction).where(AdminAction.idempotency_key == key)
        return self.db.scalar(stmt)

    def save(self, action: AdminAction) -> AdminAction:
        self.db.add(action)
        self.db.flush()
        return action

    def list_for_target(self, target_user_id: uuid.UUID) -> list[AdminAction]:
        stmt = (
            select(AdminAction)
            .where(AdminAction.target_user_id == target_user_id)
            .order_by(AdminAction.performed_at.desc())
        )
        return list(self.db.scalars(stmt).all())


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, entry: AuditLog) -> AuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_aggregate(self, aggregate_type: str, aggregate_id: uuid.UUID) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.aggregate_type == aggregate_type, AuditLog.aggregate_id == aggregate_id)
            .order_by(AuditLog.occurred_at.desc())
        )
        return list(self.db.scalars(stmt).all())


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, report: Report) -> Report:
        self.db.add(report)
        self.db.flush()
        return report

    def find_by_id(self, report_id: uuid.UUID) -> Report | None:
        return self.db.get(Report, report_id)

    def list_queue(self, status: str | None, priority: str | None) -> list[Report]:
        stmt = select(Report)
        if status:
            stmt = stmt.where(Report.status == status)
        if priority:
            stmt = stmt.where(Report.priority == priority)
        stmt = stmt.order_by(Report.priority.desc(), Report.created_at.asc())
        return list(self.db.scalars(stmt).all())
