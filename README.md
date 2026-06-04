# 🏋️ GymManagement

Aplikacja webowa do zarządzania siłownią - członkowie, trenerzy, zajęcia grupowe, rezerwacje i sprzęt. Zbudowana na Pythonie z Flaskiem i SQLite. Działa lokalnie, nie potrzebuje żadnych zewnętrznych serwisów.

---

## 🛠️ Stack

| Warstwa  | Technologia                              |
|----------|------------------------------------------|
| Backend  | Python 3.12, Flask 3.0, blueprinty       |
| Baza     | SQLite via Flask-SQLAlchemy 3.1          |
| Auth     | Sesje, hasła hashowane Werkzeugiem       |
| Bezpiec. | CSRF via Flask-WTF                       |
| Config   | Zmienne środowiskowe via python-dotenv   |
| Frontend | Jinja2 + Bootstrap 5                     |

---

## 🚀 Jak uruchomić

```bash
# zainstaluj zależności
pip install -r requirements.txt

# skopiuj plik konfiguracyjny i ustaw klucze
cp .env.example .env

# wypełnij bazę danymi demo
python seed.py

# odpal serwer
python app.py
```

Aplikacja działa pod `http://127.0.0.1:5000`.

### Dane logowania (demo)

| Rola    | Login                 | Hasło       |
|---------|-----------------------|-------------|
| Admin   | `admin`               | `admin123`  |
| Trener  | `jan.kowalski`        | `trener123` |
| Trener  | `anna.nowak`          | `trener123` |
| Trener  | `piotr.wisniewski`    | `trener123` |
| Trener  | `marta.wojcik`        | `trener123` |
| Klient  | `tomasz.krol`         | `klient123` |
| Klient  | `ewa.dabrowska`       | `klient123` |
| Klient  | `michal.kowalczyk`    | `klient123` |
| Klient  | `karolina.szymanska`  | `klient123` |

---

## ✅ Co już działa

### Bezpieczeństwo
- Ochrona CSRF - tokeny Flask-WTF we wszystkich formularzach POST
- Hasła hashowane algorytmem PBKDF2 (Werkzeug)
- Klucz aplikacji i URL bazy wczytywane z pliku `.env`
- Świadome strefy czasowe - `datetime.now(timezone.utc)` zamiast deprecated `utcnow()`

### Architektura
- Kod podzielony na blueprinty: `auth`, `admin`, `trainer`, `client`
- Fabryka aplikacji `create_app()` w `app.py`
- Współdzielone rozszerzenia (`db`, `csrf`) w `extensions.py`

### Logowanie i role
- Logowanie / wylogowanie z hashowaniem haseł
- Trzy role: **Admin**, **Trener**, **Klient** - każda widzi tylko swoje widoki
- Dekoratory na routach pilnują dostępu, nieautoryzowane żądania są przekierowywane

### Panel Admina
- **Dashboard** - statystyki na żywo: członkowie, trenerzy, zatwierdzone zajęcia, rezerwacje; badge z liczbą zajęć oczekujących na zatwierdzenie; feed 8 ostatnich rezerwacji
- **Członkowie** - pełny CRUD: dodawanie z tworzeniem konta, edycja danych i subskrypcji, usuwanie kaskadowe; wyszukiwarka po imieniu/nazwisku i filtr po typie karnetu
- **Trenerzy** - lista ze specjalizacją i stawką godzinową
- **Zajęcia** - workflow zatwierdzania: sekcja "Do zatwierdzenia" z przyciskami Zatwierdź / Odrzuć (modal z polem na notatkę); lista zatwierdzonych i odrzuconych propozycji
- **Sprzęt** - inwentarz z kategorią, statusem (sprawny / serwis / zepsuty) i datą zakupu

### Panel Trenera
- **Dashboard** - zajęcia na dziś, łączna liczba unikalnych podopiecznych, alert o oczekujących propozycjach
- **Harmonogram** - podział na: zatwierdzone (z obłożeniem), oczekujące na zatwierdzenie, odrzucone (z powodem odrzucenia)
- **Propozycja zajęć** - formularz z dniem, godziną, czasem trwania, częstotliwością (co 1/2/3/4 tygodnie) i datą pierwszej sesji
- **Podopieczni** - lista członków zapisanych na zajęcia trenera ze statusem subskrypcji

### Panel Klienta
- **Dashboard** - status subskrypcji, ile dni zostało (ostrzeżenie przy <7 dniach), 5 ostatnich rezerwacji z datami sesji
- **Zajęcia** - karty zatwierdzonych zajęć z listą nadchodzących sesji (do 3); zapis na konkretną sesję z datą; guard przed przepełnieniem i konfliktem terminów
- **Rezerwacje** - historia rezerwacji z konkretną datą sesji; oznaczenie minionych sesji; możliwość anulowania
- **Profil** - dane osobowe, typ subskrypcji, łączna liczba aktywnych rezerwacji

---

## 🗃️ Model danych

```
User ──< Member ──< Booking >── ClassSession >── GymClass >── Trainer
                                                              │
                                                         Equipment (osobna tabela)
```

- `User` - konto auth; rola: `admin | trainer | client`
- `Member` - profil klienta; typ subskrypcji: `monthly | annual | day_pass`
- `Trainer` - profil trenera ze specjalizacją i stawką
- `GymClass` - definicja zajęć: dzień, godzina, czas trwania, limit miejsc, częstotliwość, data startu, status (`pending | approved | rejected`), notatka odrzucenia
- `ClassSession` - konkretne wystąpienie zajęć z datą; generowane automatycznie po zatwierdzeniu na 12 tygodni do przodu
- `Booking` - rezerwacja klienta na konkretną sesję; status: `confirmed | cancelled`
- `Equipment` - pozycja inwentarza siłowni

---

## 🔮 Plany na przyszłość

### Członkowie i subskrypcje
- [ ] Flow przedłużania subskrypcji - admin może przedłużyć lub zmienić typ bez usuwania konta
- [ ] Eksport listy członków do CSV

### Trenerzy
- [ ] Formularz edycji trenera (admin zmienia specjalizację, stawkę)
- [ ] Widok harmonogramu w formacie kalendarza
- [ ] Oznaczanie obecności - trener potwierdza kto faktycznie przyszedł

### Zajęcia i rezerwacje
- [ ] Lista oczekujących - gdy sesja jest pełna, klient wchodzi w kolejkę
- [ ] Edycja zajęć - trener może zaktualizować propozycję przed zatwierdzeniem
- [ ] Limit rezerwacji na tydzień

### Sprzęt
- [ ] Pełny CRUD sprzętu z panelu admina (teraz jest tylko podgląd)
- [ ] Dziennik serwisowy - historia napraw dla każdego urządzenia
- [ ] Alert na dashboardzie gdy sprzęt ma status `broken` lub `maintenance`

### Raporty i analityka
- [ ] Wykres obłożenia sesji w czasie
- [ ] Szacowany przychód na podstawie aktywnych subskrypcji
- [ ] Ranking najpopularniejszych zajęć

### Technicznie
- [ ] Zmiana hasła (wszystkie role) + reset hasła przez admina
- [ ] Testy pytest (logika rezerwacji i auth)
- [ ] Migracja z SQLite na PostgreSQL
