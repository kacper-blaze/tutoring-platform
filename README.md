# System zarządzania platformą korepetycji online — szkielet projektu

Szkielet backendu wygenerowany na podstawie specyfikacji projektowej
(dokument Milestone M5, 167 stron). Stack: **Python 3.12 + FastAPI +
SQLAlchemy 2.0 + PostgreSQL + Alembic**.

## Status implementacji

| Moduł (wg specyfikacji)                          | Status                                   |
|---------------------------------------------------|-------------------------------------------|
| 1. Użytkownicy i Bezpieczeństwo (sekcja 3)         | ✅ Zaimplementowany (UC-B02–UC-B10)       |
| 2. Katalog i Wyszukiwanie Ofert (sekcja 4)         | ✅ Zaimplementowany (UC-K01–UC-K11)       |
| 3. Planowanie i dostępność (sekcja 5)              | ✅ Zaimplementowany (UC-P01–UC-P03)       |
| 4. Rezerwacje i Płatności (sekcja 6)               | ✅ Zaimplementowany (UC-R01–UC-R06)       |
| 5. Administracja i System (sekcja 7)               | ✅ Zaimplementowany (UC-A01–UC-A03 + reports) |

**Wszystkie pięć modułów przetestowane end-to-end** przez realne wywołania HTTP
na żywym serwerze z PostgreSQL, włącznie z pełnym cross-modułowym przepływem:
rejestracja → publikacja oferty (Katalog czyta profil z Users przez port) →
wyszukiwanie w katalogu → zdefiniowanie grafiku (Planowanie generuje sloty) →
rezerwacja terminu (Rezerwacje blokują slot przez `SchedulingPort`) → płatność
(idempotentna) → potwierdzenie terminu → opinia → moderacja opinii przez admina
→ blokada konta z kaskadowym unieważnieniem tokenów → zgłoszenie → anulowanie
rezerwacji z automatycznym zwrotem (RB5) → wygasanie nieopłaconej rezerwacji.

## Architektura integracji między modułami

Moduły komunikują się WYŁĄCZNIE przez wąskie porty (interfejsy), nigdy przez
bezpośrednie zapytania SQL do cudzych tabel - zgodnie z zasadą ze specyfikacji:

- `catalog/infrastructure/ports.py::TutorProfilePort` - Katalog czyta dane
  profilowe korepetytora z modułu Users.
- `planning/infrastructure/ports.py::SchedulingPort` - Rezerwacje rezerwują/
  zwalniają terminy w module Planowania (atomowy optimistic locking).
- `booking/infrastructure/ports.py::UserPort` - Rezerwacje sprawdzają status
  konta w module Users.
- `admin/application/admin_service.py` - Administracja moderuje opinie
  (moduł Katalog) i zarządza kontami (moduł Users) przez ich repozytoria.

W tym szkielecie wszystkie moduły działają w jednym procesie (modularny
monolit, wspólna baza danych) - przy ewentualnym wydzieleniu do osobnych
usług zmienia się tylko implementacja portów (na wywołania HTTP/gRPC/kolejkę),
logika domenowa pozostaje bez zmian.

## Rzeczy celowo uproszczone względem pełnej specyfikacji

- **PaymentGatewayAdapter** (`booking/infrastructure/ports.py`) jest
  zasymulowany - zawsze zwraca sukces. Podmiana na realnego operatora
  (Stripe/PayU) nie wymaga zmian w `BookingService`.
- **Wygasanie rezerwacji** jest leniwe (sprawdzane przy próbie płatności) -
  `BookingService.expire_stale_bookings()` jest gotowe do podpięcia pod
  scheduler/cron/worker dla wygasania proaktywnego.
- **Moduł Administracja**: zaimplementowany podzbiór (user_admin_metadata,
  admin_actions, audit_log, reports). Pominięte: dispute_cases,
  platform_config, notification_templates/log - TODO w kodzie.
- **Kaskadowe anulowanie rezerwacji przy blokadzie konta** (autoCancelBookings)
  nie jest zaimplementowane - endpoint zwraca `cancelledBookings: 0`.
- Brak Redis/cache, brokera zdarzeń (worker do outbox), read-repliki -
  niepotrzebne dla MVP, ale outbox (`outbox_events`, `booking_domain_events`)
  jest już zapisywany i gotowy do podpięcia workera.
- Wyszukiwanie w katalogu używa `ILIKE` zamiast pełnotekstowego
  `tsvector`/`tsquery` z indeksem GIN (sekcja 4.10).

## Struktura projektu

