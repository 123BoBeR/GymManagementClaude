# 🏋️ GymManagement

Aplikacja webowa do zarządzania siłownią - członkowie, trenerzy, zajęcia grupowe, rezerwacje, lista oczekujących, płatności i sprzęt. Zbudowana na Pythonie z Flaskiem i SQLite, z warstwą serwisową i wzorcami projektowymi (Strategy, Factory, Observer, Service Layer). Działa lokalnie, nie wymaga zewnętrznych serwisów.

---

## 🛠️ Stack

| Warstwa   | Technologia                             |
|-----------|-----------------------------------------|
| Backend   | Python 3.12+, Flask 3.0, blueprinty     |
| Baza      | SQLite / PostgreSQL (Flask-SQLAlchemy)  |
| Migracje  | Flask-Migrate / Alembic (tryb batch)    |
| Auth      | Sesje, hasła PBKDF2 (Werkzeug), reset hasła tokenem |
| Bezpiec.  | CSRF tokeny (Flask-WTF), rate-limiting (Flask-Limiter), nagłówki bezpieczeństwa |
| Config    | Zmienne środowiskowe (python-dotenv)    |
| Frontend  | Jinja2 + Bootstrap 5 + Chart.js + dark mode |
| Wzorce    | Strategy, Factory, Observer, Service Layer, Decorator |
| Testy     | pytest (154 testy)                      |

---

## 🚀 Jak uruchomić

```bash
# 1. Zainstaluj zależności
pip install -r requirements.txt

# 2. Skonfiguruj środowisko
cp .env.example .env   # i ustaw SECRET_KEY

# 3. Wypełnij bazę danymi demo
python seed.py

# 4. Odpal serwer
python app.py
```

Aplikacja działa pod `http://127.0.0.1:5000`.

> `seed.py` tworzy schemat z modeli (`create_all`) i wypełnia danymi demo — wygodne do dewelopmentu.
> W produkcji schemat zakładaj i rozwijaj migracjami (poniżej), nie `seed.py`.

### 🗄️ Migracje bazy (Flask-Migrate / Alembic)

Schemat jest wersjonowany migracjami. Typowy przepływ:

```bash
export FLASK_APP=app.py          # Windows PowerShell: $env:FLASK_APP="app.py"

flask db upgrade                 # załóż / zaktualizuj schemat do najnowszej wersji
flask db migrate -m "opis"       # wygeneruj migrację po zmianie modeli
flask db current                 # pokaż aktualną wersję
```

Migracje SQLite działają w trybie *batch* (`render_as_batch=True`) — pozwala to
dokładać/zmieniać ograniczenia (np. `UniqueConstraint` na płatnościach), których
SQLite nie obsługuje przez zwykłe `ALTER TABLE`.

Jeśli zseedowałeś bazę przez `seed.py` i chcesz ją oznaczyć jako zmigrowaną:
`flask db stamp head`.

### Konta demo

| Rola   | Login                 | Hasło       |
|--------|-----------------------|-------------|
| Admin  | `admin`               | `admin123`  |
| Trener | `jan.kowalski`        | `trener123` |
| Trener | `anna.nowak`          | `trener123` |
| Trener | `piotr.wisniewski`    | `trener123` |
| Trener | `marta.wojcik`        | `trener123` |
| Klient | `tomasz.krol`         | `klient123` |
| Klient | `ewa.dabrowska`       | `klient123` |
| Klient | `michal.kowalczyk`    | `klient123` |
| Klient | `karolina.szymanska`  | `klient123` |

---

## ✅ Funkcje

