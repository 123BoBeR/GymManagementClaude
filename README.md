# GymApp

Aplikacja webowa do zarządzania siłownią — członkowie, trenerzy, zajęcia grupowe, rezerwacje, lista oczekujących, płatności i sprzęt. Projekt zaliczeniowy (Bazy Danych + Programowanie Obiektowe).

---

## Stack

| Warstwa  | Technologia                              |
|----------|------------------------------------------|
| Backend  | Python 3.14, Flask 3.0                   |
| Baza     | SQLite via Flask-SQLAlchemy 3.1          |
| Auth     | Sesje Flask, hasła hashowane Werkzeugiem |
| Frontend | Jinja2 + Bootstrap 5 + Bootstrap Icons  |
| Wykresy  | Chart.js 4.4                             |
| Testy    | pytest 9.0 — 92 testy                    |

---

## Uruchomienie

```bash
pip install -r requirements.txt
python seed.py      # wypełnij bazę danymi demo
python app.py       # serwer na http://127.0.0.1:5000
```

### Dane logowania

| Rola   | Login                | Hasło       |
|--------|----------------------|-------------|
| Admin  | `admin`              | `admin123`  |
| Trener | `jan.kowalski`       | `trener123` |
| Trener | `anna.nowak`         | `trener123` |
| Trener | `piotr.wisniewski`   | `trener123` |
| Trener | `marta.wojcik`       | `trener123` |
| Klient | `tomasz.krol`        | `klient123` |
| Klient | `ewa.dabrowska`      | `klient123` |
| Klient | `michal.kowalczyk`   | `klient123` |
| Klient | `karolina.szymanska` | `klient123` |

---

## Funkcje

### Panel Admina

- **Dashboard** — statystyki na żywo (członkowie, trenerzy, zajęcia, rezerwacje), wykresy Chart.js: przychody ostatnich 6 miesięcy, podział karnetów, top 5 zajęć; alerty o zepsutym / serwisowanym sprzęcie
- **Klienci** — pełny CRUD; wyszukiwarka po imieniu i filtr po typie karnetu (live JS); reset hasła klienta; szybkie przedłużenie karnetu (+1m / +3m / +1rok); historia płatności per klient; eksport listy do CSV
- **Trenerzy** — pełny CRUD
- **Zajęcia** — tygodniowy plan sorted pon–nd; dodawanie, edycja i usuwanie; lista uczestników per zajęcia z paskiem zajętości
- **Sprzęt** — inwentarz z kategorią, statusem i datą zakupu; CRUD
- **Płatności** — zestawienie wszystkich transakcji z podsumowaniem przychodu
- **Kolejka** — pełny podgląd listy oczekujących z pozycją per zajęcia

### Panel Trenera

- **Dashboard** — zajęcia na dziś, łączna liczba podopiecznych
- **Harmonogram** — plan pon–nd z obłożeniem i linkiem do listy uczestników każdych zajęć
- **Moi klienci** — lista zapisanych członków ze statusem karnetu
- **Profil** — edycja specjalizacji i stawki godzinowej; zmiana hasła

### Panel Klienta

- **Dashboard** — status karnetu z odliczaniem dni; sekcja „Ten tydzień" z nadchodzącymi zajęciami; banery ostrzegawcze przy wygasaniu
- **Zajęcia** — dwa widoki: siatka kart i tygodniowy grid pon–nd; rezerwacja i kolejka oczekujących; strona szczegółów zajęć
- **Rezerwacje** — historia z filtrem Aktywne / Wszystkie / Anulowane; anulowanie rezerwacji
- **Profil** — edycja danych osobowych; zmiana hasła
- **Płatności** — historia miesięczna; symulowany przelew bankowy z animacją (numer TRF, pasek postępu, potwierdzenie sukcesu)

### Logika biznesowa

- Walidacja konfliktu terminów — odrzuca rezerwację gdy klient ma już zajęcia w tym samym dniu i godzinie
- Lista oczekujących z automatycznym przydziałem miejsca po anulowaniu
- Guard przepełnienia zajęć i duplikatów
- Custom strona 404

---

## Wzorce projektowe (OOP)

| Wzorzec | Gdzie | Opis |
|---------|-------|------|
| **Strategy** | `services.py` | `SubscriptionStrategy` + `MonthlySubscription`, `AnnualSubscription`, `DayPassSubscription` — każdy typ karnetu implementuje `label()`, `duration_days()`, `end_date()` |
| **Factory** | `services.py` | `SubscriptionFactory.create(sub_type)` tworzy odpowiednią strategię na podstawie klucza tekstowego bez wiedzy o konkretnych klasach po stronie wywołującego |
| **Service Layer** | `services.py` | `BookingService`, `MemberService`, `TrainerService`, `EquipmentService`, `PaymentService`, `WaitlistService`, `UserService` — logika biznesowa oddzielona od tras Flask |
| **Observer** | `services.py` | `BookingObserver` (ABC) + `WaitlistObserver` — po anulowaniu rezerwacji `BookingService` powiadamia obserwatorów; `WaitlistObserver` automatycznie przydziela miejsce pierwszej osobie z kolejki |
| **Decorator** | `app.py` | `@role_required(role)` — dekorator strzegący tras; każdy widok wymaga konkretnej roli (`admin` / `trainer` / `client`) |

---

## Testy

```bash
python -m pytest tests/ -v
```

**92 testy** w 6 plikach — zero warningów:

| Plik | Co testuje |
|------|------------|
| `test_auth.py` | logowanie, wylogowanie, ochrona tras |
| `test_booking.py` | rezerwacja, anulowanie, duplikaty, limit miejsc, konflikt terminów |
| `test_payment.py` | generowanie numerów TRF, inicjowanie i potwierdzanie płatności |
| `test_services.py` | MemberService, TrainerService, UserService (zmiana hasła) |
| `test_subscription.py` | Strategy + Factory — etykiety, czas trwania, daty końca karnetu |
| `test_waitlist.py` | dołączanie/opuszczanie kolejki, pozycja, WaitlistObserver |

---

## Model danych

```
User ──< Member ──< Booking >── GymClass >── Trainer
              │           │
              └──< Payment └──< Waitlist

Equipment (osobna tabela)
```

| Model | Rola |
|-------|------|
| `User` | konto auth; rola: `admin \| trainer \| client`; hasło PBKDF2 |
| `Member` | profil klienta; typ karnetu: `monthly \| annual \| day_pass` |
| `Trainer` | profil trenera; specjalizacja i stawka godzinowa |
| `GymClass` | definicja zajęć: dzień tygodnia, godzina, czas trwania, limit miejsc |
| `Booking` | połączenie Member ↔ GymClass; status: `confirmed \| cancelled` |
| `Waitlist` | kolejka oczekujących na zajęcia; ordered by `added_at` |
| `Equipment` | inwentarz siłowni; status: `working \| maintenance \| broken` |
| `Payment` | płatność za miesiąc; status: `pending \| completed`; numer TRF |
