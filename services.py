"""
Warstwa serwisowa aplikacji GymApp.

Wzorce projektowe zastosowane w tym module:
  - Strategy   — SubscriptionStrategy + konkretne implementacje typów karnetów
  - Factory    — SubscriptionFactory tworząca odpowiednią strategię na podstawie klucza
  - Service    — BookingService, MemberService, TrainerService, EquipmentService
                 enkapsulujące logikę biznesową i oddzielające ją od warstwy tras (Flask routes)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta

from models import db, User, Member, Trainer, GymClass, Booking, Equipment


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
    """Serwis obsługi rezerwacji zajęć grupowych."""

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

        db.session.add(Booking(member_id=member_id, class_id=class_id, status="confirmed"))
        db.session.commit()
        return True, f"Zapisano na zajęcia: {gym_class.name}!"

    @staticmethod
    def cancel(booking_id: int, member_id: int) -> tuple[bool, str]:
        """Anuluje rezerwację. Zwraca (sukces, komunikat)."""
        booking = db.session.get(Booking, booking_id)
        if booking is None:
            return False, "Rezerwacja nie istnieje."
        if booking.member_id != member_id:
            return False, "Brak dostępu do tej rezerwacji."
        if booking.status == "cancelled":
            return False, "Rezerwacja jest już anulowana."

        booking.status = "cancelled"
        db.session.commit()
        return True, "Rezerwacja anulowana."


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
