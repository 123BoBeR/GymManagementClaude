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
import secrets
import unicodedata
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone, timedelta

from extensions import db
from models import (User, Member, Trainer, GymClass, ClassSession, Booking,
                    WaitlistEntry, Payment, PasswordResetToken, Notification)


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


def subscription_label(code):
    """Polska etykieta karnetu wg kodu (np. 'monthly' → 'Miesięczny')."""
    try:
        return SubscriptionFactory.create(code).label()
    except ValueError:
        return code


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

        # Powiadom awansowanego klienta (wcześniej awans był „cichy").
        member = db.session.get(Member, promoted_member_id)
        cs = db.session.get(ClassSession, session_id)
        if member and cs:
            NotificationService.push(
                member.user_id,
                f'Zwolniło się miejsce — masz potwierdzoną rezerwację na '
                f'{cs.gym_class.name} ({cs.session_date.strftime("%d.%m.%Y")}).',
                icon='check-circle', url='/client/bookings')

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

        member = db.session.get(Member, member_id)
        if member is None:
            return False, "Klient nie istnieje."
        if not MemberService.is_active(member, class_session.session_date):
            return False, ("Twój karnet nie obejmuje tej daty — "
                           "przedłuż karnet, aby się zapisać.")

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

    @staticmethod
    def past_attendance(member, today=None):
        """Potwierdzone rezerwacje na minione sesje (najnowsze pierwsze)."""
        today = today or date.today()
        return (Booking.query.filter_by(member_id=member.id, status='confirmed')
                .join(ClassSession)
                .filter(ClassSession.session_date <= today,
                        ClassSession.cancelled == False)
                .order_by(ClassSession.session_date.desc()).all())

    @staticmethod
    def attendance_summary(member, today=None):
        """Statystyki frekwencji klienta na minionych sesjach."""
        past = BookingService.past_attendance(member, today)
        attended = sum(1 for b in past if b.attended is True)
        absent = sum(1 for b in past if b.attended is False)
        marked = attended + absent
        return {
            'total': len(past),
            'attended': attended,
            'absent': absent,
            'unmarked': len(past) - marked,
            'pct': round(attended / marked * 100) if marked else None,
        }


# ── Service Layer: lista oczekujących ────────────────────────────────────────

