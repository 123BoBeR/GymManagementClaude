"""
Warstwa serwisowa aplikacji GymApp.

Wzorce projektowe zastosowane w tym module:
  - Strategy   — SubscriptionStrategy + konkretne implementacje typów karnetów
  - Factory    — SubscriptionFactory tworząca odpowiednią strategię na podstawie klucza
  - Service    — BookingService, MemberService, TrainerService, EquipmentService
                 enkapsulujące logikę biznesową i oddzielające ją od warstwy tras (Flask routes)
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone

from models import db, User, Member, Trainer, GymClass, Booking, Equipment, Payment, Waitlist


_PL_MONTHS = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
    5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
    9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień",
}

BANK_ACCOUNT = "74 1160 2202 0000 0003 1752 9304"

SUBSCRIPTION_PRICES: dict[str, float] = {
    "monthly":  99.0,
    "annual":  799.0,
    "day_pass": 29.0,
}


# ── Observer Pattern: obserwatorzy zdarzeń rezerwacji ────────────────────────

class BookingObserver(ABC):
    """
    Abstrakcyjny obserwator zdarzeń rezerwacji.
    Implementacje reagują na anulowanie i potwierdzenie rezerwacji.
    """

    @abstractmethod
    def on_cancelled(self, booking: Booking) -> None:
        """Wywoływany gdy rezerwacja zostaje anulowana."""

    def on_confirmed(self, booking: Booking) -> None:
        """Wywoływany gdy rezerwacja zostaje potwierdzona. Domyślnie brak akcji."""


class WaitlistObserver(BookingObserver):
    """
    Obserwator listy oczekujących.
    Po anulowaniu rezerwacji automatycznie przydziela wolne miejsce
    pierwszej osobie z kolejki oczekujących na te zajęcia.
    """

    def on_cancelled(self, booking: Booking) -> None:
        next_entry = (Waitlist.query
                      .filter_by(class_id=booking.class_id)
                      .order_by(Waitlist.added_at)
                      .first())
        if next_entry is None:
            return
        new_booking = Booking(
            member_id=next_entry.member_id,
            class_id=next_entry.class_id,
            status='confirmed',
        )
        db.session.add(new_booking)
        db.session.delete(next_entry)
        db.session.commit()


# ── Strategy Pattern: strategie typów karnetów ───────────────────────────────

class SubscriptionStrategy(ABC):
    """Abstrakcyjna strategia karnetu — definiuje interfejs dla wszystkich typów."""

    @abstractmethod
    def label(self) -> str:
        """Polska nazwa wyświetlana w UI."""

    @abstractmethod
    def duration_days(self) -> int:
        """Liczba dni ważności karnetu."""

    @abstractmethod
    def end_date(self, start: date) -> date:
        """Oblicza datę końca karnetu na podstawie daty startu."""

    def is_active(self, member: Member) -> bool:
        """Sprawdza czy karnet klienta jest aktywny."""
        return member.subscription_end is not None and member.subscription_end >= date.today()

    def days_remaining(self, member: Member) -> int | None:
        """Zwraca liczbę pozostałych dni lub None gdy brak daty."""
        if member.subscription_end is None:
            return None
        return (member.subscription_end - date.today()).days


class MonthlySubscription(SubscriptionStrategy):
    """Karnet miesięczny — 30 dni."""

    def label(self) -> str:
        return "Miesięczny"

    def duration_days(self) -> int:
        return 30

    def end_date(self, start: date) -> date:
        return start + timedelta(days=30)


class AnnualSubscription(SubscriptionStrategy):
    """Karnet roczny — 365 dni."""

    def label(self) -> str:
        return "Roczny"

    def duration_days(self) -> int:
        return 365

    def end_date(self, start: date) -> date:
        return start + timedelta(days=365)


class DayPassSubscription(SubscriptionStrategy):
    """Karnet dzienny — 1 dzień."""

    def label(self) -> str:
        return "Karnet dzienny"

    def duration_days(self) -> int:
        return 1

    def end_date(self, start: date) -> date:
        return start + timedelta(days=1)


# ── Factory Pattern: tworzenie strategii karnetu ─────────────────────────────

class SubscriptionFactory:
    """
    Fabryka strategii karnetów.
    Tworzy odpowiednią strategię na podstawie klucza tekstowego
    bez konieczności znajomości konkretnych klas przez kod wywołujący.
    """

    _registry: dict[str, type[SubscriptionStrategy]] = {
        "monthly":  MonthlySubscription,
        "annual":   AnnualSubscription,
        "day_pass": DayPassSubscription,
    }

    @classmethod
    def create(cls, sub_type: str) -> SubscriptionStrategy:
        """Tworzy i zwraca strategię karnetu dla podanego klucza."""
        strategy_class = cls._registry.get(sub_type)
        if strategy_class is None:
            raise ValueError(f"Nieznany typ karnetu: '{sub_type}'. "
                             f"Dostępne: {list(cls._registry)}")
        return strategy_class()

    @classmethod
    def available_types(cls) -> list[str]:
        """Zwraca listę wszystkich zarejestrowanych typów karnetów."""
        return list(cls._registry)

    @classmethod
    def label_for(cls, sub_type: str) -> str:
        """Zwraca polską nazwę typu karnetu."""
        try:
            return cls.create(sub_type).label()
        except ValueError:
            return sub_type


# ── Service Layer ─────────────────────────────────────────────────────────────

class BookingService:
    """
    Serwis obsługi rezerwacji zajęć grupowych.
    Wspiera wzorzec Observer — lista obserwatorów jest powiadamiana
    o zmianach statusu rezerwacji.
    """

    _observers: list[BookingObserver] = [WaitlistObserver()]

    @classmethod
    def _notify_cancelled(cls, booking: Booking) -> None:
        for obs in cls._observers:
            obs.on_cancelled(booking)

    @classmethod
    def _notify_confirmed(cls, booking: Booking) -> None:
        for obs in cls._observers:
            obs.on_confirmed(booking)

    @staticmethod
    def book(member_id: int, class_id: int) -> tuple[bool, str]:
        """Zapisuje klienta na zajęcia. Zwraca (sukces, komunikat)."""
        gym_class = db.session.get(GymClass, class_id)
        if gym_class is None:
            return False, "Zajęcia nie istnieją."

        confirmed = Booking.query.filter_by(class_id=class_id, status="confirmed").count()
        if confirmed >= gym_class.max_capacity:
            return False, "Brak wolnych miejsc na te zajęcia."

        if Booking.query.filter_by(member_id=member_id, class_id=class_id,
                                   status="confirmed").first():
            return False, "Jesteś już zapisany na te zajęcia."

        conflict = (Booking.query
                    .join(GymClass, Booking.class_id == GymClass.id)
                    .filter(
                        Booking.member_id == member_id,
                        Booking.status == "confirmed",
                        GymClass.schedule_day == gym_class.schedule_day,
                        GymClass.schedule_time == gym_class.schedule_time,
                    ).first())
        if conflict:
            return False, (f"Masz już rezerwację w tym terminie "
                           f"({gym_class.schedule_day} {gym_class.schedule_time}).")

        db.session.add(Booking(member_id=member_id, class_id=class_id, status="confirmed"))
        db.session.commit()
        return True, f"Zapisano na zajęcia: {gym_class.name}!"

    @classmethod
    def cancel(cls, booking_id: int, member_id: int) -> tuple[bool, str]:
        """Anuluje rezerwację i powiadamia obserwatorów. Zwraca (sukces, komunikat)."""
        booking = db.session.get(Booking, booking_id)
        if booking is None:
            return False, "Rezerwacja nie istnieje."
        if booking.member_id != member_id:
            return False, "Brak dostępu do tej rezerwacji."
        if booking.status == "cancelled":
            return False, "Rezerwacja jest już anulowana."

        booking.status = "cancelled"
        db.session.commit()
        cls._notify_cancelled(booking)
        return True, "Rezerwacja anulowana."


class WaitlistService:
    """Serwis zarządzania listą oczekujących na zajęcia."""

    @staticmethod
    def join(member_id: int, class_id: int) -> tuple[bool, str]:
        """Dołącza klienta do kolejki oczekujących. Zwraca (sukces, komunikat)."""
        gym_class = db.session.get(GymClass, class_id)
        if gym_class is None:
            return False, "Zajęcia nie istnieją."

        if Booking.query.filter_by(member_id=member_id, class_id=class_id,
                                   status="confirmed").first():
            return False, "Masz już aktywną rezerwację na te zajęcia."

        if Waitlist.query.filter_by(member_id=member_id, class_id=class_id).first():
            return False, "Jesteś już na liście oczekujących."

        db.session.add(Waitlist(member_id=member_id, class_id=class_id))
        db.session.commit()
        pos = Waitlist.query.filter_by(class_id=class_id).count()
        return True, f"Dodano do kolejki oczekujących (pozycja {pos})."

    @staticmethod
    def leave(member_id: int, class_id: int) -> tuple[bool, str]:
        """Usuwa klienta z listy oczekujących."""
        entry = Waitlist.query.filter_by(member_id=member_id, class_id=class_id).first()
        if not entry:
            return False, "Nie ma Cię na liście oczekujących."
        db.session.delete(entry)
        db.session.commit()
        return True, "Usunięto z listy oczekujących."

    @staticmethod
    def position(member_id: int, class_id: int) -> int | None:
        """Zwraca pozycję klienta w kolejce lub None."""
        entries = (Waitlist.query.filter_by(class_id=class_id)
                   .order_by(Waitlist.added_at).all())
        for i, e in enumerate(entries, start=1):
            if e.member_id == member_id:
                return i
        return None


class UserService:
    """Serwis zarządzania kontami użytkowników."""

    @staticmethod
    def change_password(user: User, old_password: str,
                        new_password: str, confirm: str) -> tuple[bool, str]:
        """Zmienia hasło użytkownika po weryfikacji starego."""
        if not user.check_password(old_password):
            return False, "Stare hasło jest nieprawidłowe."
        if len(new_password) < 6:
            return False, "Nowe hasło musi mieć co najmniej 6 znaków."
        if new_password != confirm:
            return False, "Nowe hasła nie są zgodne."
        user.set_password(new_password)
        db.session.commit()
        return True, "Hasło zmienione pomyślnie."


class MemberService:
    """Serwis obsługi klientów siłowni."""

    @staticmethod
    def create(username: str, password: str, first_name: str, last_name: str,
               phone: str, sub_type: str, sub_end: date | None) -> tuple[bool, str]:
        """Tworzy nowego klienta razem z kontem użytkownika."""
        if User.query.filter_by(username=username).first():
            return False, "Nazwa użytkownika już istnieje."

        user = User(username=username, role="client")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        member = Member(user_id=user.id, first_name=first_name, last_name=last_name,
                        phone=phone, subscription_type=sub_type, subscription_end=sub_end)
        db.session.add(member)
        db.session.commit()
        return True, "Klient dodany pomyślnie."

    @staticmethod
    def update(member: Member, first_name: str, last_name: str,
               phone: str, sub_type: str, sub_end: date | None) -> tuple[bool, str]:
        """Aktualizuje dane klienta."""
        member.first_name = first_name
        member.last_name = last_name
        member.phone = phone
        member.subscription_type = sub_type
        member.subscription_end = sub_end
        db.session.commit()
        return True, "Dane zaktualizowane."

    @staticmethod
    def delete(member: Member) -> tuple[bool, str]:
        """Usuwa klienta wraz z kontem i rezerwacjami (cascade)."""
        db.session.delete(member.user)
        db.session.commit()
        return True, "Klient usunięty."

    @staticmethod
    def is_active(member: Member) -> bool:
        """Sprawdza czy karnet klienta jest aktywny."""
        strategy = SubscriptionFactory.create(member.subscription_type or "monthly")
        return strategy.is_active(member)


class TrainerService:
    """Serwis obsługi trenerów."""

    @staticmethod
    def create(username: str, password: str, first_name: str, last_name: str,
               specialization: str, hourly_rate: float) -> tuple[bool, str]:
        """Tworzy nowego trenera razem z kontem użytkownika."""
        if User.query.filter_by(username=username).first():
            return False, "Nazwa użytkownika już istnieje."

        user = User(username=username, role="trainer")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        trainer = Trainer(user_id=user.id, first_name=first_name, last_name=last_name,
                          specialization=specialization, hourly_rate=hourly_rate)
        db.session.add(trainer)
        db.session.commit()
        return True, "Trener dodany pomyślnie."

    @staticmethod
    def update(trainer: Trainer, first_name: str, last_name: str,
               specialization: str, hourly_rate: float) -> tuple[bool, str]:
        """Aktualizuje dane trenera."""
        trainer.first_name = first_name
        trainer.last_name = last_name
        trainer.specialization = specialization
        trainer.hourly_rate = hourly_rate
        db.session.commit()
        return True, "Dane trenera zaktualizowane."

    @staticmethod
    def delete(trainer: Trainer) -> tuple[bool, str]:
        """Usuwa trenera wraz z kontem (cascade)."""
        db.session.delete(trainer.user)
        db.session.commit()
        return True, "Trener usunięty."


class EquipmentService:
    """Serwis obsługi sprzętu siłowni."""

    @staticmethod
    def create(name: str, category: str, status: str,
               purchase_date: date | None) -> tuple[bool, str]:
        """Dodaje nowy sprzęt do ewidencji."""
        db.session.add(Equipment(name=name, category=category,
                                 status=status, purchase_date=purchase_date))
        db.session.commit()
        return True, "Sprzęt dodany."

    @staticmethod
    def update(equipment: Equipment, name: str, category: str,
               status: str, purchase_date: date | None) -> tuple[bool, str]:
        """Aktualizuje dane sprzętu."""
        equipment.name = name
        equipment.category = category
        equipment.status = status
        equipment.purchase_date = purchase_date
        db.session.commit()
        return True, "Dane sprzętu zaktualizowane."

    @staticmethod
    def delete(equipment: Equipment) -> tuple[bool, str]:
        """Usuwa sprzęt z ewidencji."""
        db.session.delete(equipment)
        db.session.commit()
        return True, "Sprzęt usunięty."


class PaymentService:
    """Serwis obsługi płatności (symulowanych)."""

    @staticmethod
    def amount_for(member: Member) -> float:
        return SUBSCRIPTION_PRICES.get(member.subscription_type or "monthly", 99.0)

    @staticmethod
    def generate_transfer_number() -> str:
        n = random.randint(100_000_000_000, 999_999_999_999)
        s = str(n)
        return f"TRF-{s[0:4]}-{s[4:8]}-{s[8:12]}"

    @staticmethod
    def months_for_member(member: Member) -> list[dict]:
        """Generuje listę miesięcy od dołączenia do dziś z informacją o płatności."""
        start = (member.joined_at.date() if member.joined_at else date.today()).replace(day=1)
        today_first = date.today().replace(day=1)

        result = []
        current = start
        while current <= today_first:
            month_str = current.strftime("%Y-%m")
            payment = Payment.query.filter_by(
                member_id=member.id, month_year=month_str
            ).first()
            result.append({
                "month_year": month_str,
                "label": f"{_PL_MONTHS[current.month]} {current.year}",
                "status": payment.status if payment else "pending",
                "payment_id": payment.id if payment else None,
                "amount": payment.amount if payment else PaymentService.amount_for(member),
                "paid_at": payment.paid_at if payment else None,
                "transfer_number": payment.transfer_number if payment else None,
            })
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return result

    @staticmethod
    def initiate(member_id: int, month_year: str) -> tuple[bool, dict]:
        """Tworzy lub pobiera oczekującą płatność za podany miesiąc."""
        member = db.session.get(Member, member_id)
        if not member:
            return False, {"error": "Klient nie istnieje."}

        existing = Payment.query.filter_by(member_id=member_id, month_year=month_year).first()
        if existing and existing.status == "completed":
            return False, {"error": "Ten miesiąc jest już opłacony."}

        if not existing:
            payment = Payment(
                member_id=member_id,
                amount=PaymentService.amount_for(member),
                month_year=month_year,
                status="pending",
                transfer_number=PaymentService.generate_transfer_number(),
            )
            db.session.add(payment)
            db.session.commit()
        else:
            payment = existing

        return True, {
            "payment_id": payment.id,
            "transfer_number": payment.transfer_number,
            "amount": payment.amount,
            "month_year": month_year,
            "bank_account": BANK_ACCOUNT,
        }

    @staticmethod
    def confirm(payment_id: int, member_id: int) -> tuple[bool, str]:
        """Potwierdza płatność (symulacja)."""
        payment = db.session.get(Payment, payment_id)
        if not payment:
            return False, "Płatność nie istnieje."
        if payment.member_id != member_id:
            return False, "Brak dostępu."
        if payment.status == "completed":
            return False, "Płatność już zrealizowana."

        payment.status = "completed"
        payment.paid_at = datetime.now(timezone.utc)
        db.session.commit()
        return True, "Płatność zrealizowana pomyślnie."
