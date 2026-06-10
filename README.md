# 🏋️ GymManagement

Aplikacja webowa do zarządzania siłownią - członkowie, trenerzy, zajęcia grupowe, rezerwacje, płatności i sprzęt. Zbudowana na Pythonie z Flaskiem i SQLite. Działa lokalnie, nie wymaga zewnętrznych serwisów.

---

## 🛠️ Stack

| Warstwa   | Technologia                                        |
|-----------|----------------------------------------------------|
| Backend   | Python 3.12, Flask 3.0                             |
| Baza      | SQLite via Flask-SQLAlchemy 3.1                    |
| Auth      | Sesje, hasła PBKDF2 (Werkzeug)                     |
| Serwisy   | Warstwa `services.py` - logika biznesowa oddzielona od routów |
| Frontend  | Jinja2 + Bootstrap 5 + Chart.js                    |
| Testy     | pytest (4 pliki testowe)                           |

---

## 🚀 Jak uruchomić

```bash
# 1. Zainstaluj zależności
pip install -r requirements.txt

# 2. Wypełnij bazę danymi demo
python seed.py

# 3. Odpal serwer
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

### Logowanie i role
- Sesje z trzema rolami: **Admin**, **Trener**, **Klient**
- Dekoratory na routach blokują nieautoryzowany dostęp
- Zmiana hasła dostępna w profilu każdej roli

### Panel Admina
- **Dashboard** - statystyki na żywo (członkowie, trenerzy, zajęcia, rezerwacje) + wykresy Chart.js: przychody miesięczne, podział karnetów, top 5 zajęć
- **Członkowie** - pełny CRUD; wyszukiwarka i filtr po karnecie; eksport do CSV (UTF-8 BOM dla Excela)
- **Trenerzy** - pełny CRUD (dodawanie, edycja, usuwanie)
- **Zajęcia** - dodawanie i usuwanie; tygodniowy plan z obłożeniem
- **Sprzęt** - pełny CRUD (dodawanie, edycja, usuwanie) z kategorią i statusem
- **Płatności** - historia wszystkich transakcji z łącznym przychodem

### Panel Trenera
- **Dashboard** - zajęcia na dziś, łączna liczba unikalnych podopiecznych
- **Harmonogram** - pełny tygodniowy plan z aktualnym obłożeniem
- **Podopieczni** - lista klientów zapisanych na zajęcia ze statusem karnetu

### Panel Klienta
- **Dashboard** - status karnetu, dni do końca, alert gdy < 7 dni, ostatnie rezerwacje
- **Zajęcia** - katalog posortowany po dniach; rezerwacja jednym kliknięciem; lista oczekujących gdy pełne (z podglądem pozycji w kolejce); guard przed przepełnieniem
- **Rezerwacje** - historia z możliwością anulowania (przy anulowaniu auto-awans z listy oczekujących)
- **Płatności** - tabela miesięcy od dołączenia do dziś ze statusem opłacenia; modal z danymi do przelewu i symulacją animowanego płatności bankowego
- **Profil** - dane osobowe, szczegóły karnetu, zmiana hasła

### Moduł płatności (symulowany)
Klient widzi tabelę miesięcy - każdy z nich jest `Opłacony` lub `Nieopłacony`. Kliknięcie **Opłać** otwiera modal z:
- numerem konta odbiorcy
- unikalnym tytułem przelewu (`TRF-XXXX-XXXX-XXXX`)
- kwotą zależną od karnetu (miesięczny 99 zł / roczny 799 zł / dzienny 29 zł)

**Symuluj płatność** uruchamia animację z kolejnymi komunikatami (`Łączenie z bankiem...` → `Weryfikacja danych...` → `Autoryzacja przelewu...`). Po ~3,5 s transakcja trafia do bazy jako `completed`.

---

## 🗃️ Model danych

```
User ──< Member ──< Booking >── GymClass >── Trainer
              │   < Waitlist >──┘
              └──< Payment
Equipment (osobna tabela)
```

| Model | Opis |
|---|---|
| `User` | Konto auth; rola: `admin / trainer / client` |
| `Member` | Profil klienta; karnet: `monthly / annual / day_pass` |
| `Trainer` | Profil trenera: specjalizacja, stawka |
| `GymClass` | Definicja zajęć: harmonogram, limit miejsc |
| `Booking` | Rezerwacja klienta na zajęcia; status: `confirmed / cancelled` |
| `Waitlist` | Kolejka oczekujących na pełne zajęcia; FIFO auto-awans przy anulowaniu |
| `Payment` | Płatność za miesiąc; status: `pending / completed`; pola: `month_year`, `amount`, `transfer_number` |
| `Equipment` | Inwentarz sprzętu: kategoria, status (`working / maintenance / broken`), data zakupu |

---

## 🏗️ Architektura

Logika biznesowa wydzielona do `services.py` — routy w `app.py` tylko delegują:

| Serwis | Odpowiedzialność |
|---|---|
| `BookingService` | Tworzenie i anulowanie rezerwacji, guard przed przepełnieniem |
| `WaitlistService` | Dołączanie do kolejki, opuszczanie, auto-awans, pozycja |
| `MemberService` | CRUD członków, sprawdzanie aktywności karnetu |
| `TrainerService` | CRUD trenerów |
| `EquipmentService` | CRUD sprzętu |
| `PaymentService` | Inicjowanie i potwierdzanie płatności, generowanie historii miesięcy |
| `SubscriptionFactory` | Tworzenie obiektów subskrypcji per typ |
| `UserService` | Zmiana hasła z walidacją |

---

## 🧪 Testy

```bash
python -m pytest tests/ -v
```

| Plik | Zakres |
|---|---|
| `test_auth.py` | Login, błędne dane, kontrola dostępu per rola |
| `test_booking.py` | Rezerwacja, duplikat, pełna klasa, anulowanie, auto-awans z waitlisty |
| `test_services.py` | Logika serwisów: BookingService, WaitlistService, MemberService |
| `test_subscription.py` | SubscriptionFactory - tworzenie per typ karnetu |

---

## 📁 Struktura projektu

```
├── app.py              # routy Flask
├── models.py           # modele SQLAlchemy
├── services.py         # warstwa logiki biznesowej
├── seed.py             # dane demo
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── admin/          # dashboard, members, trainers, classes, equipment, payments
│   ├── trainer/        # dashboard, schedule, members
│   └── client/         # dashboard, classes, bookings, payments, profile
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_booking.py
    ├── test_services.py
    └── test_subscription.py
```
