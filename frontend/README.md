# Frontend — System korepetycji (React + Vite)

Prosty, działający frontend konsumujący backend z `../app`. Pokrywa
główne przepływy: rejestrację/logowanie, przeglądanie katalogu,
profil korepetytora z rezerwacją i płatnością, panel korepetytora
(oferty + grafik) i historię rezerwacji ucznia.

**Czego nie ma** (świadomie pominięte, żeby nie rozdmuchiwać zakresu):
panel administratora, edycja profilu/zmiana hasła, lista ulubionych,
dodawanie opinii z poziomu UI (endpoint w backendzie istnieje i działa,
brakuje tylko formularza).

## Uruchomienie

Wymaga uruchomionego backendu (patrz `../README.md`) na porcie 8000.

```bash
cd frontend
npm install
npm run dev
```

Otwórz `http://localhost:5173`. Konfiguracja w `vite.config.js` proxuje
`/api/*` do `http://127.0.0.1:8000`, więc w developmencie nie trzeba
ustawiać CORS ani pełnych URL-i.

Jeśli backend działa pod innym adresem, zmień `target` w `vite.config.js`
albo zbuduj produkcyjnie (`npm run build`) i ustaw `CORS_ORIGINS` w `.env`
backendu na adres, pod którym serwujesz zbudowany frontend.

## Struktura

```
src/
  api/client.js          # fetch wrapper: JWT w nagłówku, auto-refresh na 401
  context/AuthContext.jsx # stan zalogowanego użytkownika (React Context)
  components/             # Navbar, ProtectedRoute
  pages/
    CatalogPage.jsx        # katalog ofert z filtrami (publiczny)
    LoginPage.jsx / RegisterPage.jsx
    TutorProfilePage.jsx   # profil, oferty, opinie, wybór slotu, płatność
    MyBookingsPage.jsx     # historia rezerwacji ucznia (opłać/anuluj)
    TutorDashboardPage.jsx # panel korepetytora: oferty + grafik
  styles/index.css         # system projektowy (design tokens, komponenty)
```

## Token JWT

Access i refresh token trzymane są w `localStorage`. Przy odpowiedzi 401
klient automatycznie próbuje odświeżyć token przez `/auth/refresh` i
ponawia żądanie raz — jeśli to się nie uda, sesja jest czyszczona.

## Build produkcyjny

```bash
npm run build
```

Wygenerowane pliki statyczne trafiają do `dist/` — można je wystawić
dowolnym serwerem plików statycznych (nginx, Vercel, itp.), pamiętając
o ustawieniu właściwego URL-a backendu (patrz wyżej) i `CORS_ORIGINS`.
