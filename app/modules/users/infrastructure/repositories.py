"""
Repozytoria modułu Użytkownicy i Bezpieczeństwo.

Interfejsy odpowiadają kontraktom portów domenowych z Tabeli 10
specyfikacji (UserRepository, TokenRepository).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.domain.models import RefreshToken, UserAccount


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, user_id: uuid.UUID) -> UserAccount | None:
        return self.db.get(UserAccount, user_id)

    def find_by_email(self, email: str) -> UserAccount | None:
        stmt = select(UserAccount).where(UserAccount.email == email.lower())
        return self.db.scalar(stmt)

    def find_by_activation_token(self, token: str) -> UserAccount | None:
        stmt = select(UserAccount).where(UserAccount.activation_token == token)
        return self.db.scalar(stmt)

    def find_by_password_reset_token(self, token: str) -> UserAccount | None:
        stmt = select(UserAccount).where(UserAccount.password_reset_token == token)
        return self.db.scalar(stmt)

    def save(self, account: UserAccount) -> UserAccount:
        self.db.add(account)
        self.db.flush()
        return account


class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.db.scalar(stmt)

    def revoke_all_for_user(self, user_id: uuid.UUID, reason: str) -> int:
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
        )
        tokens = self.db.scalars(stmt).all()
        now = datetime.now(timezone.utc)
        for token in tokens:
            token.revoked = True
            token.revoked_at = now
            token.revoke_reason = reason
        self.db.flush()
        return len(tokens)

    def revoke_by_hash(self, token_hash: str, reason: str) -> None:
        token = self.find_by_hash(token_hash)
        if token and not token.revoked:
            token.revoked = True
            token.revoked_at = datetime.now(timezone.utc)
            token.revoke_reason = reason
            self.db.flush()
