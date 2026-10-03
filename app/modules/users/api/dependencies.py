"""Zależności FastAPI: ekstrakcja bieżącego użytkownika z access tokenu JWT."""
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.modules.users.domain.models import UserAccount
from app.modules.users.infrastructure.repositories import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    if credentials is None:
        raise UnauthorizedError("Brak tokenu uwierzytelniającego", error_code="MISSING_TOKEN")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedError("Token nieprawidłowy lub wygasły", error_code="TOKEN_INVALID") from exc

    user_id = uuid.UUID(payload["sub"])
    account = UserRepository(db).find_by_id(user_id)
    if account is None or account.status in ("SUSPENDED", "BLOCKED", "DELETED", "PENDING_DELETION"):
        raise UnauthorizedError("Konto niedostępne", error_code="ACCOUNT_UNAVAILABLE")

    return account


def require_role(*roles: str):
    def _checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if user.role not in roles:
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError("Brak uprawnień do wykonania tej operacji", error_code="INSUFFICIENT_ROLE")
        return user

    return _checker
