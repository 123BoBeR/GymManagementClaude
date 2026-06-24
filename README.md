# 🏋️ GymManagement

Aplikacja webowa do zarządzania siłownią - członkowie, trenerzy, zajęcia grupowe, rezerwacje, lista oczekujących, płatności i sprzęt. Zbudowana na Pythonie z Flaskiem i SQLite, z warstwą serwisową i wzorcami projektowymi (Strategy, Factory, Observer, Service Layer). Działa lokalnie, nie wymaga zewnętrznych serwisów.

---

## 🛠️ Stack

| Warstwa   | Technologia                             |
|-----------|-----------------------------------------|
| Backend   | Python 3.12+, Flask 3.0, blueprinty     |
| Baza      | SQLite / PostgreSQL (Flask-SQLAlchemy)  |
| Auth      | Sesje, hasła PBKDF2 (Werkzeug)          |
| Bezpiec.  | CSRF tokeny (Flask-WTF)                 |
| Config    | Zmienne środowiskowe (python-dotenv)    |
| Frontend  | Jinja2 + Bootstrap 5 + Chart.js + dark mode |
| Wzorce    | Strategy, Factory, Observer, Service Layer, Decorator |
| Testy     | pytest (67 testów)                      |

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
- Tryb ciemny (toggle w sidebarze, zapamiętany w localStorage, bez migotania)
- Responsywny layout — off-canvas sidebar z hamburgerem na telefonach, tabele przewijane poziomo
- Strona **Kontakt** dla wszystkich ról; admin zarządza opcjami kontaktu (dodaj/usuń)
- Własna strona 404

### Logowanie i role
- Sesje z trzema rolami: **Admin**, **Trener**, **Klient**
- Dekoratory na routach blokują nieautoryzowany dostęp
- Zmiana hasła dostępna z sidebara dla każdej roli

### Panel Admina
- **Dashboard** - statystyki na żywo + 3 wykresy Chart.js (przychód 6 mies., podział karnetów, top 5 zajęć) + alert gdy sprzęt broken/maintenance + feed ostatnich rezerwacji
- **Członkowie** - pełny CRUD z wyszukiwarką i filtrem po karnecie; szybkie odnowienie karnetu (modal +1m/+3m/+1 rok); reset hasła; historia płatności per klient; eksport do CSV
- **Trenerzy** - lista z edycją danych (modal)
- **Zajęcia** - workflow zatwierdzania: sekcja "Do zatwierdzenia" z przyciskami Zatwierdź / Odrzuć (modal z notatką); lista zatwierdzonych i odrzuconych; lista uczestników per zajęcia
- **Kolejka** - przegląd wszystkich oczekujących z pozycją FIFO i datą dodania
- **Sprzęt** - pełny CRUD (dodawanie, edycja, usuwanie) z kategorią i statusem
- **Płatności** - zestawienie wszystkich transakcji + statystyki przychodu
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
- **Rezerwacje** - historia z filtrem Aktywne / Wszystkie / Anulowane; oznaczenie minionych; anulowanie z auto-awansem kolejki
- **Płatności** - historia miesięczna; symulowany przelew bankowy z numerem TRF i animacją paska postępu
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
| `Payment` | Płatność za miesiąc; status `pending / completed`; numer TRF; data opłacenia |
| `Equipment` | Inwentarz sprzętu: kategoria, status, data zakupu |
| `ContactOption` | Dane kontaktowe siłowni (etykieta, wartość, ikona); CRUD po stronie admina |

---

## 🧪 Testy

```bash
python -m pytest tests/ -v
```

**67 testów, 67 zielonych:**

| Plik | Zakres |
|---|---|
| `test_auth.py` | Login, błędne dane, wylogowanie, kontrola dostępu per rola |
| `test_bookings.py` | Rezerwacja, duplikat, pełna sesja, anulowanie, konflikt terminów, waitlist + auto-awans |
| `test_subscription.py` | Strategy + Factory: etykiety, ceny, czas trwania, daty końca karnetów |
| `test_payment.py` | PaymentService: numery TRF, initiate/confirm, duplikaty, przychód |
| `test_services.py` | BookingService, MemberService, UserService (warstwa serwisowa) |
| `test_waitlist.py` | WaitlistService + Observer: join/leave/pozycja, auto-awans |

---

## ⚙️ Konfiguracja produkcyjna

Aby przełączyć na PostgreSQL:

```bash
# 1. Odkomentuj w requirements.txt:
#    psycopg2-binary==2.9.9

# 2. Ustaw w .env:
DATABASE_URL=postgresql://user:password@localhost:5432/gymmanagement
```

Żadne zmiany w kodzie aplikacji nie są potrzebne.

---

## 📁 Struktura projektu

```
├── app.py                  # create_app() factory + handler 404
├── extensions.py           # db, csrf
├── models.py               # modele SQLAlchemy (z Payment)
├── services.py             # warstwa serwisowa + wzorce OOP
├── seed.py                 # dane demo
├── requirements.txt
├── .env.example
├── blueprints/
│   ├── auth.py             # /, /login, /logout, /change-password
│   ├── admin.py            # /admin/*  (członkowie, zajęcia, kolejka, płatności, raporty)
│   ├── trainer.py          # /trainer/* (harmonogram, obecność, uczestnicy, profil)
│   ├── client.py           # /client/*  (zajęcia, rezerwacje, płatności, profil)
│   ├── sessions.py         # generator sesji
│   └── utils.py            # dekoratory auth (@role_required)
├── templates/
│   ├── base.html           # sidebar, dark mode toggle
│   ├── 404.html
│   ├── login.html
│   ├── change_password.html
│   ├── admin/              # + payments, member_payments, class_members, waitlist
│   ├── trainer/            # + profile, class_members
│   └── client/             # + payments, payment_pay, session_detail
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_bookings.py
    ├── test_subscription.py
    ├── test_payment.py
    ├── test_services.py
    └── test_waitlist.py
```
