"""
Porty domenowe modułu Rezerwacji: UserPort (autoryzacja tożsamości,
sekcja 6.6.5 - "moduł Użytkowników przez UserPort") oraz
PaymentGatewayAdapter (granica adaptera płatniczego, sekcja 6.6.6).

PaymentGatewayAdapter jest tu zasymulowany synchronicznie (zawsze
sukces, brak realnego operatora) - jedyny komponent modułu, który w
docelowej wersji rozmawia z zewnętrznym systemem (np. Stripe/PayU).
Podmiana implementacji tej klasy na realną integrację nie wymaga zmian
w BookingService, ponieważ ten zależy wyłącznie od interfejsu poniżej.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.users.infrastructure.repositories import UserRepository


class UserPort:
    def __init__(self, db: Session):
        self._users = UserRepository(db)

    def is_account_active(self, user_id: uuid.UUID) -> bool:
        account = self._users.find_by_id(user_id)
        return account is not None and account.status not in ("SUSPENDED", "BLOCKED", "DELETED")


@dataclass
class PaymentResult:
    succeeded: bool
    external_id: str


@dataclass
class RefundResult:
    succeeded: bool


class PaymentGatewayAdapter:
    """
    Symulowany operator płatności. W realnej integracji: wywołanie
    synchroniczne + oczekiwanie na callback (W1/W2 z UC-R02 są
    absorbowane wewnątrz adaptera - logika domenowa widzi tylko wynik).
    """

    def charge(self, amount: float, currency: str, method_token: str | None, idempotency_key: str) -> PaymentResult:
        # TODO: integracja z realnym operatorem (np. Stripe PaymentIntents).
        return PaymentResult(succeeded=True, external_id=f"sim_{uuid.uuid4().hex[:16]}")

    def refund(self, amount: float, external_payment_id: str | None) -> RefundResult:
        # TODO: mechanizm ponowień z wykładniczym opóźnieniem + emisja RefundFailedEvent
        # po wyczerpaniu prób (sekcja 6.6.5) - w tym szkielecie zawsze sukces.
        return RefundResult(succeeded=True)
