# 🗃️ Schemat bazy danych — GymManagement

Diagram związków encji (ERD) wygenerowany na podstawie modeli SQLAlchemy (`models.py`).
**12 tabel.** Diagram renderuje się automatycznie na GitHubie.

```mermaid
erDiagram
    USERS ||--o| MEMBERS : "profil klienta"
    USERS ||--o| TRAINERS : "profil trenera"
    USERS ||--o{ NOTIFICATIONS : "otrzymuje"
    USERS ||--o{ PASSWORD_RESET_TOKENS : "generuje"
    TRAINERS ||--o{ GYM_CLASSES : "prowadzi"
    GYM_CLASSES ||--o{ CLASS_SESSIONS : "ma terminy"
    MEMBERS ||--o{ BOOKINGS : "rezerwuje"
    CLASS_SESSIONS ||--o{ BOOKINGS : "dotyczy"
    MEMBERS ||--o{ WAITLIST : "czeka w kolejce"
    CLASS_SESSIONS ||--o{ WAITLIST : "ma kolejkę"
    MEMBERS ||--o{ PAYMENTS : "opłaca"

    USERS {
        int id PK
        string username UK
        string password_hash
        string role "admin | trainer | client"
    }
    MEMBERS {
        int id PK
        int user_id FK
        string first_name
        string last_name
        string phone
        datetime joined_at
        string subscription_type "monthly | annual | day_pass"
        date subscription_end
    }
    TRAINERS {
        int id PK
        int user_id FK
        string first_name
        string last_name
        string specialization
        float hourly_rate
    }
    NOTIFICATIONS {
        int id PK
        int user_id FK
        string message
        string icon
        string url
        bool read
        datetime created_at
    }
    PASSWORD_RESET_TOKENS {
        int id PK
        int user_id FK
        string token UK
        datetime expires_at
        bool used
    }
    GYM_CLASSES {
        int id PK
        int trainer_id FK
        string name
        text description
        int max_capacity
        string schedule_day
        string schedule_time
        int duration_minutes
        int frequency_weeks
        date start_date
        string status "pending | approved | rejected"
        text rejection_note
    }
    CLASS_SESSIONS {
        int id PK
        int class_id FK
        date session_date
        bool cancelled
    }
    BOOKINGS {
        int id PK
        int member_id FK
        int session_id FK
        datetime booked_at
        string status "confirmed | cancelled"
        bool attended
    }
    WAITLIST {
        int id PK
        int member_id FK
        int session_id FK
        datetime added_at
    }
    PAYMENTS {
        int id PK
        int member_id FK
        float amount
        string month_year "YYYY-MM (UK z member_id)"
        string status "pending | completed"
        string transfer_number
        datetime created_at
        datetime paid_at
    }
    EQUIPMENT {
        int id PK
        string name
        string category
        string status "working | maintenance | broken"
        date purchase_date
    }
    CONTACT_OPTIONS {
        int id PK
        string label
        string value
        string icon
    }
```

---

## Opis relacji

| Relacja | Typ | Klucz obcy | Kaskada usuwania |
|---------|-----|-----------|------------------|
| `User` → `Member` | 1 : 0..1 | `members.user_id` | ✅ delete-orphan |
| `User` → `Trainer` | 1 : 0..1 | `trainers.user_id` | ✅ delete-orphan |
| `User` → `Notification` | 1 : N | `notifications.user_id` | ✅ delete-orphan |
| `User` → `PasswordResetToken` | 1 : N | `password_reset_tokens.user_id` | ✅ delete-orphan |
| `Trainer` → `GymClass` | 1 : N | `gym_classes.trainer_id` | — |
| `GymClass` → `ClassSession` | 1 : N | `class_sessions.class_id` | ✅ delete-orphan |
| `Member` → `Booking` | 1 : N | `bookings.member_id` | ✅ delete-orphan |
| `ClassSession` → `Booking` | 1 : N | `bookings.session_id` | ✅ delete-orphan |
| `Member` → `WaitlistEntry` | 1 : N | `waitlist.member_id` | ✅ delete-orphan |
| `ClassSession` → `WaitlistEntry` | 1 : N | `waitlist.session_id` | ✅ delete-orphan |
| `Member` → `Payment` | 1 : N | `payments.member_id` | ✅ delete-orphan |

**Tabele bez relacji (słownikowe):** `Equipment`, `ContactOption`.

**Ograniczenia unikalności:** `users.username`, `password_reset_tokens.token`,
`payments(member_id, month_year)` — jeden wpis płatności na klienta i okres rozliczeniowy.

**Tabela łącząca M:N:** `Booking` i `WaitlistEntry` realizują relację wiele-do-wielu
między `Member` a `ClassSession` (klient ↔ sesja zajęć).
