"""
Router /api/v1/users - endpointy prywatne zarządzania własnym kontem.

Kontrakty zgodne z sekcją 3.9 dokumentu (UC-B06, UC-B07, UC-B09, UC-B10).
Wszystkie endpointy wymagają ważnego access tokenu JWT.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.users.api.dependencies import get_current_user
from app.modules.users.api.schemas import (
    ChangePasswordRequest,
    UpdateProfileRequest,
    UserAccountResponse,
    VerifyPhoneRequest,
)
from app.modules.users.application.auth_service import AuthService
from app.modules.users.domain.models import UserAccount

router = APIRouter(prefix="/users", tags=["Users (Użytkownicy i Bezpieczeństwo)"])


@router.get("/me", response_model=UserAccountResponse)
def get_me(user: UserAccount = Depends(get_current_user)):
    return UserAccountResponse.model_validate(user)


@router.patch("/me/profile", response_model=UserAccountResponse)
def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    """UC-B06 - Edycja profilu (ucznia lub korepetytora, w zależności od roli)."""
    account = AuthService(db).update_profile(user, payload.model_dump(exclude_unset=True))
    return UserAccountResponse.model_validate(account)


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    """UC-B07 - Zmiana hasła (emituje PasswordChangedEvent, unieważnia wszystkie sesje)."""
    AuthService(db).change_password(user, payload.currentPassword, payload.newPassword)
    return {"message": "Hasło zostało zmienione. Wszystkie sesje zostały wylogowane."}


@router.post("/me/verify-phone", response_model=UserAccountResponse)
def verify_phone(
    payload: VerifyPhoneRequest,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    """UC-B09 - Weryfikacja tożsamości przez kod SMS (RB-B6)."""
    account = AuthService(db).verify_phone(user, payload.phoneNumber, payload.smsCode)
    return UserAccountResponse.model_validate(account)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    """UC-B10 - Usunięcie konta (soft-delete + anonimizacja, emituje AccountDeactivatedEvent)."""
    AuthService(db).delete_account(user)
