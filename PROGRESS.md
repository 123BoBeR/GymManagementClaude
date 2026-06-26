# 📈 Postęp prac — GymManagement

Dokument opisuje rzeczywisty przebieg prac nad projektem na podstawie historii commitów
gałęzi `dev` (45 commitów, 2026-05-19 → 2026-06-26). Stanowi bazę do sprawozdania.

---

## Oś czasu (skrót)

| Data | Faza | Kluczowy efekt | Testy |
|------|------|----------------|:-----:|
| 2026-05-19 | **0. Prototyp** | Pierwsza działająca wersja + README z roadmapą | — |
| 2026-06-04 | **1. Bezpieczeństwo i architektura** | Podział na blueprinty, CSRF, workflow zajęć, obecność, waitlista, raporty | 16 |
| 2026-06-14 | *(hotfix)* | Naprawa filtra `enumerate` w szablonie raportów | 16 |
| 2026-06-23 | **2. Wzorce OOP i płatności** | Warstwa serwisowa (Strategy/Factory/Observer), moduł płatności, dark mode | 51 |
| 2026-06-24 | **3. Dojrzałość funkcjonalna** | Auto-loginy, miesięczny model karnetu, strona Kontakt, responsywność | ~86 |
| 2026-06-25 | **4. Logika P0 + gotowość produkcyjna** | Naprawa dziur logicznych, migracje, rejestracja, powiadomienia, hardening | 138 |
| 2026-06-26 | **5. Testy, dokumentacja, konteneryzacja** | Domknięcie testów (trener + IDOR), README, Docker + CI | **154** |

> Rozwój pokrycia testami: **16 → 51 → 86 → 138 → 154**.

---

## Faza 0 — Prototyp (19.05.2026)

Pierwsza implementacja aplikacji do zarządzania siłownią oraz dokumentacja startowa.

- `dbdfb58` — pierwsza wersja aplikacji (modele, podstawowe widoki)
- `0c15366` — README po polsku z opisem funkcji i roadmapą
- `e1937ef` — wyszukiwarka i filtr po karnecie na liście członków

**Efekt:** działający szkielet aplikacji z podstawową obsługą członków.

---

## Faza 1 — Bezpieczeństwo i architektura (04.06.2026)

Największy pojedynczy etap prac — przejście od prototypu do uporządkowanej,
bezpiecznej aplikacji z pełnym zakresem funkcji dla trzech ról.

**Bezpieczeństwo i fundamenty:**
- `d657974` — ochrona CSRF we wszystkich formularzach POST (Flask-WTF)
- `23c0813` — `SECRET_KEY` i `DATABASE_URL` wyniesione do `.env`
- `21829c8` — poprawne strefy czasowe (`datetime.now(timezone.utc)`)
- `0418305` — **refaktoryzacja: rozbicie monolitu na blueprinty** `auth/admin/trainer/client` + fabryka `create_app()`

**Funkcje biznesowe:**
- `99d6796` — model `ClassSession` + workflow zatwierdzania zajęć przez admina
- `9bbde38` — walidacja konfliktu terminów przy rezerwacji
- `21b447a` — lista oczekujących na pełne sesje + auto-awans przy anulowaniu
- `23c7b5f` — oznaczanie obecności przez trenera
- `e68b12b` — szybkie odnawianie karnetu (modal +1m/+3m/+1 rok)
- `b17531a` / `5d6d312` — edycja propozycji zajęć (trener) i danych trenera (admin)
- `ae97788` — pełny CRUD sprzętu
- `da1ecb7` — raporty: wykres obłożenia tygodniowego + ranking zajęć
- `f0c2dee` — zmiana hasła (wszystkie role) + reset hasła klienta przez admina
- `d6085e6` — eksport listy członków do CSV

**Jakość:**
- `e89f77a` — **pierwsze testy pytest: 16** (autoryzacja + logika rezerwacji/waitlisty)
- `794ceb4` — konfiguracja PostgreSQL (`.env.example`, `requirements.txt`)

**Efekt:** bezpieczna, modularna aplikacja z workflow zajęć, obecnością, kolejką
oczekujących i raportami; pokrycie 16 testami.

---

## Hotfix (14.06.2026)

- `0d5f8c0` — rejestracja `enumerate` jako filtr Jinja2 (naprawa błędu strony raportów
  zgłoszonego przy uruchomieniu na innym środowisku).

---

## Faza 2 — Wzorce projektowe i płatności (23.06.2026)

Skok jakościowy: wydzielenie logiki biznesowej do warstwy serwisowej opartej na
wzorcach projektowych oraz wprowadzenie modułu płatności.

