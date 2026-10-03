"""
Serwis aplikacyjny modułu Użytkownicy i Bezpieczeństwo.

Implementuje logikę przypadków użycia UC-B02 - UC-B10 zgodnie z regułami
biznesowymi opisanymi w sekcji 3.5 dokumentu:
  RB-B1: unikalność adresu e-mail + ochrona przed enumeracją kont,
  RB-B2: złożoność hasła (min. 8 zn., cyfra, znak specjalny),
  RB-B4: blokada konta po przekroczeniu limitu nieudanych logowań,
  RB-B6: unikalność numeru telefonu po weryfikacji SMS.

Uwaga: wysyłka e-mail/SMS oraz broker zdarzeń są poza zakresem tego
szkieletu - NotificationPort i AccountEventPublisher są tu zastąpione
prostymi implementacjami "no-op"/logującymi, gotowymi do podmiany.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
    ValidationFailedError,
)
from app.core.security import (
    create_access_token,
    generate_one_time_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.users.domain.models import OutboxEvent, RefreshToken, StudentProfile, TutorProfile, UserAccount
from app.modules.users.infrastructure.repositories import TokenRepository, UserRepository

settings = get_settings()


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.tokens = TokenRepository(db)

    # --- Outbox (Transactional Outbox pattern, sekcja 3.8) --------------

    def _emit_event(self, event_type: str, aggregate_id: uuid.UUID, payload: dict) -> None:
        event = OutboxEvent(
            event_type=event_type,
            aggregate_type="UserAccount",
            aggregate_id=aggregate_id,
            payload=payload,
        )
        self.db.add(event)

    # --- UC-B02: Rejestracja konta --------------------------------------

    def register(self, email: str, password: str, first_name: str, last_name: str, role: str) -> UserAccount:
        email = email.lower()
        if self.users.find_by_email(email) is not None:
            # RB-B1 dopuszcza jawny 409 tutaj (w przeciwieństwie do forgot-password,
            # gdzie ochrona przed enumeracją wymaga odpowiedzi nieodróżnialnej od sukcesu).
            raise ConflictError("Konto z tym adresem e-mail już istnieje", error_code="EMAIL_ALREADY_EXISTS")

        account = UserAccount(
            email=email,
            password_hash=hash_password(password),
            role=role,
            status="PENDING_ACTIVATION",
            verification_status="UNVERIFIED",
            activation_token=generate_one_time_token(),
            activation_token_expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.activation_token_expire_hours),
        )
        self.users.save(account)

        if role == "TUTOR":
            self.db.add(TutorProfile(user_id=account.id, first_name=first_name, last_name=last_name))
        else:
            self.db.add(StudentProfile(user_id=account.id, first_name=first_name, last_name=last_name))

        self._emit_event(
            "AccountCreatedEvent",
            account.id,
            {"userId": str(account.id), "email": account.email, "role": account.role},
        )
        self.db.commit()
        self.db.refresh(account)
        return account

    # --- Aktywacja konta (kliknięcie linku z e-maila) --------------------

    def activate_account(self, token: str) -> UserAccount:
        account = self.users.find_by_activation_token(token)
        if account is None:
            raise NotFoundError("Nieprawidłowy token aktywacyjny", error_code="ACTIVATION_TOKEN_INVALID")
        if account.activation_token_expires_at and account.activation_token_expires_at < datetime.now(timezone.utc):
            raise ValidationFailedError("Link aktywacyjny wygasł", error_code="ACTIVATION_TOKEN_EXPIRED")

        account.status = "ACTIVE"
        account.activation_token = None
        account.activation_token_expires_at = None
        self._emit_event("AccountActivatedEvent", account.id, {"userId": str(account.id)})
        self.db.commit()
        self.db.refresh(account)
        return account

    # --- UC-B03: Logowanie ------------------------------------------------

    def login(self, email: str, password: str, remember_me: bool = False) -> tuple[UserAccount, str, str]:
        email = email.lower()
        account = self.users.find_by_email(email)

        # RB-B1: odpowiedź celowo nieodróżnialna od "błędne hasło", żeby nie ujawniać
        # czy dany e-mail istnieje w systemie.
        generic_error = UnauthorizedError(
            "Nieprawidłowy adres e-mail lub hasło", error_code="INVALID_CREDENTIALS"
        )

        if account is None:
            raise generic_error

        # RB-B4: blokada konta po przekroczeniu limitu nieudanych prób logowania.
        now = datetime.now(timezone.utc)
        if account.locked_until and account.locked_until > now:
            raise TooManyRequestsError(
                f"Konto tymczasowo zablokowane do {account.locked_until.isoformat()}",
                error_code="ACCOUNT_TEMPORARILY_LOCKED",
            )

        if account.status in ("SUSPENDED", "BLOCKED", "DELETED"):
            raise ForbiddenError("Konto zablokowane przez administratora", error_code="ACCOUNT_BLOCKED")

        if account.status == "PENDING_ACTIVATION":
            raise ForbiddenError("Konto nie zostało aktywowane", error_code="ACCOUNT_NOT_ACTIVATED")

        if not verify_password(password, account.password_hash):
            account.failed_login_attempts += 1
            if account.failed_login_attempts >= settings.max_failed_login_attempts:
                account.locked_until = now + timedelta(minutes=settings.account_lock_minutes)
            self.db.commit()
            raise generic_error

        # Sukces logowania: reset licznika, wydanie tokenów.
        account.failed_login_attempts = 0
        account.locked_until = None
        access_token = create_access_token(str(account.id), account.role)
        refresh_token_plain = self._issue_refresh_token(account.id, remember_me)
        self.db.commit()
        self.db.refresh(account)
        return account, access_token, refresh_token_plain

    def _issue_refresh_token(self, user_id: uuid.UUID, remember_me: bool) -> str:
        plain = generate_refresh_token()
        days = settings.refresh_token_expire_days_remember_me if remember_me else settings.refresh_token_expire_days
        token = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(plain),
            expires_at=datetime.now(timezone.utc) + timedelta(days=days),
        )
        self.tokens.save(token)
        return plain

    # --- POST /auth/refresh ------------------------------------------------

    def refresh(self, refresh_token_plain: str) -> tuple[str, str]:
        token_hash = hash_token(refresh_token_plain)
        stored = self.tokens.find_by_hash(token_hash)
        if stored is None or stored.revoked or stored.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("Token odświeżający nieprawidłowy lub wygasły", error_code="REFRESH_TOKEN_INVALID")

        account = self.users.find_by_id(stored.user_id)
        if account is None or account.status in ("SUSPENDED", "BLOCKED", "DELETED"):
            raise ForbiddenError("Konto niedostępne", error_code="ACCOUNT_BLOCKED")

        # Rotacja refresh tokenu: unieważnij stary, wydaj nowy.
        self.tokens.revoke_by_hash(token_hash, reason="ROTATED")
        new_refresh = self._issue_refresh_token(account.id, remember_me=False)
        new_access = create_access_token(str(account.id), account.role)
        self.db.commit()
        return new_access, new_refresh

    # --- UC-B05: Wylogowanie -------------------------------------------------

    def logout(self, refresh_token_plain: str) -> None:
        self.tokens.revoke_by_hash(hash_token(refresh_token_plain), reason="LOGOUT")
        self.db.commit()

    # --- UC-B07: Zmiana hasła ------------------------------------------------

    def change_password(self, account: UserAccount, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, account.password_hash):
            raise ValidationFailedError("Bieżące hasło jest nieprawidłowe", error_code="CURRENT_PASSWORD_INVALID")
        account.password_hash = hash_password(new_password)
        self.tokens.revoke_all_for_user(account.id, reason="PASSWORD_CHANGE")
        self._emit_event("PasswordChangedEvent", account.id, {"userId": str(account.id)})
        self.db.commit()

    # --- UC-B08: Reset hasła (żądanie + wykonanie) --------------------------

    def forgot_password(self, email: str) -> None:
        """RB-B1: zawsze zwraca sukces, niezależnie czy e-mail istnieje (ochrona przed enumeracją)."""
        account = self.users.find_by_email(email.lower())
        if account is not None:
            account.password_reset_token = generate_one_time_token()
            account.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
            self.db.commit()
        # W obu przypadkach (konto istnieje / nie istnieje) odpowiedź API jest identyczna.

    def reset_password(self, token: str, new_password: str) -> None:
        account = self.users.find_by_password_reset_token(token)
        if account is None or (
            account.password_reset_expires_at and account.password_reset_expires_at < datetime.now(timezone.utc)
        ):
            raise ValidationFailedError("Token resetu hasła nieprawidłowy lub wygasły", error_code="RESET_TOKEN_INVALID")

        account.password_hash = hash_password(new_password)
        account.password_reset_token = None
        account.password_reset_expires_at = None
        self.tokens.revoke_all_for_user(account.id, reason="PASSWORD_RESET")
        self._emit_event("PasswordChangedEvent", account.id, {"userId": str(account.id)})
        self.db.commit()

    # --- UC-B06: Edycja profilu ---------------------------------------------

    def update_profile(self, account: UserAccount, data: dict) -> UserAccount:
        if account.role == "TUTOR":
            profile = account.tutor_profile
            editable = {
                "firstName": "first_name", "lastName": "last_name", "avatarUrl": "avatar_url",
                "bio": "bio", "subjects": "subjects", "hourlyRate": "hourly_rate",
                "education": "education", "experienceYears": "experience_years",
            }
        else:
            profile = account.student_profile
            editable = {
                "firstName": "first_name", "lastName": "last_name", "avatarUrl": "avatar_url",
                "learningGoals": "learning_goals", "subjects": "subjects",
                "educationLevel": "education_level",
            }

        if profile is None:
            raise NotFoundError("Profil użytkownika nie istnieje", error_code="PROFILE_NOT_FOUND")

        for field, attr in editable.items():
            if field in data and data[field] is not None:
                setattr(profile, attr, data[field])

        self.db.commit()
        self.db.refresh(account)
        return account

    # --- UC-B09: Weryfikacja tożsamości (SMS) --------------------------------

    def verify_phone(self, account: UserAccount, phone_number: str, sms_code: str) -> UserAccount:
        # Uwaga: rzeczywista wysyłka/weryfikacja kodu SMS jest poza zakresem
        # tego szkieletu (integracja z zewnętrznym dostawcą SMS).
        if sms_code != "000000":  # placeholder do podmiany na realną integrację
            raise ValidationFailedError("Nieprawidłowy kod SMS", error_code="SMS_CODE_INVALID")

        existing = self.users.find_by_email  # no-op, unikalność phone_number wymuszona przez UNIQUE w DB
        account.phone_number = phone_number
        account.verification_status = "PHONE_VERIFIED"
        self._emit_event("AccountActivatedEvent", account.id, {"userId": str(account.id), "phoneVerified": True})
        self.db.commit()
        self.db.refresh(account)
        return account

    # --- UC-B10: Usunięcie konta (soft delete) -------------------------------

    def delete_account(self, account: UserAccount) -> None:
        account.status = "PENDING_DELETION"
        account.deleted_at = datetime.now(timezone.utc)
        # Anonimizacja danych osobowych (finalizeDeletion) - uproszczona wersja:
        account.email = f"deleted-{account.id}@anonymized.local"
        account.phone_number = None
        account.oauth_subject = None
        self.tokens.revoke_all_for_user(account.id, reason="ACCOUNT_DELETED")
        self._emit_event("AccountDeactivatedEvent", account.id, {"userId": str(account.id)})
        self.db.commit()