```
app/
  core/               # config, baza danych, bezpieczeństwo (JWT/bcrypt), wyjątki, typy cross-DB
  modules/
    users/            # Użytkownicy i Bezpieczeństwo (rejestracja, JWT, profile)
    catalog/          # Katalog i Wyszukiwanie (oferty, opinie, ulubieni)
    planning/         # Planowanie i Dostępność (grafiki, sloty, SchedulingPort)
    booking/          # Rezerwacje i Płatności (bookingi, płatności, zwroty)
    admin/            # Administracja i System (moderacja, blokady, audyt, zgłoszenia)
    (każdy moduł ma tę samą strukturę: domain/ infrastructure/ application/ api/)
  main.py             # punkt wejścia, rejestracja routerów, obsługa błędów
alembic/              # migracje bazy danych
requirements.txt
.env.example
```

Architektura modułu Users odzwierciedla podział z dokumentu: `domain`
(encje i reguły), `infrastructure` (dostęp do danych), `application`
(przypadki użycia), `api` (kontrakty REST) — każdy kolejny moduł powinien
być rozbudowywany w tym samym schemacie.

## Uruchomienie lokalne

### 1. Wymagania
- Python 3.12+
- PostgreSQL 14+ (lub SQLite do szybkich testów — patrz `.env.example`)

### 2. Instalacja

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Konfiguracja

```bash
cp .env.example .env
# edytuj .env - ustaw DATABASE_URL i JWT_SECRET_KEY
```

Do szybkiego developmentu bez instalowania PostgreSQL można w `.env`
odkomentować `DATABASE_URL=sqlite:///./dev.db` — modele są napisane w
sposób niezależny od silnika bazy (patrz `app/core/types.py`).

### 4. Baza danych

```bash
# Utworzenie bazy (jeśli używasz PostgreSQL lokalnie):
createdb tutoring_platform

# Migracje:
alembic upgrade head
```

### 5. Start serwera

```bash
uvicorn app.main:app --reload --port 8000
```

Dokumentacja API (Swagger UI): http://localhost:8000/docs
Health check: http://localhost:8000/health

### 6. Frontend (opcjonalnie)

Prosty frontend w React + Vite konsumujący to API — patrz
[`frontend/README.md`](frontend/README.md). W skrócie:

```bash
cd frontend
npm install
npm run dev
```

Otwórz `http://localhost:5173` (backend musi działać na porcie 8000).

## Przykładowy przepływ (curl)

```bash
# Rejestracja
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"jan@example.com","password":"Haslo#2026","firstName":"Jan","lastName":"Kowalski","role":"STUDENT"}'

# Aktywacja (token z odpowiedzi/DB - docelowo z e-maila)
curl http://localhost:8000/api/v1/auth/activate/{token}

# Logowanie
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"jan@example.com","password":"Haslo#2026"}'

# Endpoint chroniony (użyj accessToken z odpowiedzi logowania)
curl http://localhost:8000/api/v1/users/me -H "Authorization: Bearer {accessToken}"
```

## Migracje (Alembic)

```bash
# Nowa migracja po zmianie modeli:
alembic revision --autogenerate -m "opis zmiany"

# Zastosowanie migracji:
alembic upgrade head
```

**Uwaga:** po `alembic revision --autogenerate` sprawdź wygenerowany plik
w `alembic/versions/` — jeśli używasz customowych typów z
`app/core/types.py` (GUID, StringArray), może być potrzebny ręczny import
`import app.core.types` na górze pliku migracji (autogenerate go czasem
pomija).

## Kolejne kroki

Wszystkie pięć modułów backendu (sekcje 3–7 specyfikacji) jest już
zaimplementowanych i przetestowanych end-to-end — patrz tabela "Status
implementacji" wyżej. Pozostało:

1. **Testy automatyczne (pytest) i CI** — na razie moduły zweryfikowano
   ręcznie przez żądania HTTP na żywym serwerze; brakuje pokrycia testami
   jednostkowymi/integracyjnymi i pipeline'u CI (np. GitHub Actions)
   uruchamiającego je automatycznie przy każdym pushu.
2. **Frontend** — katalog `frontend/` zawiera prostą aplikację React
   (Vite) konsumującą to API: przeglądanie katalogu, rejestracja/logowanie,
   profil korepetytora, rezerwacja i płatność, panel korepetytora
   (oferty, grafik). Patrz `frontend/README.md`.
3. Pełnotekstowe wyszukiwanie PostgreSQL (`tsvector`/`tsquery` + GIN)
   zamiast obecnego `ILIKE` (moduł Katalog, sekcja 4.10).
4. Worker publikujący zdarzenia z tabel `outbox_events`/
   `booking_domain_events` do brokera (obecnie tylko zapisywane,
   nieodczytywane).
5. Realna integracja płatnicza (Stripe/PayU) w miejsce symulowanego
   `PaymentGatewayAdapter`.
6. Kaskadowe anulowanie aktywnych rezerwacji przy blokadzie konta
   (`admin.block_user` — obecnie `cancelledBookings` zawsze 0).
