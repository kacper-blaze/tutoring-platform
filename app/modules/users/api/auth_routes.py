"""
Router /api/v1/auth - endpointy publiczne uwierzytelniania.

Kontrakty zgodne z sekcją 3.9 dokumentu (UC-B02, UC-B03, UC-B05, UC-B08).
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.modules.users.api.dependencies import get_current_user
from app.modules.users.api.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
)
from app.modules.users.application.auth_service import AuthService
from app.modules.users.domain.models import UserAccount

router = APIRouter(prefix="/auth", tags=["Auth (Użytkownicy i Bezpieczeństwo)"])
settings = get_settings()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """UC-B02 - Rejestracja konta ucznia lub korepetytora."""
    service = AuthService(db)
    account = service.register(
        email=payload.email,
        password=payload.password,
        first_name=payload.firstName,
        last_name=payload.lastName,
        role=payload.role,
    )
    return RegisterResponse(userId=account.id, email=account.email, status=account.status)


@router.get("/activate/{token}", status_code=status.HTTP_200_OK)
def activate_account(token: str, db: Session = Depends(get_db)):
    """Aktywacja konta po kliknięciu w link z e-maila (uzupełnienie UC-B02)."""
    service = AuthService(db)
    account = service.activate_account(token)
    return {"userId": str(account.id), "status": account.status, "message": "Konto zostało aktywowane"}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """UC-B03 - Logowanie do systemu."""
    service = AuthService(db)
    account, access_token, refresh_token = service.login(payload.email, payload.password, payload.rememberMe)
    return LoginResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=settings.access_token_expire_minutes * 60,
        role=account.role,
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Odświeżenie access tokenu; refresh token przesyłany wyłącznie w ciele żądania."""
    service = AuthService(db)
    access_token, new_refresh = service.refresh(payload.refreshToken)
    return RefreshResponse(
        accessToken=access_token,
        refreshToken=new_refresh,
        expiresIn=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    db: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
):
    """UC-B05 - Wylogowanie (unieważnienie refresh tokenu)."""
    AuthService(db).logout(payload.refreshToken)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """UC-B08 (krok 1) - RB-B1: odpowiedź zawsze identyczna, niezależnie od istnienia konta."""
    AuthService(db).forgot_password(payload.email)
    return {"message": "Jeśli konto istnieje, wysłano instrukcje resetu hasła"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """UC-B08 (krok 2) - ustawienie nowego hasła na podstawie tokenu resetu."""
    AuthService(db).reset_password(payload.token, payload.newPassword)
    return {"message": "Hasło zostało zmienione"}