- `ea0891c` — **warstwa serwisowa OOP** (`services.py`): wzorce **Strategy** (typy karnetów),
  **Factory** (tworzenie strategii), **Observer** (awans z kolejki), **Service Layer**
  (logika oddzielona od tras); moduł płatności; tryb ciemny; **rozrost testów do 51**
- `801cf4a` — pełny CRUD trenerów w panelu admina + link do szczegółów sesji

**Efekt:** architektura z czytelnym podziałem odpowiedzialności i wzorcami OOP;
płatności; pokrycie 51 testami.

---

## Faza 3 — Dojrzałość funkcjonalna (24.06.2026)

Dopracowanie modelu domenowego i doświadczenia użytkownika.

- `757e406` — auto-generowane loginy (np. `j.kowalski`) + automatyczne wyliczanie
  ważności karnetu + wyszukiwarka trenerów
- `f25e972` — **miesięczny model karnetu** (rozliczenie w pełnych miesiącach zamiast dat)
- `ad09bca` — strona **Kontakt** (CRUD admina) + **responsywność mobilna** (off-canvas sidebar)
- `776e7e7` — eksport płatności do CSV, filtr sprzętu, naprawa strony 404 w trybie ciemnym

**Efekt:** spójny model karnetu, obsługa mobilna, pełniejszy panel admina.

---

## Faza 4 — Domknięcie logiki i gotowość produkcyjna (25.06.2026)

Najintensywniejszy dzień prac — audyt logiki, naprawa krytycznych dziur oraz
przygotowanie do wdrożenia produkcyjnego, plus zestaw nowych funkcji.

**Naprawa dziur logicznych (priorytet P0):**
- `b125122` — bramka aktywnego karnetu przy rezerwacji, odwoływanie pojedynczej sesji,
  rolling-generacja sesji (idempotentna), kaskady kluczy obcych przy usuwaniu

**Gotowość produkcyjna:**
- `0ea8b82` — hardening: `debug`/`SECRET_KEY` za zmiennymi środowiskowymi, bezpieczne
  ciasteczka sesji, nagłówki bezpieczeństwa
- `4a61854` — **migracje bazy danych** (Flask-Migrate / Alembic) + `UniqueConstraint` płatności
- `0278eab` — spójność płatności przy odnowieniu (wspólny upsert)
- `3a7c500` — rate-limiting logowania (Flask-Limiter)

