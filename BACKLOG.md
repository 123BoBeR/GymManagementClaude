# BACKLOG — branch `dev`

Pełny backlog zadań do ukończenia projektu GymApp.
Oparty na audycie brancha `dev` i porównaniu z `develop`.

---

## Co jest już gotowe na `dev`

| Funkcja | Plik |
|---------|------|
| Blueprint architektura (auth/admin/trainer/client) | `blueprints/` |
| `create_app()` factory + `extensions.py` | `app.py`, `extensions.py` |
| CSRF ochrona (Flask-WTF) | `extensions.py`, formularze |
| Model `ClassSession` — realne daty sesji | `models.py` |
| Workflow zajęć: propose → approve/reject (admin) | `blueprints/admin.py`, `blueprints/trainer.py` |
| Oznaczanie obecności przez trenera | `blueprints/trainer.py`, `templates/trainer/attendance.html` |
| Waitlist z auto-awansem przy anulowaniu (inline) | `blueprints/client.py` |
| Detekcja konfliktu terminów (overlap time-based) | `blueprints/client.py` |
| CRUD klientów + reset hasła + szybkie odnawianie | `blueprints/admin.py` |
| CRUD trenerów + edycja (modal) | `blueprints/admin.py` |
| CRUD sprzętu + alert na dashboardzie admina | `blueprints/admin.py`, `templates/admin/` |
| Raporty: wykres obłożenia + ranking zajęć | `blueprints/admin.py`, `templates/admin/reports.html` |
| Eksport członków do CSV | `blueprints/admin.py` |
| Zmiana hasła (wszystkie role) | `blueprints/auth.py`, `templates/change_password.html` |
| Dekorator `@role_required` | `blueprints/utils.py` |

---

## Zrobione / Do zrobienia

### SEKCJA 1 — Fundamenty (najpierw to)

#### ✅ B01 · Fix suite testowej — ZROBIONE
**Rozwiązanie:** `create_app(test_config=None)` przyjmuje override configu *przed* `init_app`, więc silnik binduje się do `:memory:` zamiast pliku. Usunięto stale `instance/gym.db` i `__pycache__`.  
**Wynik:** 16/16 testów na zielono.  
**Pliki:** `app.py`, `tests/conftest.py`

#### ✅ B02 · Usuń deprecated `Model.query.get_or_404(id)` — ZROBIONE
**Rozwiązanie:** 15 wywołań → `db.get_or_404(Model, id)`; 2 legacy `Query.get()` w testach → `db.session.get()`.  
**Wynik:** 16/16 testów, zero warningów.  
**Pliki:** `blueprints/admin.py`, `blueprints/trainer.py`, `blueprints/client.py`, `tests/test_bookings.py`

---

### SEKCJA 2 — Wzorce OOP i logika biznesowa (core projektu)

#### ✅ B03 · `services.py` — wzorce OOP — ZROBIONE
**Zaimplementowane 4 wzorce** + warstwa serwisowa faktycznie używana przez blueprinty:

| Wzorzec | Implementacja |
|---------|--------------|
| **Strategy** | `SubscriptionStrategy` + `Monthly/Annual/DayPass` — `label()`, `price()`, `duration_days()`, `end_date()` |
| **Factory** | `SubscriptionFactory.create()` + `all_types()` |
| **Observer** | `BookingObserver` + `WaitlistObserver` — awans z waitlisty po anulowaniu |
| **Service Layer** | `BookingService`, `WaitlistService`, `PaymentService`, `MemberService`, `UserService` |

`client.py` (book/waitlist/cancel) i `auth.py` (change_password) przepięte na serwisy. 16/16 testów.  
**Pliki:** `services.py` (nowy), `blueprints/client.py`, `blueprints/auth.py`

#### ✅ B04 · Model `Payment` w `models.py` — ZROBIONE
`Payment(member_id, amount, month_year, status, transfer_number, created_at, paid_at)` + relacja `Member.payments`.  
**Pliki:** `models.py`

#### ✅ B05 · Moduł płatności — trasy i szablony — ZROBIONE
- `GET /admin/payments` + statystyki przychodu (`admin/payments.html`)
- `GET /admin/members/<id>/payments` — historia per klient (`admin/member_payments.html`) + przycisk 🧾 na liście
- `GET /client/payments` — 6 miesięcy + status (`client/payments.html`)
- `POST /client/payments/initiate` → TRF, `GET /payments/<id>/pay` symulowany przelew z animacją paska postępu, `POST /payments/<id>/confirm`
- Linki w sidebarze (admin + klient). Seed z przykładowymi płatnościami.
- Smoke test: initiate→pay→confirm + obie strony admina = 200.  
**Pliki:** `blueprints/admin.py`, `blueprints/client.py`, `seed.py`, `templates/base.html`, 4 nowe szablony

