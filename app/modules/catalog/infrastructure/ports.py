"""
Porty domenowe modułu Katalogu - odczyt danych z innych modułów WYŁĄCZNIE
przez interfejs serwisu, nigdy bezpośrednim zapytaniem SQL do cudzych
tabel (zasada z sekcji 4.13 / 4.9 dokumentu).

W tym szkielecie wszystkie moduły działają w jednym procesie (modularny
monolit), więc port jest zaimplementowany jako wywołanie repozytorium
modułu Użytkowników w tej samej sesji DB - ale przez wąski, jawny
interfejs (nie przez import modelu ORM cudzego modułu w całej
aplikacji). Przy ewentualnym wydzieleniu modułów do osobnych usług
(mikroserwisów) zmienia się tylko implementacja tej klasy (na wywołanie
HTTP/gRPC), reszta modułu Katalogu pozostaje bez zmian.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.users.infrastructure.repositories import UserRepository


@dataclass
class TutorProfileView:
    tutor_id: uuid.UUID
    first_name: str
    last_name: str
    bio: str | None
    avatar_url: str | None
    subjects: list[str]


class TutorProfilePort:
    def __init__(self, db: Session):
        self._users = UserRepository(db)

    def get_tutor_profile(self, tutor_id: uuid.UUID) -> TutorProfileView | None:
        account = self._users.find_by_id(tutor_id)
        if account is None or account.role != "TUTOR" or account.tutor_profile is None:
            return None
        profile = account.tutor_profile
        return TutorProfileView(
            tutor_id=account.id,
            first_name=profile.first_name,
            last_name=profile.last_name,
            bio=profile.bio,
            avatar_url=profile.avatar_url,
            subjects=profile.subjects,
        )

    def tutor_exists(self, tutor_id: uuid.UUID) -> bool:
        account = self._users.find_by_id(tutor_id)
        return account is not None and account.role == "TUTOR"