### Bezpieczeństwo i architektura
- CSRF tokeny we wszystkich formularzach POST (Flask-WTF)
- Hasła hashowane PBKDF2, klucze aplikacji w `.env`
- Świadome strefy czasowe (`datetime.now(timezone.utc)`)
- Kod podzielony na blueprinty: `auth`, `admin`, `trainer`, `client`
- Fabryka `create_app(test_config)`, współdzielone rozszerzenia w `extensions.py`
- Logika biznesowa w warstwie serwisowej (`services.py`) — oddzielona od tras
- Nowoczesne API SQLAlchemy 2.x (`db.get_or_404`, `db.session.get`)
- Hardening produkcyjny: `SECRET_KEY` i `debug` za zmiennymi środowiskowymi, bezpieczne ciasteczka sesji (HttpOnly/SameSite/Secure), nagłówki `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- Schemat bazy wersjonowany migracjami (Flask-Migrate / Alembic)
- Tryb ciemny (toggle w sidebarze, zapamiętany w localStorage, bez migotania)
- Responsywny layout — off-canvas sidebar z hamburgerem na telefonach, tabele przewijane poziomo
- Strona **Kontakt** dla wszystkich ról; admin zarządza opcjami kontaktu (dodaj/usuń)
- Własna strona 404

### Logowanie i role
- Sesje z trzema rolami: **Admin**, **Trener**, **Klient**
- Dekoratory na routach blokują nieautoryzowany dostęp
- Zmiana hasła dostępna z sidebara dla każdej roli
- **Rejestracja klienta** (self-signup) — publiczny `/register`, auto-login wg konwencji, karnet od pierwszego okresu, auto-zalogowanie
- **Reset hasła** ("zapomniałem hasła") — jednorazowy token z TTL 60 min; anty-enumeracja kont
- **Rate-limiting logowania** (10/min) z dedykowaną stroną 429
- **Powiadomienia** — dzwonek z licznikiem w sidebarze + strona `/notifications` (awans z kolejki, potwierdzenie płatności, wygasający karnet)

### Panel Admina
- **Dashboard** - statystyki na żywo + 3 wykresy Chart.js (przychód 6 mies., podział karnetów, top 5 zajęć) + alert gdy sprzęt broken/maintenance + feed ostatnich rezerwacji
- **Członkowie** - pełny CRUD z wyszukiwarką i filtrem po karnecie; szybkie odnowienie karnetu (modal +1m/+3m/+1 rok); reset hasła; historia płatności per klient; eksport do CSV
- **Trenerzy** - lista z edycją danych (modal)
- **Zajęcia** - workflow zatwierdzania: sekcja "Do zatwierdzenia" z przyciskami Zatwierdź / Odrzuć (modal z notatką); lista zatwierdzonych i odrzuconych; lista uczestników per zajęcia
- **Kolejka** - przegląd wszystkich oczekujących z pozycją FIFO i datą dodania
- **Sprzęt** - pełny CRUD (dodawanie, edycja, usuwanie) z kategorią i statusem
- **Płatności** - zestawienie wszystkich transakcji + statystyki przychodu; eksport CSV; paginacja
- **Wynagrodzenia** - raport kosztów pracy trenerów (stawka × godziny minionych, nieodwołanych sesji) per trener + suma
- **Raporty** - wykres słupkowy obłożenia tygodniowego (Chart.js, 8 tyg.) + ranking zajęć z wypełnieniem

### Panel Trenera
- **Dashboard** - zajęcia na dziś, unikalni klienci, alert o oczekujących propozycjach
- **Harmonogram** - trzy sekcje: zatwierdzone / oczekujące / odrzucone (z powodem i przyciskiem "Popraw i wyślij ponownie"); lista uczestników per zajęcia (z obecnościami)
- **Propozycja zajęć** - formularz z dniem, godziną, czasem trwania, częstotliwością (co 1-4 tygodnie) i datą startu
- **Obecność** - lista sesji ±7/14 dni; per sesja: toggle Był/a / Nieobecny / — dla każdego zapisanego
- **Podopieczni** - lista klientów ze statusem karnetu
- **Profil** - edycja specjalizacji i stawki godzinowej, zmiana hasła

### Panel Klienta
- **Dashboard** - status i dni do końca karnetu (alert przy <7 dniach), sekcja "Ten tydzień" z nadchodzącymi sesjami, przedłużanie karnetu (modal)
- **Zajęcia** - karty z nadchodzącymi sesjami (do 3); strona szczegółów sesji; zapis na konkretną sesję; lista oczekujących gdy pełne; guard przed przepełnieniem i konfliktami terminów
- **Rezerwacje** - historia z filtrem Aktywne / Wszystkie / Anulowane; oznaczenie minionych; anulowanie z auto-awansem kolejki; paginacja
- **Płatności** - rozliczenie w okresach (miesięczny: proporcja pierwszego niepełnego miesiąca; roczny: pełny rok kotwiczony do miesiąca dołączenia; dzienny: wejściówka na dziś); symulowany przelew bankowy z numerem TRF i animacją paska postępu
- **Frekwencja** - "Moja frekwencja": minione sesje z obecnością (był/nieobecny/nieoznaczone) + statystyki i % frekwencji
- **Profil** - edycja danych osobowych (modal); szczegóły karnetu

---

## 🧩 Wzorce projektowe (OOP)

Logika biznesowa żyje w `services.py` i jest faktycznie wywoływana z blueprintów (nie martwy kod).

| Wzorzec | Gdzie | Opis |
|---|---|---|
| **Strategy** | `services.py` | `SubscriptionStrategy` + `MonthlySubscription`, `AnnualSubscription`, `DayPassSubscription` — każdy karnet zna swoją etykietę, cenę, czas trwania i datę końca |
| **Factory** | `services.py` | `SubscriptionFactory.create(typ)` zwraca właściwą strategię bez wiedzy wywołującego o klasach |
| **Observer** | `services.py` | `BookingObserver` + `WaitlistObserver` — po anulowaniu rezerwacji `BookingService` powiadamia obserwatorów; `WaitlistObserver` awansuje pierwszą osobę z kolejki |
| **Service Layer** | `services.py` | `BookingService`, `WaitlistService`, `PaymentService`, `MemberService`, `UserService` — logika oddzielona od tras Flask |
| **Decorator** | `blueprints/utils.py` | `@role_required(rola)` strzeże tras wg roli z sesji |

---

## 🗃️ Model danych

> 📊 Pełny diagram ERD (12 tabel, wszystkie kolumny i relacje) renderujący się na
> GitHubie: **[DATABASE.md](DATABASE.md)**.

```
User ──< Member ──< Booking >── ClassSession >── GymClass >── Trainer
          │       < WaitlistEntry >──┘                    │
          └──< Payment                              Equipment