#### ✅ B06 · Logika subskrypcji — ZROBIONE
- Ceny via `SubscriptionFactory` (99/799/29 zł) — przekazane do widoku
- `POST /client/subscription/renew` — klient sam przedłuża karnet (stackuje od końca), zapisuje opłatę completed
- Banner ≤7 dni (+ obsługa wygasłego) na dashboardzie  
**Pliki:** `services.py`, `blueprints/client.py`, `templates/client/dashboard.html`

---

### SEKCJA 3 — Brakujące widoki i trasy

#### ✅ B07 · Admin: lista uczestników per zajęcia — ZROBIONE
`GET /admin/classes/<id>/members` — unikalni uczestnicy ze wszystkich sesji zajęć, status karnetu, liczba rezerwacji; przycisk 👥 na liście zajęć.  
**Pliki:** `blueprints/admin.py`, `templates/admin/class_members.html`, `templates/admin/classes.html`

#### ✅ B08 · Admin: kolejka oczekujących — ZROBIONE
`GET /admin/waitlist` — wpisy pogrupowane wg sesji z pozycją w kolejce, datą, zajęciami; link w sidebarze.  
**Pliki:** `blueprints/admin.py`, `templates/admin/waitlist.html`, `templates/base.html`

#### ✅ B09 · Trainer: profil z edycją — ZROBIONE
`GET/POST /trainer/profile` — statystyki (zajęcia, podopieczni, stawka) + edycja specjalizacji i stawki; link do zmiany hasła; pozycja w sidebarze.  
**Pliki:** `blueprints/trainer.py`, `templates/trainer/profile.html`, `templates/base.html`

#### ✅ B10 · Trainer: lista uczestników per zajęcia — ZROBIONE
`GET /trainer/classes/<id>/members` (guard własności) — uczestnicy + licznik obecności; przycisk 👥 na harmonogramie. Bonus: usunięto martwą kolumnę „Dzień" (pokazywała „-").  
**Pliki:** `blueprints/trainer.py`, `templates/trainer/class_members.html`, `templates/trainer/schedule.html`

#### ✅ B11 · Client: edycja profilu — ZROBIONE
`POST /client/profile/edit` (przez `MemberService.update_profile`) + modal edycji imienia/nazwiska/telefonu.  
**Pliki:** `blueprints/client.py`, `templates/client/profile.html`

#### ✅ B12 · Client: dashboard — sekcja "Ten tydzień" — ZROBIONE
Sekcja "Ten tydzień" z nadchodzącymi sesjami (najbliższe 7 dni, sortowane po dacie), nazwy linkują do szczegółów sesji.  
**Pliki:** `blueprints/client.py`, `templates/client/dashboard.html`

#### ✅ B13 · Client: filtr rezerwacji — ZROBIONE
Przyciski Aktywne / Wszystkie / Anulowane (`?status=`) + filtrowanie w route (domyślnie aktywne).  
**Pliki:** `blueprints/client.py`, `templates/client/bookings.html`

#### ✅ B14 · Client: szczegóły sesji — ZROBIONE
`GET /client/sessions/<id>` — opis, trener, specjalizacja, pasek zajętości + kontekstowa akcja (zapisz / waitlist / już zapisany / pełne / przeszłe / odwołane).  
**Pliki:** `blueprints/client.py`, `templates/client/session_detail.html`

---

### SEKCJA 4 — UX i polish

#### ✅ B15 · Custom strona 404 — ZROBIONE
`@app.errorhandler(404)` + `templates/404.html` (duże „404", przycisk „Wróć na start", spójny styl).  
**Pliki:** `app.py`, `templates/404.html`

#### ✅ B16 · Wyszukiwarka + filtr karnetów — ZROBIONE (było na `dev`)
`members.html` miał już live search (imię/nazwisko) + select filtr karnetu (JS bez przeładowania). Dołożono przycisk 🧾 płatności.  
**Pliki:** `templates/admin/members.html`

#### ✅ B17 · Wykresy Chart.js na dashboardzie admina — ZROBIONE
3 wykresy: przychód 6 mies (bar, z `Payment`), podział karnetów (doughnut), top 5 zajęć (poziomy bar). Dane przez `| tojson`.  
**Pliki:** `blueprints/admin.py`, `templates/admin/dashboard.html`