**Nowe funkcje:**
- `918c1e9` — rejestracja klienta (self-signup) + reset hasła („zapomniałem hasła")
- `75d0a1e` — system powiadomień (pod wzorzec Observer)
- `63eee8e` — płatności w okresach rozliczeniowych + proporcja pierwszego okresu
- `c690003` — historia frekwencji klienta + raport wynagrodzeń trenerów

**Jakość kodu:**
- `f147063` — refaktoryzacja: wspólne stałe, usunięcie martwego kodu
- `5d978a7` — paginacja list (płatności, rezerwacje)

**Efekt:** aplikacja domknięta logicznie i gotowa produkcyjnie (migracje, hardening,
rate-limiting); pokrycie **138 testów**.

---

## Faza 5 — Testy, dokumentacja, konteneryzacja (26.06.2026)

- `bd0382d` — **domknięcie testów (B48):** trasy trenera (propozycja/edycja zajęć,
  obecność, uczestnicy, profil — z kontrolą własności) + testy IDOR (klient A nie sięgnie
  do danych klienta B) → **154 testy**; **aktualizacja README (B49)** w pełnej zgodności
  z kodem; **konteneryzacja (B39):** serwer produkcyjny waitress (`wsgi.py`),
  `Dockerfile`, `docker-compose.yml` (aplikacja + PostgreSQL), CI w GitHub Actions
  (pytest na każdy push/PR).

**Efekt:** komplet testów, dokumentacja zsynchronizowana z kodem, konfiguracja wdrożenia
i ciągła integracja.

---

## 🔄 Punkty zwrotne (zmiany kierunku)

W trakcie prac wystąpiło kilka momentów, w których przyjęty kierunek został zmieniony lub
przepisany — w odróżnieniu od liniowej rozbudowy funkcji. To one najlepiej obrazują ewolucję
projektu i decyzje projektowe.

### Architektura

- **Monolit → blueprinty** (04.06, `0418305`) — całość kodu znajdowała się początkowo
  w jednym `app.py`. Refaktoryzacja usunęła z niego 383 linie i rozbiła aplikację na moduły
  `auth/admin/trainer/client` oraz fabrykę `create_app()`.
- **Logika w trasach → warstwa serwisowa OOP** (23.06, `ea0891c`) — drugi, większy zwrot:
  logika biznesowa wpleciona dotąd w trasy Flaska została wydzielona do `services.py`
  (+383 linie), a trasy przepięte na serwisy ze wzorcami Strategy / Factory / Observer /
  Service Layer. Przejście z kodu proceduralnego na obiektowy.

### Model domenowy i funkcjonalność

- **Karnet w datach → model miesięczny** (24.06, `f25e972`) — zmiana sposobu liczenia
  ważności karnetu: z konkretnych dat na rozliczenie w pełnych miesiącach. Wymusiła
  przepisanie logiki subskrypcji oraz testów.
- **⭐ Płatności przepisane po feedbacku** (25.06, `63eee8e`) — **najczystszy punkt zwrotny,
  jedyny wymuszony zewnętrznym feedbackiem** (BACKLOG, „Sekcja 13 — Feedback"). Zgłoszone
  problemy: pełna kwota za niepełny pierwszy miesiąc, miesiące pokazywane „wstecz" sprzed
  założenia konta, karnet roczny prezentowany jako miesiące. Efekt: przepisanie na okresy
  rozliczeniowe z proporcją (`payable_periods` zastąpiło `months_for_member`,
  `record_completed` → `settle_period`; +189 linii w `services.py`, +100 w testach).
- **Konta tylko przez admina → samodzielna rejestracja** (25.06, `918c1e9`) — wcześniej konto
  klienta zakładał wyłącznie admin; dodano publiczny `/register` oraz reset hasła (+524 linie).
- **„Ciche" awansowanie z kolejki → powiadomienia** (25.06, `75d0a1e`) — awans z listy
  oczekujących odbywał się bez informowania użytkownika; wprowadzono system powiadomień (Observer).

### Stack — ewolucja, nie rewolucja

Stack nie został dramatycznie przełączony (Flask + SQLite od początku do końca) — przyrastał
o kolejne biblioteki. Jedyny zwrot wart wyróżnienia:

- **`db.create_all()` → migracje Alembic** (25.06, `4a61854`) — zmiana sposobu zakładania
  i rozwijania schematu bazy: z generowania z modeli na wersjonowane migracje (Flask-Migrate).
  W produkcji schemat zakłada się migracjami, nie `seed.py`.

Pozostałe zmiany stacku miały charakter **addytywny**: Flask-WTF (CSRF) i python-dotenv (04.06),
Flask-Limiter (rate-limiting, 25.06), waitress + Docker (serwer produkcyjny, 26.06).

---

## Stan obecny (na 2026-06-26)

**Zakres funkcjonalny — trzy role:**
- **Admin:** dashboard z wykresami, CRUD członków/trenerów/sprzętu, workflow zatwierdzania
  zajęć, kolejka oczekujących, płatności, raport wynagrodzeń, raporty obłożenia, eksport CSV
- **Trener:** harmonogram, propozycje zajęć, obecność, lista podopiecznych, profil
- **Klient:** rejestracja, rezerwacje, lista oczekujących, płatności w okresach,
  frekwencja, powiadomienia, przedłużanie karnetu

**Architektura i jakość:**
- Warstwa serwisowa OOP ze wzorcami: Strategy, Factory, Observer, Service Layer, Decorator
- Blueprinty + fabryka `create_app()`, migracje bazy (Alembic)
- Bezpieczeństwo: CSRF, hasła PBKDF2, rate-limiting, hardening produkcyjny, nagłówki
- **154 testy jednostkowe i integracyjne (100% zielonych)**
- CI (GitHub Actions) uruchamiające testy na każdy push
- Konfiguracja wdrożenia: Docker + docker-compose (PostgreSQL), serwer waitress

**Stack:** Python 3.12 · Flask 3.0 · SQLAlchemy · SQLite/PostgreSQL · Jinja2 + Bootstrap 5 +
Chart.js · pytest

---

## Podsumowanie liczbowe

| Metryka | Wartość |
|---------|---------|
| Okres prac | 2026-05-19 – 2026-06-26 (≈ 5 tygodni) |
| Liczba commitów (`dev`) | 45 |
| Liczba testów | 154 (z 0 → 16 → 51 → 138 → 154) |
| Role użytkowników | 3 (admin, trener, klient) |
| Modele danych | 11 |
| Wzorce projektowe | 5 (Strategy, Factory, Observer, Service Layer, Decorator) |

---

*Dokument wygenerowany na podstawie historii commitów gałęzi `dev`. Szczegółowy backlog
zadań z opisem realizacji: [BACKLOG.md](BACKLOG.md). Pełny opis funkcji: [README.md](README.md).*