```

| Model | Opis |
|---|---|
| `User` | Konto auth; rola: `admin / trainer / client` |
| `Member` | Profil klienta; karnet: `monthly / annual / day_pass` |
| `Trainer` | Profil trenera: specjalizacja, stawka |
| `GymClass` | Definicja zajęć: harmonogram, częstotliwość, status (`pending / approved / rejected`), notatka odrzucenia |
| `ClassSession` | Konkretne wystąpienie zajęć z datą; auto-generowane na 12 tyg. po zatwierdzeniu |
| `Booking` | Rezerwacja klienta na sesję; status `confirmed / cancelled`; flaga obecności |
| `WaitlistEntry` | Kolejka oczekujących na pełną sesję; FIFO auto-awans przy anulowaniu |
| `Payment` | Płatność za okres rozliczeniowy; status `pending / completed`; numer TRF; data opłacenia; `UniqueConstraint(member_id, month_year)` |
| `Equipment` | Inwentarz sprzętu: kategoria, status, data zakupu |
| `ContactOption` | Dane kontaktowe siłowni (etykieta, wartość, ikona); CRUD po stronie admina |
| `Notification` | Powiadomienie użytkownika: treść, ikona, link, flaga przeczytania |
| `PasswordResetToken` | Jednorazowy token resetu hasła z czasem ważności (TTL 60 min) |

---

## 🧪 Testy

```bash
python -m pytest tests/ -v
```

**154 testy, 154 zielone:**

| Plik | Zakres |
|---|---|
| `test_auth.py` | Login, błędne dane, wylogowanie, kontrola dostępu per rola, rejestracja, reset hasła, hardening |
| `test_bookings.py` | Rezerwacja, duplikat, pełna sesja, anulowanie, konflikt terminów, waitlist + auto-awans, paginacja |
| `test_subscription.py` | Strategy + Factory: etykiety, ceny, czas trwania, daty końca karnetów |
| `test_payment.py` | PaymentService: numery TRF, initiate/confirm, okresy rozliczeniowe, proporcja, przychód |
| `test_services.py` | BookingService, MemberService, UserService (warstwa serwisowa), frekwencja |
| `test_waitlist.py` | WaitlistService + Observer: join/leave/pozycja, auto-awans, bramka karnetu |
| `test_admin.py` | CRUD trenerów/klientów, generacja loginów, kaskady usuwania, kontakt, payroll, paginacja |
| `test_sessions.py` | Odwoływanie sesji (guard własności) + rolling-generacja (idempotencja) |
| `test_notifications.py` | NotificationService: push, licznik nieprzeczytanych, awans z kolejki, wygasający karnet |
| `test_trainer.py` | Trasy trenera: propozycja/edycja zajęć, obecność, uczestnicy, profil (guardy własności) |
| `test_authz.py` | IDOR / autoryzacja pozioma: klient A nie ruszy płatności ani rezerwacji klienta B |

---

## ⚙️ Konfiguracja produkcyjna

**Zmienne środowiskowe** (`.env`):

```bash
FLASK_ENV=production     # wymusza obecność SECRET_KEY + bezpieczne ciasteczka (Secure)
SECRET_KEY=...           # w produkcji wymagany — brak = błąd startu (nie ma fallbacku)
# FLASK_DEBUG=1          # NIGDY w produkcji (zdalne wykonanie kodu)
```

**Przełączenie na PostgreSQL:**

```bash
# 1. Odkomentuj w requirements.txt:
#    psycopg2-binary==2.9.9