class WaitlistService:
    @staticmethod
    def join(member_id, session_id):
        class_session = db.session.get(ClassSession, session_id)
        if class_session is None:
            return False, "Sesja nie istnieje."
        member = db.session.get(Member, member_id)
        if member is None or not MemberService.is_active(member, class_session.session_date):
            return False, ("Twój karnet nie obejmuje tej daty — "
                           "przedłuż karnet, aby dołączyć do kolejki.")
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
    """Płatności w modelu okresów rozliczeniowych.

    - miesięczny: okres = miesiąc kalendarzowy; pierwszy (niepełny) miesiąc
      liczony proporcjonalnie do dni pozostałych,
    - roczny: okres = pełny rok kotwiczony do miesiąca dołączenia
      (nie styczeń–grudzień), pełna cena,
    - dzienny: wejściówka ważna tylko w dniu zakupu.

    Opłacenie okresu przedłuża ważność karnetu do końca tego okresu
    (jeden mechanizm: płatności i „przedłużenie" to to samo).
    """

    @staticmethod
    def amount_for(member):
        """Pełna cena karnetu wg typu (bez proporcji)."""
        try:
            return SubscriptionFactory.create(member.subscription_type).price()
        except ValueError:
            return 0.0

    @staticmethod
    def generate_transfer_number():
        parts = [f"{random.randint(0, 9999):04d}" for _ in range(3)]
        return "TRF-" + "-".join(parts)

    # ── Okresy rozliczeniowe ──────────────────────────────────────────────────

    @staticmethod
    def _anchor_start(member):
        """Pierwszy dzień miesiąca dołączenia — kotwica okresów."""
        j = member.joined_at.date() if member.joined_at else date.today()
        return date(j.year, j.month, 1)

    @staticmethod
    def _period_for_index(member, index):
        """(start, end, key) okresu nr `index` (0 = okres startowy od kotwicy)."""
        anchor = PaymentService._anchor_start(member)
        if member.subscription_type == 'annual':
            start = date(anchor.year + index, anchor.month, 1)
            end = _add_months(start, 12) - timedelta(days=1)
        else:
            start = _add_months(anchor, index)
            end = _end_of_month(start)
        return start, end, f"{start.year:04d}-{start.month:02d}"

    @staticmethod
    def _current_index(member, today=None):
        """Indeks okresu zawierającego dziś (0 = startowy)."""
        today = today or date.today()
        anchor = PaymentService._anchor_start(member)
        months = (today.year - anchor.year) * 12 + (today.month - anchor.month)
        if months < 0:
            return 0
        return months // 12 if member.subscription_type == 'annual' else months

    @staticmethod
    def _index_for_key(member, key):
        y, m = int(key[:4]), int(key[5:7])
        anchor = PaymentService._anchor_start(member)
        months = (y - anchor.year) * 12 + (m - anchor.month)
        if member.subscription_type == 'annual':
            return months // 12 if months >= 0 else 0
        return max(months, 0)

    @staticmethod
    def _period_label(member, start, end):
        if member.subscription_type == 'annual':
            return f"{month_label(start)} – {month_label(end)}"
        return month_label(start)

    @staticmethod
    def _period_amount(member, index):
        """Kwota okresu: proporcja tylko dla pierwszego, niepełnego miesiąca
        karnetu miesięcznego; w pozostałych wypadkach pełna cena."""
        full = PaymentService.amount_for(member)
        if member.subscription_type == 'monthly' and index == 0:
            j = member.joined_at.date() if member.joined_at else None
            if j and j.day > 1:
                first = date(j.year, j.month, 1)
                days_in_month = (_end_of_month(j) - first).days + 1
                remaining = days_in_month - j.day + 1
                return round(full * remaining / days_in_month, 2)
        return full

    @staticmethod
    def _amount_for_key(member, key):
        return PaymentService._period_amount(member, PaymentService._index_for_key(member, key))

    @staticmethod
    def _period_end_for_key(member, key):
        if member.subscription_type == 'day_pass':
            return date.today()
        y, m = int(key[:4]), int(key[5:7])
        start = date(y, m, 1)
        if member.subscription_type == 'annual':
            return _add_months(start, 12) - timedelta(days=1)
        return _end_of_month(start)

    @staticmethod
    def payable_periods(member, count=3, today=None):
        """Najbliższe `count` okresów do opłacenia (bieżący + do przodu).

        Pusta lista dla karnetu dziennego (obsługiwany osobno — wejściówka).
        Nie pokazuje okresów sprzed dołączenia klienta.
        """
        if member.subscription_type == 'day_pass':
            return []
        cur = PaymentService._current_index(member, today)
        periods = []
        for i in range(cur, cur + count):
            start, end, key = PaymentService._period_for_index(member, i)
            payment = Payment.query.filter_by(member_id=member.id, month_year=key).first()
            periods.append({
                'index': i, 'start': start, 'end': end, 'key': key,
                'label': PaymentService._period_label(member, start, end),
                'amount': PaymentService._period_amount(member, i),
                'status': payment.status if payment else 'unpaid',
                'payment_id': payment.id if payment else None,
                'transfer_number': payment.transfer_number if payment else None,
                'paid_at': payment.paid_at if payment else None,
            })
        return periods

    @staticmethod
    def _extend_subscription(member, key):
        """Przedłuża ważność karnetu do końca opłaconego okresu."""
        end = PaymentService._period_end_for_key(member, key)
        if member.subscription_end is None or end > member.subscription_end:
            member.subscription_end = end

    @staticmethod
    def initiate(member_id, period_key):
        """Tworzy (lub zwraca istniejącą) płatność pending z numerem TRF."""
        member = db.session.get(Member, member_id)
        if member is None:
            return False, {"error": "Klient nie istnieje."}

        existing = Payment.query.filter_by(member_id=member_id, month_year=period_key).first()
        if existing and existing.status == 'completed':
            return False, {"error": "Ten okres jest już opłacony."}

        if existing:
            payment = existing
        else:
            payment = Payment(
                member_id=member_id,
                amount=PaymentService._amount_for_key(member, period_key),
                month_year=period_key,
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
        member = db.session.get(Member, payment.member_id)
        if member:
            PaymentService._extend_subscription(member, payment.month_year)
            NotificationService.push(
                member.user_id,
                f'Płatność {payment.amount:.0f} zł za {payment.month_year} '
                f'została potwierdzona.',
                icon='check-circle', url='/client/payments')
        db.session.commit()
        return True, "Płatność zatwierdzona."

    @staticmethod
    def settle_period(member, period_key, amount=None):
        """Bezpośrednio rozlicza okres (upsert completed) i przedłuża karnet.

        Używane przez „Przedłuż" — bez symulacji przelewu (od razu opłacone).
        """
        if amount is None:
            amount = PaymentService._amount_for_key(member, period_key)
        payment = Payment.query.filter_by(
            member_id=member.id, month_year=period_key).first()
        if payment is None:
            payment = Payment(member_id=member.id, month_year=period_key)
            db.session.add(payment)
        payment.amount = amount
        payment.status = 'completed'
        if not payment.transfer_number:
            payment.transfer_number = PaymentService.generate_transfer_number()
        payment.paid_at = datetime.now(timezone.utc)
        PaymentService._extend_subscription(member, period_key)
        NotificationService.push(
            member.user_id,
            f'Płatność {amount:.0f} zł za {period_key} została potwierdzona.',
            icon='check-circle', url='/client/payments')
        db.session.commit()
        return payment

    @staticmethod
    def settle_next_period(member):
        """Opłaca najbliższy okres przedłużający ważność (przycisk „Przedłuż").

        Wybiera pierwszy nieopłacony okres, którego koniec wykracza poza obecną
        ważność karnetu — dzięki temu „przedłuż" zawsze faktycznie przedłuża.
        """
        if member.subscription_type == 'day_pass':
            key = date.today().strftime('%Y-%m')
            p = PaymentService.settle_period(member, key, PaymentService.amount_for(member))
            return {'key': key, 'amount': p.amount, 'end': date.today()}

        coverage = member.subscription_end or (date.today() - timedelta(days=1))
        cur = PaymentService._current_index(member)
        for i in range(cur, cur + 24):
            start, end, key = PaymentService._period_for_index(member, i)
            payment = Payment.query.filter_by(member_id=member.id, month_year=key).first()
            if (payment is None or payment.status != 'completed') and end > coverage:
                amount = PaymentService._period_amount(member, i)
                PaymentService.settle_period(member, key, amount)
                return {'key': key, 'amount': amount, 'end': end}
        # awaryjnie: bieżący okres
        start, end, key = PaymentService._period_for_index(member, cur)
        amount = PaymentService._period_amount(member, cur)
        PaymentService.settle_period(member, key, amount)
        return {'key': key, 'amount': amount, 'end': end}

    @staticmethod
    def total_revenue():
        completed = Payment.query.filter_by(status='completed').all()
        return sum(p.amount for p in completed)


# ── Service Layer: powiadomienia ─────────────────────────────────────────────

class NotificationService:
    @staticmethod
    def push(user_id, message, icon='bell', url=None):
        """Dodaje powiadomienie do sesji DB (bez commitu — robi to wołający)."""
        if not user_id:
            return None
        note = Notification(user_id=user_id, message=message, icon=icon, url=url)
        db.session.add(note)
        return note

    @staticmethod
    def for_user(user_id, limit=20):
        return (Notification.query.filter_by(user_id=user_id)
                .order_by(Notification.created_at.desc()).limit(limit).all())

    @staticmethod
    def unread_count(user_id):
        return Notification.query.filter_by(user_id=user_id, read=False).count()

    @staticmethod
    def mark_all_read(user_id):
        Notification.query.filter_by(user_id=user_id, read=False).update({'read': True})
        db.session.commit()

    @staticmethod
    def notify_expiring(member, days_left):
        """Powiadomienie o wygasającym karnecie (≤7 dni), bez duplikatów.

        Nie tworzy kolejnego, jeśli istnieje już nieprzeczytane powiadomienie
        tego typu (klucz: ikona 'hourglass-split').
        """
        if days_left is None or days_left < 0 or days_left > 7:
            return None
        existing = Notification.query.filter_by(
            user_id=member.user_id, read=False, icon='hourglass-split').first()
        if existing:
            return None
        dni = 'dzień' if days_left == 1 else 'dni'
        note = NotificationService.push(
            member.user_id,
            f'Twój karnet wygasa za {days_left} {dni} — pamiętaj o przedłużeniu.',
            icon='hourglass-split', url='/client/')
        db.session.commit()
        return note


# ── Raport: wynagrodzenia trenerów ───────────────────────────────────────────

def trainer_payroll(today=None):
    """Koszt pracy trenerów = stawka × godziny przeprowadzonych sesji.

    Liczone są minione, nieodwołane sesje zatwierdzonych zajęć
    (godziny = liczba sesji × czas trwania zajęć).
    """
    today = today or date.today()
    rows = []
    for t in Trainer.query.all():
        hours = 0.0
        sessions_count = 0
        for c in t.classes:
            if c.status != 'approved':
                continue
            past = [s for s in c.sessions
                    if s.session_date <= today and not s.cancelled]
            sessions_count += len(past)
            hours += len(past) * (c.duration_minutes or 0) / 60
        rate = t.hourly_rate or 0
        rows.append({
            'trainer': t,
            'sessions': sessions_count,
            'hours': round(hours, 1),
            'rate': rate,
            'cost': round(hours * rate, 2),
        })
    rows.sort(key=lambda r: r['cost'], reverse=True)
    return rows


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
    def fresh_subscription_end(sub_type):
        """Data ważności nowego karnetu danego typu (od bieżącego okresu)."""
        return SubscriptionFactory.create(sub_type).extend(None)

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
    def register_client(first_name, last_name, password, phone='', sub_type='monthly'):
        """Self-signup klienta. Zwraca (ok, result).

        result = utworzony User (sukces) albo komunikat błędu (str).
        Login generowany automatycznie wg konwencji aplikacji; karnet aktywny
        na pierwszy okres (parytet z zakładaniem klienta przez admina).
        """
        first = (first_name or '').strip()
        last = (last_name or '').strip()
        if not first or not last:
            return False, "Imię i nazwisko są wymagane."
        if len(password or '') < 6:
            return False, "Hasło musi mieć co najmniej 6 znaków."
        try:
            strategy = SubscriptionFactory.create(sub_type)
        except ValueError:
            return False, "Nieprawidłowy typ karnetu."

        username = UserService.generate_client_username(first, last)
        user = User(username=username, role='client')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        member = Member(
            user_id=user.id, first_name=first, last_name=last,
            phone=(phone or '').strip(), subscription_type=sub_type,
            subscription_end=strategy.extend(None),
        )
        db.session.add(member)
        db.session.commit()
        return True, user

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

    @staticmethod
    def create_reset_token(username, ttl_minutes=60):
        """Tworzy jednorazowy token resetu hasła. Zwraca token albo None.

        Zwraca None tylko gdy użytkownik nie istnieje — wołający NIE powinien
        ujawniać tego użytkownikowi (ochrona przed enumeracją kont).
        """
        user = User.query.filter_by(username=username).first()
        if user is None:
            return None
        token = secrets.token_urlsafe(32)
        db.session.add(PasswordResetToken(
            user_id=user.id, token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        ))
        db.session.commit()
        return token

    @staticmethod
    def reset_password_with_token(token, new, confirm):
        """Ustawia nowe hasło na podstawie tokenu. Zwraca (ok, komunikat)."""
        prt = PasswordResetToken.query.filter_by(token=token, used=False).first()
        if prt is None:
            return False, "Link resetujący jest nieprawidłowy lub został już użyty."
        expires = prt.expires_at
        if expires.tzinfo is None:               # SQLite zwraca datę naiwną
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return False, "Link resetujący wygasł. Poproś o nowy."
        if len(new or '') < 6:
            return False, "Nowe hasło musi mieć co najmniej 6 znaków."
        if new != confirm:
            return False, "Hasła nie są identyczne."
        prt.user.set_password(new)
        prt.used = True
        db.session.commit()
        return True, "Hasło zostało zmienione. Możesz się zalogować."
