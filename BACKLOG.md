# Backlog — GymApp

Zadania do zrobienia w gałęzi `develop`. `master` zostaje nienaruszony do prezentacji.

---

## Do zrobienia

### #23 Lista uczestników zajęć
**Priorytet:** wysoki | **Szacunek:** ~1h

Admin i trener mogą podejrzeć kto jest zapisany na konkretne zajęcia.

- `GET /admin/classes/<id>/members` — tabela z imieniem, nazwiskiem, statusem subskrypcji
- `GET /trainer/classes/<id>/members` — to samo, ale tylko dla zajęć danego trenera
- Przycisk „Uczestnicy" na liście zajęć (ikonka osoby)

---

### #24 Szczegóły zajęć dla klienta
**Priorytet:** średni | **Szacunek:** ~45min

Klient klika nazwę zajęć i widzi pełny opis zamiast tylko listy.

- `GET /client/classes/<id>` — nazwa, opis, trener, dzień/godzina, czas trwania, obłożenie (X/Y miejsc), przycisk rezerwacji
- Link z `/client/classes` na każdej nazwie zajęć

---

### #25 Własna strona 404
**Priorytet:** niski | **Szacunek:** ~20min

Zamiast domyślnego ekranu Werkzeuga — własna strona dopasowana do stylu aplikacji.

- `@app.errorhandler(404)` w `app.py`
- `templates/404.html` dziedziczący po `base.html`
- Komunikat i przycisk powrotu do dashboardu

---

### #26 Bugfix: kolumna „Dzień" w grafiku trenera
**Priorytet:** średni | **Szacunek:** ~15min

W `templates/trainer/schedule.html` wyświetla się pusta kolumna „—" zamiast dnia tygodnia.

- Sprawdzić jaka zmienna jest przekazywana w kontekście szablonu
- Poprawić wyświetlanie dnia lub usunąć zbędną kolumnę

---

### #27 Historia płatności klienta w panelu admina
**Priorytet:** niski | **Szacunek:** ~30min

Admin wchodzi w profil klienta i widzi jego historię transakcji.

- Sekcja „Płatności" na stronie `/admin/members/<id>/edit` (lub osobna zakładka)
- Tabela: miesiąc, kwota, status, data opłacenia
- Podsumowanie: łączna liczba i kwota opłaconych

---

### #28 Tygodniowy widok zajęć dla klienta
**Priorytet:** niski | **Szacunek:** ~1.5h

Zamiast posortowanej listy — siatka pon–nd z zajęciami w odpowiednich kolumnach.

- Grupowanie zajęć po `schedule_day` (0–6)
- Nagłówki kolumn: Pon / Wt / Śr / Czw / Pt / Sob / Nd
- Karta zajęć z godziną, nazwą i przyciskiem rezerwacji
- Widok responsywny (na mobile zawija do listy)

---

### #29 Walidacja konfliktu terminów rezerwacji
**Priorytet:** średni | **Szacunek:** ~30min

Klient nie może zarezerwować dwóch zajęć w tym samym dniu i godzinie.

- W `BookingService.book()` sprawdzić czy klient ma już aktywną rezerwację na ten sam `schedule_day` + `schedule_time`
- Jeśli tak — zwrócić `(False, "Masz już rezerwację na ten termin")`
- Dodać test w `tests/test_booking.py` (lub `test_services.py`)

---

## Następny tydzień — Docker

Konteneryzacja aplikacji jako osobny temat (przedmiot IT Systems Management).

- `Dockerfile` dla aplikacji Flask (Python 3.12-slim, kopiuj kod, `pip install`, `CMD flask run`)
- `docker-compose.yml` — serwis `web` + wolumen dla `instance/gym.db`
- Zmienne środowiskowe: `SECRET_KEY`, `DATABASE_URL` przez `.env`
- Opcjonalnie: `nginx` jako reverse proxy

---

## Zrobione (ostatnie sesje)

- [x] Testy `PaymentService` (16 testów)
- [x] Testy `WaitlistService` + `WaitlistObserver` (13 testów)
- [x] Testy `UserService.change_password` (5 testów)
- [x] Profil trenera — podgląd statystyk i edycja specjalizacji/stawki (`/trainer/profile`)
- [x] Edycja zajęć przez admina (`/admin/classes/<id>/edit`)
- [x] Edycja danych osobowych klienta (`/client/profile/edit`)
- [x] Panel kolejki oczekujących dla admina (`/admin/waitlist`)
- [x] Alerty sprzętowe na dashboardzie admina (baner zepsuty / serwis)
- [x] Wyszukiwarka i filtr na liście klientów (JS, bez przeładowania)
- [x] Reset hasła klienta przez admina (`/admin/members/<id>/reset-password`)
- [x] Szybkie przedłużenie karnetu (+1m / +3m / +1rok) bez dateutil
