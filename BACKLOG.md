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

#### ✅ B27 · Model miesięczny karnetu — ZROBIONE
Karnet rozliczany w pełnych miesiącach zamiast w dniach: „aktywny w tym miesiącu albo nie".
- `SubscriptionStrategy.extend(current_end, today)` — miesięczny +1 mies., roczny +12 mies., zawsze do końca miesiąca; aktywny → dolicza (czerwiec + miesiąc = lipiec), wygasły → od bieżącego miesiąca; day_pass = tylko dziś
- UI bez konkretnych dat — filtr Jinja `month_label` pokazuje „lipiec 2026" zamiast „31.07.2026" (dashboard, profil, lista klientów, formularze, flash)
- `renew_subscription` / tworzenie / edycja / odnowienie przepięte na `extend`
- Zaktualizowane testy (subscription/services/admin). **86 testów.**
**Pliki:** `services.py`, `app.py`, `blueprints/{admin,client}.py`, `templates/{client/dashboard,client/profile,admin/members,admin/member_form}.html`, `tests/{test_subscription,test_services,test_admin}.py`

---

#### ✅ B28 · Strona Kontakt + responsywność mobilna — ZROBIONE
- Model `ContactOption` + strona `/contact` dla wszystkich ról (telefon, email, adres, godziny)
- Admin dodaje/usuwa opcje kontaktu (kontrolki widoczne tylko dla admina); link „Kontakt" w sidebarze
- Responsywność: off-canvas sidebar z hamburgerem + półprzezroczyste tło na telefonach (≤768px), tabele auto-owijane w `.table-responsive` (przewijanie poziome)
- Seed z domyślnymi danymi kontaktowymi. **+4 testy.**
**Pliki:** `models.py`, `blueprints/{auth,admin}.py`, `templates/{contact,base}.html`, `seed.py`, `tests/test_admin.py`

---

### SEKCJA 8 — Dziury logiczne (audyt 2026-06-24) · **P0**

> Najwyższy priorytet: rzeczy, które wpływają na faktyczne działanie aplikacji.
> Każde zadanie domyka się testem.