#### ✅ B18 · Dark mode toggle — ZROBIONE (zbudowane od zera)
Na `dev` nie było dark mode. Dodano: system CSS variables (jasny/ciemny), nadpisania Bootstrap (tabele/modale/formularze), przycisk w sidebarze z localStorage, skrypt no-flash w `<head>`.  
**Pliki:** `templates/base.html`

---

### SEKCJA 5 — Rozbudowa testów

#### ✅ B19 · test_subscription.py — ZROBIONE
Strategy (labels/prices/duration/end_date) + Factory (create per typ, ValueError, all_types). **16 testów.**

#### ✅ B20 · test_payment.py — ZROBIONE
amount_for, format/unikalność TRF, months_for_member, initiate (pending/repeat/completed/brak klienta), confirm (timestamp/wrong member/double), total_revenue. **18 testów.**

#### ✅ B21 · test_services.py — ZROBIONE
BookingService (book, duplikat, pełne, przeszłe, konflikt, cancel, wrong member), MemberService (update/renew/is_active/days_left), UserService (4 ścieżki zmiany hasła). **17 testów.**

#### ✅ B22 · test_waitlist.py — ZROBIONE
WaitlistService (join/duplikat/leave/position) + WaitlistObserver (awans po anulowaniu, brak awansu bez kolejki). **8 testów.**

**Łącznie: 67 testów (16 → 67), wszystkie zielone.**

---

### SEKCJA 6 — Finalizacja

#### ✅ B23 · Aktualizacja README — ZROBIONE
Stack (67 testów, wzorce), funkcje per rola z płatnościami/kolejką/profilami, nowa sekcja wzorców OOP (5), model danych z `Payment`, tabela 6 plików testowych, zaktualizowana struktura projektu.  
**Pliki:** `README.md`

---

## Kolejność realizacji (zalecana)

```
B01 → B02 → B03 → B04 → B05 → B06
             ↓
B07 → B08 → B09 → B10 → B11 → B12 → B13 → B14
             ↓
B15 → B16 → B17 → B18
             ↓
B19 → B20 → B21 → B22
             ↓
           B23
```

**Priorytety twardde:**
- B03 (`services.py`) odblokowuje B05, B06, B19–B22
- B04 (`Payment`) odblokowuje B05, B07 (admin payments), B17 (wykresy)
- B01 (testy green) — najlepiej zaraz, bo każde nowe zadanie powinno mieć test

---

---

### SEKCJA 7 — Domknięcia po backlogu (kontynuacja)

#### ✅ B24 · Admin: pełny CRUD trenerów — ZROBIONE
Dodawanie trenera (User+Trainer, walidacja loginu/hasła) i usuwanie (cascade, blokada gdy ma zajęcia) — wcześniej tylko edycja. Plus link do szczegółów sesji z listy zajęć klienta. **+5 testów (`test_admin.py`).**
**Pliki:** `blueprints/admin.py`, `templates/admin/trainers.html`, `templates/client/classes.html`, `tests/test_admin.py`

---

#### ✅ B25 · Polish: eksport płatności + filtr sprzętu + fix 404 — ZROBIONE
Eksport płatności do CSV (admin, parytet z eksportem klientów), live search + filtr stanu na liście sprzętu, naprawa niewidocznego nagłówka 404 w trybie ciemnym. **+1 test.**
**Pliki:** `blueprints/admin.py`, `templates/admin/payments.html`, `templates/admin/equipment.html`, `templates/404.html`, `tests/test_admin.py`

---

#### ✅ B26 · Auto-loginy + auto-ważność + wyszukiwarka trenerów — ZROBIONE
- Login klienta: `[litera_imienia].[nazwisko]`, przy kolizji narasta o kolejną literę (`j.kowalski` → `ja.kowalski` → `jan.kowalski`), polskie znaki transliterowane (`Łukasz Wójcik` → `l.wojcik`)
- Login trenera: `t.[imię].[nazwisko]` (przy kolizji + numer)
- Ważność karnetu zawsze wyliczana wg typu (koniec ręcznego wpisywania dat) — przy dodaniu, zmianie typu i odnowieniu (stackowanie cykliczne)
- Wyszukiwarka na liście trenerów (live JS, jak u klientów)
- `UserService.generate_client_username` / `generate_trainer_username` + transliteracja diakrytyków. **+10 testów.**
**Pliki:** `services.py`, `blueprints/admin.py`, `templates/admin/{member_form,members,trainers}.html`, `tests/test_admin.py`

---

*Ostatnia aktualizacja: 2026-06-24 · branch `dev` · 83 testy*