# 2. Ustaw w .env:
DATABASE_URL=postgresql://user:password@localhost:5432/gymmanagement
```

Żadne zmiany w kodzie aplikacji nie są potrzebne — schemat zakładasz migracjami (`flask db upgrade`).

### 🐳 Uruchomienie w Dockerze

Pełny stack (aplikacja na serwerze **waitress** + **PostgreSQL**) stawia się jedną komendą:

```bash
docker compose up --build
```

Aplikacja: `http://localhost:5000`. Kontener przy starcie sam zakłada/aktualizuje
schemat (`flask db upgrade`), a dane Postgresa trzyma w wolumenie `pgdata`.
Sam obraz aplikacji (bez Postgresa) zbudujesz i uruchomisz tak:

```bash
docker build -t gymmanagement .
docker run -p 5000:5000 -e SECRET_KEY=twoj-klucz gymmanagement
```

Produkcyjnie aplikację serwuje `waitress` (`wsgi:app`) — nie deweloperski `app.run`.
Lokalnie (bez Dockera) ten sam serwer odpalisz przez `python wsgi.py`.

### 🔁 CI (GitHub Actions)

`.github/workflows/ci.yml` uruchamia całą suitę `pytest` przy każdym `push` i `pull_request`
(na gałęzie `dev` / `develop` / `main` / `master`).

---

## 📁 Struktura projektu

```
├── app.py                  # create_app() factory + handlery 404/429 + CLI sessions-refresh
├── wsgi.py                 # punkt wejścia serwera produkcyjnego (waitress)
├── extensions.py           # db, csrf, migrate, limiter
├── models.py               # modele SQLAlchemy (z Payment, Notification, PasswordResetToken)
├── services.py             # warstwa serwisowa + wzorce OOP
├── constants.py            # wspólne stałe (kolejność dni tygodnia)
├── seed.py                 # dane demo
├── requirements.txt
├── .env.example
├── Dockerfile              # obraz produkcyjny (waitress)
├── docker-compose.yml      # aplikacja + PostgreSQL
├── .github/workflows/ci.yml # CI: pytest na push / PR
├── migrations/             # migracje Alembic (Flask-Migrate)
├── blueprints/
│   ├── auth.py             # /, /login, /logout, /change-password
│   ├── admin.py            # /admin/*  (członkowie, zajęcia, kolejka, płatności, raporty)
│   ├── trainer.py          # /trainer/* (harmonogram, obecność, uczestnicy, profil)
│   ├── client.py           # /client/*  (zajęcia, rezerwacje, płatności, profil)
│   ├── sessions.py         # generator sesji
│   └── utils.py            # dekoratory auth (@role_required)
├── templates/
│   ├── base.html           # sidebar, dark mode toggle, dzwonek powiadomień
│   ├── 404.html / 429.html
│   ├── login.html / register.html / forgot_password.html / reset_password.html
│   ├── notifications.html / contact.html / change_password.html
│   ├── admin/              # + payments, member_payments, class_members, waitlist, payroll
│   ├── trainer/            # + profile, class_members
│   └── client/             # + payments, payment_pay, session_detail, attendance
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_bookings.py
    ├── test_subscription.py
    ├── test_payment.py
    ├── test_services.py
    ├── test_waitlist.py
    ├── test_admin.py
    ├── test_sessions.py
    ├── test_notifications.py
    ├── test_trainer.py
    └── test_authz.py
```
