"""
Centralna konfiguracja aplikacji.

Wartości wczytywane są ze zmiennych środowiskowych / pliku .env.
Zgodnie z uwagą ze specyfikacji (moduł Użytkownicy i Bezpieczeństwo,
sekcja "Podmiana bazy H2/SQLite na produkcję (PostgreSQL) bez zmiany
serwisów") warstwa dostępu do danych jest niezależna od konkretnego
silnika bazy danych - do developmentu można użyć SQLite, docelowo
PostgreSQL, bez zmian w kodzie serwisów/repozytoriów.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Aplikacja ---
    app_name: str = "System zarządzania platformą korepetycji online"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    # --- Baza danych ---
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/tutoring_platform"

    # --- JWT (sekcja 3.9 - konwencje wspólne) ---
    jwt_secret_key: str = "change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    refresh_token_expire_days_remember_me: int = 30

    # --- RB-B4: blokada konta po nieudanych logowaniach ---
    max_failed_login_attempts: int = 5
    account_lock_minutes: int = 15

    # --- Aktywacja konta (UC-B02) ---
    activation_token_expire_hours: int = 24

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
