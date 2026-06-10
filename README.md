# 🏋️ GymManagement

Aplikacja webowa do zarządzania siłownią - członkowie, trenerzy, zajęcia grupowe, rezerwacje i sprzęt. Zbudowana na Pythonie z Flaskiem i SQLite. Działa lokalnie, nie potrzebuje żadnych zewnętrznych serwisów.

---

## 🛠️ Stack

| Warstwa  | Technologia                       |
|----------|-----------------------------------|
| Backend  | Python 3.12, Flask 3.0            |
| Baza     | SQLite via Flask-SQLAlchemy 3.1   |
| Auth     | Sesje, hasła hashowane Werkzeugiem |
| Frontend | Jinja2 + Bootstrap 5              |

---

## 🚀 Jak uruchomić

```bash
# zainstaluj zależności
pip install -r requirements.txt

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

### Logowanie i role
- Logowanie / wylogowanie z hashowaniem haseł (Werkzeug PBKDF2)
- Trzy role: **Admin**, **Trener**, **Klient** - każda widzi tylko swoje widoki
- Dekoratory na routach pilnują dostępu, nieautoryzowane żądania są przekierowywane

### Panel Admina
- **Dashboard** - statystyki na żywo: ilu członków, trenerów, zajęć, aktywnych rezerwacji; feed 8 ostatnich rezerwacji
- **Członkowie** - pełny CRUD: dodawanie z tworzeniem konta, edycja danych i subskrypcji, usuwanie kaskadowe (usuwa konto + rezerwacje)
- **Trenerzy** - lista ze specjalizacją i stawką godzinową
- **Zajęcia** - tygodniowy plan posortowany po dniach; dodawanie i usuwanie zajęć; inline widać ile miejsc jest zajętych
- **Sprzęt** - inwentarz z kategorią, statusem (sprawny / serwis / zepsuty) i datą zakupu

### Panel Trenera
- **Dashboard** - zajęcia na dziś, łączna liczba unikalnych podopiecznych
- **Grafik** - pełny tygodniowy plan posortowany pon-nd z aktualnym obłożeniem
- **Podopieczni** - lista członków zapisanych na zajęcia trenera ze statusem subskrypcji

### Panel Klienta
- **Dashboard** - status subskrypcji, ile dni zostało, 5 ostatnich rezerwacji
- **Zajęcia** - katalog wszystkich zajęć posortowany po dniach; rezerwacja jednym kliknięciem; guard przed przepełnieniem
- **Rezerwacje** - historia rezerwacji z możliwością anulowania
- **Profil** - dane osobowe, typ subskrypcji, łączna liczba aktywnych rezerwacji
- **Płatności** - historia opłat miesięcznych, przycisk „Opłać" uruchamia symulowany przelew bankowy

### Moduł płatności (symulowany)
Klient wchodzi w zakładkę **Płatności** i widzi tabelę miesięcy od daty dołączenia do dziś — każdy miesiąc ma status *Opłacono* lub *Nieopłacone*.

Kliknięcie **Opłać** otwiera modal z danymi do przelewu:
- numer konta odbiorcy
- wygenerowany unikalny tytuł przelewu (format `TRF-XXXX-XXXX-XXXX`)
- kwota zależna od typu karnetu (miesięczny 99 zł / roczny 799 zł / dzienny 29 zł)

Kliknięcie **Symuluj płatność** uruchamia animację ładowania z paskiem postępu i kolejnymi komunikatami (`Łączenie z bankiem...` → `Weryfikacja danych...` → `Autoryzacja przelewu...` itd.). Po ~3,5 s transakcja jest oznaczana jako `completed` w bazie, modal pokazuje ekran sukcesu, a strona odświeża się automatycznie.

Admin widzi wszystkie transakcje z podsumowaniem (liczba opłaconych, łączny przychód) w zakładce **Płatności**.

---

## 🗃️ Model danych

```
User ──< Member ──< Booking >── GymClass >── Trainer
              │
              └──< Payment
Equipment (osobna tabela)
```

- `User` - konto auth; rola: `admin | trainer | client`
- `Member` - profil klienta; typ subskrypcji: `monthly | annual | day_pass`
- `Trainer` - profil trenera ze specjalizacją i stawką
- `GymClass` - definicja zajęć: dzień, godzina, czas trwania, limit miejsc
- `Booking` - połączenie Member ↔ GymClass; status: `confirmed | cancelled`
- `Equipment` - pozycja inwentarza siłowni
- `Payment` - płatność za miesiąc; status: `pending | completed`; pola: `month_year`, `amount`, `transfer_number`, `paid_at`

---

## 🔮 Plany na przyszłość

### Członkowie i subskrypcje
- [ ] Automatyczny banner ostrzegawczy gdy zostało < 7 dni subskrypcji
- [ ] Wyszukiwarka i filtry na liście członków (imię, typ subskrypcji, data wygaśnięcia)
- [ ] Eksport listy członków do CSV

### Zajęcia i rezerwacje
- [ ] Lista oczekujących - gdy zajęcia są pełne, klient wchodzi w kolejkę i dostaje miejsce przy anulowaniu
- [ ] Edycja zajęć - zmiana nazwy, opisu, godziny, pojemności bez usuwania i tworzenia od nowa
- [ ] Limit rezerwacji na tydzień

### Raporty i analityka
- [ ] Wykres obłożenia zajęć w czasie
- [ ] Ranking najpopularniejszych zajęć

### Technicznie
- [ ] Formularz zmiany hasła dla wszystkich ról
- [ ] Migracja z SQLite na PostgreSQL pod produkcję
- [ ] Konfiguracja przez zmienne środowiskowe (`.env` + `python-dotenv`)
