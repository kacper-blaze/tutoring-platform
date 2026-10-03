"""
Modele ORM modułu Użytkownicy i Bezpieczeństwo.

Odzwierciedlają dosłownie schemat z sekcji 3.8 dokumentu specyfikacji:
tabele user_accounts, student_profiles, tutor_profiles, refresh_tokens
oraz outbox_events (Transactional Outbox), wraz z typami wyliczeniowymi
user_role, account_status, verification_status.
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
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy import JSON as SA_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import GUID, AwareDateTime, StringArray


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Typy wyliczeniowe (ENUM) -------------------------------------------

UserRole = Enum(
    "STUDENT", "TUTOR", "ADMIN", "SUPER_ADMIN",
    name="user_role",
)

AccountStatus = Enum(
    "PENDING_ACTIVATION", "ACTIVE", "VERIFIED", "SUSPENDED",
    "BLOCKED", "PENDING_DELETION", "DELETED",
    name="account_status",
)

VerificationStatus = Enum(
    "UNVERIFIED", "PHONE_VERIFIED", "FULLY_VERIFIED",
    name="verification_status",
)


# --- user_accounts -------------------------------------------------------

class UserAccount(Base):
    """Główny agregat modułu - tożsamość, poświadczenia, cykl życia konta."""

    __tablename__ = "user_accounts"
    __table_args__ = (
        CheckConstraint(
            "password_hash IS NOT NULL OR (oauth_provider IS NOT NULL AND oauth_subject IS NOT NULL)",
            name="chk_password_or_oauth",
        ),
        Index("idx_ua_email", "email"),
        Index("idx_ua_status", "status"),
        Index("idx_ua_locked", "locked_until"),
        Index("idx_ua_activation_token", "activation_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(72), nullable=True)
    role: Mapped[str] = mapped_column(UserRole, nullable=False, default="STUDENT")
    status: Mapped[str] = mapped_column(AccountStatus, nullable=False, default="PENDING_ACTIVATION")
    verification_status: Mapped[str] = mapped_column(VerificationStatus, nullable=False, default="UNVERIFIED")
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    activation_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activation_token_expires_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    oauth_subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)

    # Reset hasła (nie wyszczególnione jako osobna tabela w dokumencie -
    # modelowane analogicznie do activation_token, dedykowane pola resetu)
    password_reset_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    tutor_profile: Mapped["TutorProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


# --- student_profiles ----------------------------------------------------

class StudentProfile(Base):
    """Dane profilowe ucznia. Relacja 1:1 z user_accounts (UC-B02, UC-B06)."""

    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    subjects: Mapped[list[str]] = mapped_column(StringArray(), nullable=False, default=list)
    education_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["UserAccount"] = relationship(back_populates="student_profile")


# --- tutor_profiles --------------------------------------------------------

class TutorProfile(Base):
    """Dane profilowe korepetytora. Relacja 1:1 z user_accounts (UC-B02, UC-B06, UC-B09)."""

    __tablename__ = "tutor_profiles"
    __table_args__ = (
        CheckConstraint("hourly_rate IS NULL OR hourly_rate > 0", name="chk_tutor_hourly_rate_positive"),
        CheckConstraint("experience_years IS NULL OR experience_years >= 0", name="chk_tutor_experience_nonneg"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    subjects: Mapped[list[str]] = mapped_column(StringArray(), nullable=False, default=list)
    hourly_rate: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_years: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    verification_docs: Mapped[list[str]] = mapped_column(StringArray(), nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["UserAccount"] = relationship(back_populates="tutor_profile")


# --- refresh_tokens ---------------------------------------------------------

class RefreshToken(Base):
    """Append-only rejestr tokenów odświeżających z miękkim unieważnianiem (revoked)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("idx_rt_token_hash", "token_hash"),
        Index("idx_rt_user_active", "user_id", "expires_at"),
        Index("idx_rt_cleanup", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    revoked: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)

    user: Mapped["UserAccount"] = relationship(back_populates="refresh_tokens")


# --- outbox_events (Transactional Outbox) -----------------------------------

class OutboxEvent(Base):
    """
    Implementacja wzorca Transactional Outbox (moduł Użytkowników).

    Każda zmiana domenowa wymagająca powiadomienia innych modułów jest
    zapisywana tutaj w tej samej transakcji, co modyfikacja encji.
    Dedykowany worker (poza zakresem tego szkieletu) publikowałby te
    zdarzenia do brokera i oznaczał je jako published.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (Index("idx_outbox_users_unpublished", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False, default="UserAccount")
    aggregate_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    payload: Mapped[dict] = mapped_column(SA_JSON, nullable=False)
    published: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=_utcnow, nullable=False)