#### ✅ B29 · Bramka aktywnego karnetu przy rezerwacji — ZROBIONE
**✅ Wynik:** `book()` i `WaitlistService.join()` odrzucają zapis, gdy karnet nie obejmuje daty sesji (`is_active(member, session_date)`); UI gated w `session_detail` i `classes` (badge „Karnet" → przedłużenie). **+3 testy.**
**Pliki:** `services.py`, `blueprints/client.py`, `templates/client/{classes,session_detail}.html`, `tests/{test_services,test_waitlist}.py`

**Problem:** `BookingService.book()` nie sprawdza, czy klient ma aktywny karnet — osoba z wygasłym karnetem zapisze się na zajęcia. `is_active()` służy dziś tylko do wyświetlenia statusu na dashboardzie.
**Zakres:**
- `BookingService.book()` (i `WaitlistService.join()`) odrzuca zapis, gdy `MemberService.is_active(member)` jest fałszywe — czytelny komunikat („Karnet wygasł — przedłuż, aby się zapisać").
- Sesja musi mieścić się w okresie ważności karnetu (`session_date <= subscription_end`).
- UI: ukryć/zablokować przycisk zapisu dla nieaktywnych + link do przedłużenia.
- Test: nieaktywny klient nie zapisze się; aktywny owszem.
**Pliki:** `services.py`, `blueprints/client.py`, `templates/client/{classes,session_detail}.html`, `tests/test_bookings.py`

#### ✅ B30 · Odwoływanie pojedynczej sesji (ożywienie `ClassSession.cancelled`) — ZROBIONE
**✅ Wynik:** Trener odwołuje własną sesję (`POST /trainer/sessions/<id>/cancel`, guard własności + blokada przeszłych/podwójnych); świadomie bez awansu kolejki. Poprawione agregacje uczestników (admin + trener) pomijają odwołane sesje; klient widzi „Sesja odwołana" w rezerwacjach. **+4 testy.** *Odwoływanie po stronie admina odłożone — wymaga widoku sesji admina.*
**Pliki:** `blueprints/{trainer,admin}.py`, `templates/trainer/sessions.html`, `templates/client/bookings.html`, `tests/test_sessions.py`

**Problem:** Pole `cancelled` istnieje i jest sprawdzane przy rezerwacji oraz filtrowane w widokach, ale **żadna trasa nigdy nie ustawia go na `True`** — nie da się odwołać jednych zajęć (choroba trenera itp.).
**Zakres:**
- Trasa admin (`POST /admin/sessions/<id>/cancel`) i trener (`POST /trainer/sessions/<id>/cancel`, guard własności) ustawia `cancelled = True`.
- Powiadomienie/oznaczenie zapisanych klientów (przy włączonym B42 — notyfikacja; na start: rezerwacje pozostają, ale sesja wyświetla się jako „odwołana").
- UI: przycisk „Odwołaj sesję" na liście sesji + wyraźne oznaczenie odwołanych.
- Test: po odwołaniu nie można rezerwować, sesja znika z nadchodzących.
**Pliki:** `blueprints/admin.py`, `blueprints/trainer.py`, `templates/trainer/sessions.html`, `templates/admin/*`, `tests/`

#### ✅ B31 · Rolling-generacja sesji — ZROBIONE
**✅ Wynik:** `ensure_future_sessions()` (idempotentne, pomija istniejące/odwołane daty, nie cofa się) + `refresh_all_future_sessions()`. Wyzwalacze: komenda CLI `flask sessions-refresh` (cron) i leniwe wywołanie w `client_classes`. **+3 testy.**
**Pliki:** `blueprints/sessions.py`, `app.py` (CLI), `blueprints/client.py`, `tests/test_sessions.py`

**Problem:** `generate_sessions()` tworzy 12 tygodni naprzód **tylko przy zatwierdzeniu** zajęć — po ~kwartale zajęcia zostają bez sesji.
**Zakres:**
- Funkcja `ensure_future_sessions(gym_class, horizon_weeks=12)` idempotentnie dogenerowuje brakujące sesje do horyzontu (bez duplikatów istniejących dat).
- Wyzwalacz: komenda CLI (`flask sessions:refresh`) do crona **oraz** lazy-wywołanie przy wejściu na listę zajęć/harmonogram.
- Test: powtórne wywołanie nie tworzy duplikatów; uzupełnia tylko brakujące.
**Pliki:** `blueprints/sessions.py`, `app.py` (CLI), `tests/test_sessions.py` (nowy)

#### ✅ B32 · Spójność płatności przy odnowieniu + unikalność — ZROBIONE
**✅ Wynik:** `PaymentService.record_completed()` (upsert) — jeden miesiąc = jeden wpis; klient i admin renew rejestrują przychód tą samą ścieżką (admin renew wcześniej nie zapisywał nic → „darmowe" w raportach). `UniqueConstraint(member_id, month_year)` na modelu + w migracji (B36) — twarda gwarancja na poziomie DB. **+5 testów.**
**Residual (świadomy):** dwa odnowienia w tym samym miesiącu kalendarzowym = jeden wpis (model `month_year` = miesiąc kalendarzowy; pełne rozliczenie per-okres to osobny redesign).
**Pliki:** `services.py`, `models.py`, `blueprints/{client,admin}.py`, `tests/{test_payment,test_admin}.py`

**Problem:** Klient odnawiając zapisuje `Payment` completed, admin odnawiając — nie zapisuje nic (odnowienie „darmowe" w raportach). Brak ograniczenia unikalności `Payment(member_id, month_year)` — możliwe duplikaty.
**Zakres:**
- Decyzja + ujednolicenie: odnowienie przez admina również tworzy rozliczoną płatność (lub świadomie oznaczane jako „korekta administracyjna").
- `UniqueConstraint(member_id, month_year)` na modelu `Payment`; `client renew` i `initiate` nie tworzą duplikatu (upsert).
- Test: dwa odnowienia w jednym miesiącu = jeden wpis płatności.
**Pliki:** `models.py`, `blueprints/admin.py`, `blueprints/client.py`, `services.py`, `tests/test_payment.py`

#### ✅ B33 · Kaskady i integralność przy usuwaniu klienta — ZROBIONE
**✅ Wynik:** Kaskady `delete-orphan` dla `Member→WaitlistEntry/Payment` i `ClassSession→WaitlistEntry`; `PRAGMA foreign_keys=ON` dla SQLite (event listener, bezpieczny dla innych silników). Usunięcie klienta/zajęć nie zostawia osieroconych wierszy ani nie wywala na FK. Wybrana opcja: **usuwanie** płatności wraz z klientem (spójne z twardym delete). **+2 testy.**
**Pliki:** `models.py`, `extensions.py`, `tests/test_admin.py`

**Problem:** `WaitlistEntry` i `Payment` nie mają kaskady od `Member` — usunięcie klienta zostawia wiszące wpisy (SQLite domyślnie nie egzekwuje FK).
**Zakres:**
- Kaskada/`ondelete` dla `WaitlistEntry` (usuń) i `Payment` (decyzja: usuń vs zachowaj jako anonimowe „były klient").
- Włączyć `PRAGMA foreign_keys=ON` dla SQLite (event listener w `extensions.py`).
- Test: usunięcie klienta nie zostawia osieroconych wpisów / nie wywala widoku płatności.
**Pliki:** `models.py`, `extensions.py`, `tests/`

#### 🟡 B34 · Drobne guardy logiki — CZĘŚCIOWO ZROBIONE
- ✅ **B34a:** Obecność można zapisać tylko dla sesji minionych/dzisiejszych — guard serwerowy w `trainer_attendance` (POST).
- ⬜ **B34b:** (Opcjonalnie) zabezpieczenie wyścigu pojemności w `book()` — świadomie odłożone (przy SQLite + 1 proces teoretyczne).
**Pliki:** `blueprints/trainer.py`

---

### SEKCJA 9 — Gotowość produkcyjna i bezpieczeństwo · **P1**

#### ✅ B35 · Debug i SECRET_KEY za zmiennymi środowiskowymi — ZROBIONE
**✅ Wynik:** `debug` czytany z `FLASK_DEBUG` (domyślnie wyłączony); brak `SECRET_KEY` przy `FLASK_ENV=production` → `RuntimeError` na starcie (dev nadal ma fallback). **+1 test.**
**Pliki:** `app.py`, `.env.example`, `tests/test_auth.py`

#### ✅ B36 · Migracje bazy (Flask-Migrate / Alembic) — ZROBIONE
**✅ Wynik:** `Flask-Migrate` wpięty (`migrate.init_app(..., render_as_batch=True)` — tryb batch dla SQLite); pierwsza migracja `a5403d93b3fc` z pełnego schematu (10 tabel + `uq_payment_member_month`); instrukcja w README (`flask db upgrade/migrate/current`, `stamp head`).
**Pliki:** `requirements.txt`, `extensions.py`, `app.py`, `migrations/`, `README.md`

#### ✅ B37 · Hardening sesji i nagłówków — ZROBIONE
**✅ Wynik:** `SESSION_COOKIE_HTTPONLY=True`, `SAMESITE=Lax`, `SECURE` w produkcji; nagłówki `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` przez `after_request`. **+1 test.**
**Pliki:** `app.py`, `tests/test_auth.py`

#### ⬜ B38 · Rate-limiting logowania — DO ZROBIENIA
**Zakres:** `Flask-Limiter` na `/login` (np. 5 prób/min/IP), czytelny komunikat po przekroczeniu.
**Pliki:** `app.py`, `blueprints/auth.py`, `requirements.txt`

#### ⬜ B39 · Serwer WSGI + Docker + CI — DO ZROBIENIA · 📌 NA SAM KONIEC (wykończeniówka)
> **Decyzja (2026-06-25):** Docker/konteneryzacja to wykończeniówka — robimy ją jako **ostatnie zadanie projektu**, po wszystkich funkcjach i poprawkach. Nie zaczynać wcześniej.
**Zakres:** `waitress`/`gunicorn` zamiast `app.run`, `Dockerfile` + `docker-compose` (z Postgresem), GitHub Actions uruchamiające `pytest` na push.
**Pliki:** `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `requirements.txt`, `README.md`

---

### SEKCJA 10 — Nowe funkcje · **P1–P2**

#### ✅ B40 · Rejestracja klienta (self-signup) — ZROBIONE · P1
**✅ Wynik:** Publiczna `/register` → `UserService.register_client()` (walidacja, auto-login wg konwencji, karnet na pierwszy okres, auto-zalogowanie). Linki na stronie logowania. **+4 testy.**
**Pliki:** `blueprints/auth.py`, `services.py`, `templates/{register,login}.html`, `tests/test_auth.py`

#### ✅ B41 · Reset hasła („zapomniałem hasła") — ZROBIONE · P1
**✅ Wynik:** Model `PasswordResetToken` (token jednorazowy, TTL 60 min) + `/forgot-password` (anty-enumeracja) i `/reset-password/<token>`. Brak e-maila → link pokazywany w devie (w prod do wysłania mailem). Migracja `ade5177d6fd1`. **+5 testów.**
**Pliki:** `models.py`, `services.py`, `blueprints/auth.py`, `templates/{forgot,reset}_password.html`, `templates/login.html`, `migrations/`, `tests/test_auth.py`

#### ✅ B42 · Warstwa powiadomień (pod Observer) — ZROBIONE · P1
**✅ Wynik:** Model `Notification` + `NotificationService` (push/for_user/unread_count/mark_all_read/notify_expiring). Podpięcia: **awans z kolejki** (Observer — koniec „cichego" awansu), **potwierdzenie płatności** (`PaymentService.confirm`), **wygasający karnet ≤7 dni** (dashboard, z dedupem). „Dzwonek" z licznikiem w sidebarze (context processor) + strona `/notifications` z „oznacz przeczytane". Migracja `ece940d7a6fe`. **+7 testów.**
**Pliki:** `models.py`, `services.py`, `app.py`, `blueprints/{auth,client}.py`, `templates/{base,notifications}.html`, `migrations/`, `tests/test_notifications.py`

#### ⬜ B43 · Historia obecności klienta — DO ZROBIENIA · P2
Widok „Moja frekwencja" (był/nieobecny per sesja, % obecności). Trener oznacza, klient dziś tego nie widzi.
**Pliki:** `blueprints/client.py`, `templates/client/`, `tests/`

#### ⬜ B44 · Raport wynagrodzeń trenerów — DO ZROBIENIA · P2
`hourly_rate` istnieje, ale nigdzie nie liczy kosztów. Raport: stawka × przeprowadzone sesje/godziny per trener.
**Pliki:** `blueprints/admin.py`, `templates/admin/`, `tests/`

#### ⬜ B45 · Paginacja list — DO ZROBIENIA · P2
Paginacja dla członków / płatności / rezerwacji (dziś ładują wszystko naraz).
**Pliki:** `blueprints/admin.py`, `blueprints/client.py`, `templates/`

---

### SEKCJA 11 — Jakość kodu · **P2**

#### ⬜ B46 · Konsolidacja warstwy serwisowej — DO ZROBIENIA
Admin/trener operują na modelach wprost; `subscription_end` liczone inline w `admin.py` zamiast przez `MemberService`/Strategy. Przepiąć tworzenie/edycję/odnowienie na serwisy.
**Pliki:** `blueprints/admin.py`, `blueprints/trainer.py`, `services.py`

#### ⬜ B47 · DRY: wspólne stałe i etykiety — DO ZROBIENIA
`DAY_ORDER`/`DAYS` zduplikowane w 3 plikach, `_sub_label()` powiela `Strategy.label()`. Wydzielić do jednego modułu; importy lokalne → top-level.
**Pliki:** `constants.py` (nowy) / `services.py`, `blueprints/*`

---

### SEKCJA 12 — Testy i dokumentacja · **P1**

#### ⬜ B48 · Domknięcie testów — DO ZROBIENIA
- Trasy trenera (propose/edit/attendance/members) — dziś prawie nietknięte.
- `generate_sessions` / rolling-generacja (B31).
- IDOR / autoryzacja między użytkownikami (klient A nie zobaczy płatności/rezerwacji klienta B).
**Pliki:** `tests/test_trainer.py` (nowy), `tests/test_sessions.py`, `tests/test_auth.py`

#### ⬜ B49 · Aktualizacja dokumentacji — DO ZROBIENIA
README: liczba testów 67 → **90**, opis nowych funkcji (rejestracja, powiadomienia, migracje), sekcja „uruchomienie produkcyjne". Utrzymać BACKLOG.
**Pliki:** `README.md`, `BACKLOG.md`

---

## Kolejność realizacji (zalecana, audyt 2026-06-24)

```
P0 (dziury logiczne):   B29 → B30 → B31 → B32 → B33 → B34
P1 (produkcja + bazowe): B35 → B36 → B37 → B38 → B39
                                  ↓
P1 (funkcje + testy):    B40 → B41 → B42 → B48 → B49
                                  ↓
P2 (reszta funkcji/jakość): B43 → B44 → B45 → B46 → B47
```

**Twarde zależności:**
- B36 (migracje) najlepiej **przed** B32/B33 (zmiany schematu: constrainty, kaskady) — żeby zmiany schematu szły migracją, nie dropem.
- B42 (powiadomienia) wzmacnia B30 (info o odwołaniu) i B41 (reset hasła e-mailem).
- Każde zadanie z P0 domyka się testem (B48 zbiera resztę).

---

*Ostatnia aktualizacja: 2026-06-25 · branch `dev` · **125 testów** · zrobione: B29–B33, B34a, B35–B37, B40–B42 · pozostaje: B34b, B38, B43–B49, B39 (📌 sam koniec)*
