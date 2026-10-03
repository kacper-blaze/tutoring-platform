"""
Wyjątki domenowe wspólne dla wszystkich modułów.

Kody błędów i statusy HTTP odpowiadają konwencji ze specyfikacji
(sekcja 3.9 "Konwencje wspólne"):
400 walidacja semantyczna, 401 brak/wygaśnięcie tokenu,
403 autoryzacja/konto zablokowane, 404 zasób nie istnieje,
409 konflikt, 422 walidacja syntaktyczna, 429 zbyt wiele prób,
503 zależny serwis niedostępny.
"""
from fastapi import status


class AppError(Exception):
    """Bazowy wyjątek aplikacyjny niosący kod błędu i status HTTP."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "ERROR"

    def __init__(self, message: str, *, error_code: str | None = None, details: list | None = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.error_code
        self.details = details or []


class ValidationFailedError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_FAILED"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"


class TooManyRequestsError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "TOO_MANY_REQUESTS"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "SERVICE_UNAVAILABLE"
