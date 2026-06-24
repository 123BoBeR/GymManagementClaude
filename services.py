"""Warstwa serwisowa + wzorce projektowe (OOP).

Zebrane w jednym miejscu wzorce wykorzystane w projekcie:

- Strategy       : SubscriptionStrategy + 3 konkretne strategie karnetów
- Factory        : SubscriptionFactory.create()
- Observer       : BookingObserver + WaitlistObserver (awans z listy oczekujących)
- Service Layer  : BookingService, WaitlistService, PaymentService,
                   MemberService, UserService — logika biznesowa odseparowana
                   od tras Flask (blueprintów).
"""

import random
import unicodedata
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone, timedelta

from extensions import db
from models import User, Member, GymClass, ClassSession, Booking, WaitlistEntry, Payment


def _slugify(text):
    """Usuwa polskie znaki diakrytyczne i zostawia same małe litery/cyfry."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # ł nie rozkłada się przez NFKD — podmień ręcznie
    text = text.replace('ł', 'l').replace('Ł', 'L')
    return ''.join(c for c in text.lower() if c.isalnum())

BANK_ACCOUNT = "PL 12 3456 7890 1234 5678 9012 3456"


# ── Pomocnicze: arytmetyka miesięcy ──────────────────────────────────────────

def _add_months(d, n):
    """Przesuwa datę o n miesięcy, ląduje na 1. dniu wynikowego miesiąca."""
    m = d.month - 1 + n
    y = d.year + m // 12
    return date(y, m % 12 + 1, 1)


def _end_of_month(d):
    """Ostatni dzień miesiąca, w którym leży data d."""
    return _add_months(d, 1) - timedelta(days=1)


_PL_MONTHS = ['', 'styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec',
              'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień']


def month_label(d):
    """Etykieta miesiąca, np. 'lipiec 2026' (zamiast konkretnej daty)."""
    if not d:
        return '—'
    return f"{_PL_MONTHS[d.month]} {d.year}"


# ── Strategy: typy karnetów ───────────────────────────────────────────────────

class SubscriptionStrategy(ABC):
    """Wspólny interfejs dla typów karnetów.

    Model jest miesięczny: karnet jest aktywny w danym miesiącu albo nie —
    `subscription_end` to zawsze ostatni dzień ostatniego opłaconego miesiąca.
    """
    code = None

    @abstractmethod
    def label(self):
        ...

    @abstractmethod
    def price(self):
        ...

    @abstractmethod
    def extend(self, current_end, today=None):
        """Zwraca nową datę ważności po dokupieniu jednego okresu.

        Jeśli karnet jest jeszcze aktywny — dolicza okres do bieżącej ważności
        (czerwiec + miesiąc = lipiec). Jeśli wygasł lub go nie ma — liczy od
        bieżącego miesiąca.
        """
        ...


class _MonthlyBased(SubscriptionStrategy):
    """Karnet rozliczany w pełnych miesiącach (miesięczny, roczny)."""
    months = 1

    def extend(self, current_end, today=None):
        today = today or date.today()
        if current_end and current_end >= today:
            return _end_of_month(_add_months(current_end, self.months))
        return _end_of_month(_add_months(today, self.months - 1))


class MonthlySubscription(_MonthlyBased):
    code = 'monthly'
    months = 1

    def label(self):
        return 'Miesięczny'

    def price(self):
        return 99.0


class AnnualSubscription(_MonthlyBased):
    code = 'annual'
    months = 12

    def label(self):
        return 'Roczny'

    def price(self):
        return 799.0


class DayPassSubscription(SubscriptionStrategy):
    code = 'day_pass'

    def label(self):
        return 'Dzienny'

    def price(self):
        return 29.0

    def extend(self, current_end, today=None):
        # Wejściówka jednodniowa — ważna tylko w dniu zakupu.
        return today or date.today()


# ── Factory ───────────────────────────────────────────────────────────────────

class SubscriptionFactory:
    """Tworzy odpowiednią strategię na podstawie klucza tekstowego."""
    _registry = {
        'monthly': MonthlySubscription,
        'annual': AnnualSubscription,
        'day_pass': DayPassSubscription,
    }

    @classmethod
    def create(cls, sub_type):
        strategy_cls = cls._registry.get(sub_type)
        if strategy_cls is None:
            raise ValueError(f"Nieznany typ karnetu: {sub_type}")
        return strategy_cls()

    @classmethod
    def all_types(cls):
        return [strategy_cls() for strategy_cls in cls._registry.values()]


# ── Observer: powiadomienia o zwolnieniu miejsca ─────────────────────────────

class BookingObserver(ABC):
    @abstractmethod
    def on_booking_cancelled(self, session_id):
        ...


class WaitlistObserver(BookingObserver):
    """Po anulowaniu rezerwacji awansuje pierwszą osobę z listy oczekujących."""

    def on_booking_cancelled(self, session_id):
        nxt = (WaitlistEntry.query
               .filter_by(session_id=session_id)
               .order_by(WaitlistEntry.added_at)
               .first())
        if not nxt:
            return None
        db.session.add(Booking(
            member_id=nxt.member_id,
            session_id=session_id,
            status='confirmed',
        ))
        promoted_member_id = nxt.member_id
        db.session.delete(nxt)
        return promoted_member_id


# ── Service Layer: rezerwacje ────────────────────────────────────────────────

class BookingService:
    _observers = [WaitlistObserver()]

    @staticmethod
    def _to_minutes(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    @classmethod
    def book(cls, member_id, session_id):
        """Zwraca (ok: bool, komunikat: str)."""
        class_session = db.session.get(ClassSession, session_id)
        if class_session is None:
            return False, "Sesja nie istnieje."
        gym_class = class_session.gym_class

        if class_session.cancelled:
            return False, "Ta sesja została odwołana."
        if class_session.session_date < date.today():
            return False, "Nie można rezerwować przeszłych sesji."

        confirmed = Booking.query.filter_by(session_id=session_id, status='confirmed').count()
        if confirmed >= gym_class.max_capacity:
            return False, "Brak wolnych miejsc na tę sesję."

        if Booking.query.filter_by(member_id=member_id, session_id=session_id,
                                   status='confirmed').first():
            return False, "Jesteś już zapisany na tę sesję."

        # konflikt terminów — nakładanie się godzin tego samego dnia
        new_start = cls._to_minutes(gym_class.schedule_time)
        new_end = new_start + gym_class.duration_minutes
        same_day = (Booking.query
                    .filter_by(member_id=member_id, status='confirmed')
                    .join(ClassSession)
                    .filter(ClassSession.session_date == class_session.session_date)
                    .all())
        for b in same_day:
            ex_start = cls._to_minutes(b.gym_class.schedule_time)
            ex_end = ex_start + b.gym_class.duration_minutes
            if new_start < ex_end and ex_start < new_end:
                return False, (f'Konflikt terminów: "{b.gym_class.name}" '
                               f'({b.gym_class.schedule_day}, {b.gym_class.schedule_time}) '
                               f'pokrywa się z wybranymi zajęciami.')

        db.session.add(Booking(member_id=member_id, session_id=session_id, status='confirmed'))
        WaitlistEntry.query.filter_by(member_id=member_id, session_id=session_id).delete()
        db.session.commit()
        return True, (f'Zapisano na: {gym_class.name} '
                      f'({class_session.session_date.strftime("%d.%m.%Y")})!')

    @classmethod
    def cancel(cls, member_id, booking_id):
        """Anuluje rezerwację i powiadamia obserwatorów (Observer)."""
        booking = db.session.get(Booking, booking_id)
        if booking is None:
            return False, "Rezerwacja nie istnieje."
        if booking.member_id != member_id:
            return False, "Brak dostępu."

        booking.status = 'cancelled'
        db.session.flush()

        promoted = None
        for observer in cls._observers:
            result = observer.on_booking_cancelled(booking.session_id)
            promoted = promoted or result
        db.session.commit()

        if promoted:
            return True, ("Rezerwacja anulowana. Miejsce przekazano pierwszej "
                          "osobie z listy oczekujących.")
        return True, "Rezerwacja anulowana."


# ── Service Layer: lista oczekujących ────────────────────────────────────────

class WaitlistService:
    @staticmethod
    def join(member_id, session_id):
        if WaitlistEntry.query.filter_by(member_id=member_id, session_id=session_id).first():
            return False, "Już jesteś na liście oczekujących."
        db.session.add(WaitlistEntry(member_id=member_id, session_id=session_id))
        db.session.commit()
        pos = WaitlistEntry.query.filter_by(session_id=session_id).count()
        return True, f"Dodano na listę oczekujących — pozycja {pos}."

    @staticmethod
    def leave(member_id, session_id):
        deleted = WaitlistEntry.query.filter_by(
            member_id=member_id, session_id=session_id).delete()
        db.session.commit()
        if deleted:
            return True, "Usunięto z listy oczekujących."
        return False, "Nie było Cię na liście oczekujących."

    @staticmethod
    def position(member_id, session_id):
        entries = (WaitlistEntry.query
                   .filter_by(session_id=session_id)
                   .order_by(WaitlistEntry.added_at).all())
        for i, entry in enumerate(entries, start=1):
            if entry.member_id == member_id:
                return i
        return None


# ── Service Layer: płatności ─────────────────────────────────────────────────

class PaymentService:
    @staticmethod
    def amount_for(member):
        try:
            return SubscriptionFactory.create(member.subscription_type).price()
        except ValueError:
            return 0.0

    @staticmethod
    def generate_transfer_number():
        parts = [f"{random.randint(0, 9999):04d}" for _ in range(3)]
        return "TRF-" + "-".join(parts)

    @staticmethod
    def months_for_member(member, count=6):
        """Ostatnie `count` miesięcy wraz ze statusem płatności."""
        today = date.today()
        result = []
        year, month = today.year, today.month
        for _ in range(count):
            my = f"{year:04d}-{month:02d}"
            payment = Payment.query.filter_by(member_id=member.id, month_year=my).first()
            result.append({
                'month_year': my,
                'amount': PaymentService.amount_for(member),
                'status': payment.status if payment else 'pending',
                'payment_id': payment.id if payment else None,
                'transfer_number': payment.transfer_number if payment else None,
                'paid_at': payment.paid_at if payment else None,
            })
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return result

    @staticmethod
    def initiate(member_id, month_year):
        """Tworzy (lub zwraca istniejącą) płatność pending z numerem TRF."""
        member = db.session.get(Member, member_id)
        if member is None:
            return False, {"error": "Klient nie istnieje."}

        existing = Payment.query.filter_by(member_id=member_id, month_year=month_year).first()
        if existing and existing.status == 'completed':
            return False, {"error": "Płatność za ten miesiąc jest już opłacona."}

        if existing:
            payment = existing
        else:
            payment = Payment(
                member_id=member_id,
                amount=PaymentService.amount_for(member),
                month_year=month_year,
                status='pending',
                transfer_number=PaymentService.generate_transfer_number(),
            )
            db.session.add(payment)
            db.session.commit()

        return True, {
            "payment_id": payment.id,
            "transfer_number": payment.transfer_number,
            "amount": payment.amount,
            "bank_account": BANK_ACCOUNT,
            "month_year": payment.month_year,
        }

    @staticmethod
    def confirm(payment_id, member_id):
        payment = db.session.get(Payment, payment_id)
        if payment is None:
            return False, "Płatność nie istnieje."
        if payment.member_id != member_id:
            return False, "Brak dostępu do tej płatności."
        if payment.status == 'completed':
            return False, "Ta płatność jest już zatwierdzona."
        payment.status = 'completed'
        payment.paid_at = datetime.now(timezone.utc)
        db.session.commit()
        return True, "Płatność zatwierdzona."

    @staticmethod
    def total_revenue():
        completed = Payment.query.filter_by(status='completed').all()
        return sum(p.amount for p in completed)


# ── Service Layer: członkowie ────────────────────────────────────────────────

class MemberService:
    @staticmethod
    def update_profile(member, first_name=None, last_name=None, phone=None):
        if first_name is not None:
            member.first_name = first_name.strip()
        if last_name is not None:
            member.last_name = last_name.strip()
        if phone is not None:
            member.phone = phone.strip()
        db.session.commit()
        return True, "Dane zaktualizowane."

    @staticmethod
    def renew_subscription(member, sub_type, today=None):
        """Przedłuża karnet o jeden okres (Strategy + Factory).

        Cyklicznie: jeśli karnet jeszcze aktywny — dolicza do bieżącej ważności,
        w przeciwnym razie liczy od bieżącego miesiąca.
        """
        strategy = SubscriptionFactory.create(sub_type)
        member.subscription_type = sub_type
        member.subscription_end = strategy.extend(member.subscription_end, today)
        db.session.commit()
        return member.subscription_end

    @staticmethod
    def is_active(member, on_date=None):
        on_date = on_date or date.today()
        return member.subscription_end is not None and member.subscription_end >= on_date

    @staticmethod
    def days_left(member, on_date=None):
        on_date = on_date or date.today()
        if member.subscription_end is None:
            return None
        return (member.subscription_end - on_date).days


# ── Service Layer: użytkownicy ───────────────────────────────────────────────

class UserService:
    @staticmethod
    def generate_client_username(first_name, last_name):
        """Login klienta: [pierwsza litera imienia].[nazwisko].
        Przy kolizji bierze kolejną literę imienia (ja.kowalski, jan.kowalski...),
        a gdy całe imię nie wystarczy — dokłada numer."""
        first = _slugify(first_name)
        last = _slugify(last_name)
        if not first or not last:
            base = (first or last or 'klient')
            return UserService._unique(base)
        for i in range(1, len(first) + 1):
            candidate = f"{first[:i]}.{last}"
            if not User.query.filter_by(username=candidate).first():
                return candidate
        return UserService._unique(f"{first}.{last}")

    @staticmethod
    def generate_trainer_username(first_name, last_name):
        """Login trenera: t.[całe imię].[całe nazwisko] (przy kolizji + numer)."""
        first = _slugify(first_name)
        last = _slugify(last_name)
        base = f"t.{first}.{last}"
        return UserService._unique(base)

    @staticmethod
    def _unique(base):
        candidate, n = base, 1
        while User.query.filter_by(username=candidate).first():
            n += 1
            candidate = f"{base}{n}"
        return candidate

    @staticmethod
    def change_password(user, current, new, confirm):
        if not user.check_password(current):
            return False, "Aktualne hasło jest nieprawidłowe."
        if len(new) < 6:
            return False, "Nowe hasło musi mieć co najmniej 6 znaków."
        if new != confirm:
            return False, "Hasła nie są identyczne."
        user.set_password(new)
        db.session.commit()
        return True, "Hasło zmienione pomyślnie."
