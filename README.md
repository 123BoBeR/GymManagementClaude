# 🏋️ GymManagement

Aplikacja webowa do zarządzania siłownią - członkowie, trenerzy, zajęcia grupowe, rezerwacje i sprzęt. Zbudowana na Pythonie z Flaskiem i SQLite. Działa lokalnie, nie wymaga zewnętrznych serwisów.

---

## 🛠️ Stack

| Warstwa   | Technologia                             |
|-----------|-----------------------------------------|
| Backend   | Python 3.12, Flask 3.0, blueprinty      |
| Baza      | SQLite / PostgreSQL (Flask-SQLAlchemy)  |
| Auth      | Sesje, hasła PBKDF2 (Werkzeug)          |
| Bezpiec.  | CSRF tokeny (Flask-WTF)                 |
| Config    | Zmienne środowiskowe (python-dotenv)    |
| Frontend  | Jinja2 + Bootstrap 5 + Chart.js         |
| Testy     | pytest (16 testów)                      |

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
- Fabryka `create_app()`, współdzielone rozszerzenia w `extensions.py`

### Logowanie i role
- Sesje z trzema rolami: **Admin**, **Trener**, **Klient**
- Dekoratory na routach blokują nieautoryzowany dostęp
- Zmiana hasła dostępna z sidebara dla każdej roli

### Panel Admina
- **Dashboard** - statystyki na żywo + badge z liczbą zajęć do zatwierdzenia + feed ostatnich rezerwacji
- **Członkowie** - pełny CRUD z wyszukiwarką i filtrem po karnecie; szybkie odnowienie karnetu (modal +1m/+3m/+1 rok); reset hasła; eksport do CSV
- **Trenerzy** - lista z edycją danych (modal)
- **Zajęcia** - workflow zatwierdzania: sekcja "Do zatwierdzenia" z przyciskami Zatwierdź / Odrzuć (modal z notatką); lista zatwierdzonych i odrzuconych
- **Sprzęt** - pełny CRUD (dodawanie, edycja, usuwanie) z kategorią i statusem
- **Raporty** - wykres słupkowy obłożenia tygodniowego (Chart.js, 8 tyg.) + ranking zajęć z wypełnieniem

### Panel Trenera
- **Dashboard** - zajęcia na dziś, unikalni klienci, alert o oczekujących propozycjach
- **Harmonogram** - trzy sekcje: zatwierdzone / oczekujące / odrzucone (z powodem i przyciskiem "Popraw i wyślij ponownie")
- **Propozycja zajęć** - formularz z dniem, godziną, czasem trwania, częstotliwością (co 1-4 tygodnie) i datą startu
- **Obecność** - lista sesji ±7/14 dni; per sesja: toggle Był/a / Nieobecny / — dla każdego zapisanego
- **Podopieczni** - lista klientów ze statusem karnetu

### Panel Klienta
- **Dashboard** - status i dni do końca karnetu (alert przy <7 dniach), ostatnie rezerwacje
- **Zajęcia** - karty z nadchodzącymi sesjami (do 3); zapis na konkretną sesję; lista oczekujących gdy pełne; guard przed przepełnieniem i konfliktami terminów
- **Rezerwacje** - historia z datami sesji; oznaczenie minionych; anulowanie z auto-awansem kolejki
- **Profil** - dane osobowe i szczegóły karnetu

---

## 🗃️ Model danych

```
User ──< Member ──< Booking >── ClassSession >── GymClass >── Trainer
                  < WaitlistEntry >──┘                    │
                                                     Equipment
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
| `Equipment` | Inwentarz sprzętu: kategoria, status, data zakupu |

---

## 🧪 Testy

```bash
python -m pytest tests/ -v
```

**16 testów, 16 zielonych:**

| Plik | Zakres |
|---|---|
| `test_auth.py` | Login, błędne dane, wylogowanie, kontrola dostępu per rola (8 testów) |
| `test_bookings.py` | Rezerwacja, duplikat, pełna sesja, anulowanie, kradzież rezerwacji, konflikt terminów, waitlist + auto-awans (8 testów) |

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
├── app.py                  # create_app() factory
├── extensions.py           # db, csrf
├── models.py               # modele SQLAlchemy
├── seed.py                 # dane demo
├── requirements.txt
├── .env.example
├── blueprints/
│   ├── auth.py             # /, /login, /logout, /change-password
│   ├── admin.py            # /admin/*
│   ├── trainer.py          # /trainer/*
│   ├── client.py           # /client/*
│   ├── sessions.py         # generator sesji
│   └── utils.py            # dekoratory auth
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── change_password.html
│   ├── admin/
│   ├── trainer/
│   └── client/
└── tests/
    ├── conftest.py
    ├── test_auth.py
    └── test_bookings.py
```
