"""Testy serwisu listy oczekujących (WaitlistService) i WaitlistObserver."""

from datetime import date
from models import db, User, Member, Booking, Waitlist
from services import BookingService, WaitlistService


class TestWaitlistService:

    def _fill_class(self, seeded):
        """Ustawia max_capacity=0 żeby zajęcia były pełne."""
        gc = seeded["gym_class"]
        gc.max_capacity = 0
        db.session.commit()
        return gc

    def _make_extra_member(self):
        """Tworzy i zwraca dodatkowego klienta."""
        u = User(username="klient_extra", role="client")
        u.set_password("x")
        db.session.add(u)
        db.session.flush()
        m = Member(user_id=u.id, first_name="Anna", last_name="X",
                   subscription_type="monthly", subscription_end=date(2027, 1, 1))
        db.session.add(m)
        db.session.commit()
        return m

    def test_join_adds_entry(self, seeded):
        gc = self._fill_class(seeded)
        member = seeded["member"]
        ok, msg = WaitlistService.join(member.id, gc.id)
        assert ok is True
        assert Waitlist.query.filter_by(member_id=member.id, class_id=gc.id).first() is not None

    def test_join_message_includes_position(self, seeded):
        gc = self._fill_class(seeded)
        ok, msg = WaitlistService.join(seeded["member"].id, gc.id)
        assert ok is True
        assert "1" in msg

    def test_join_rejects_duplicate(self, seeded):
        gc = self._fill_class(seeded)
        member = seeded["member"]
        WaitlistService.join(member.id, gc.id)
        ok, msg = WaitlistService.join(member.id, gc.id)
        assert ok is False
        assert "już" in msg

    def test_join_rejects_when_already_confirmed_booking(self, seeded):
        member = seeded["member"]
        gc = seeded["gym_class"]
        BookingService.book(member.id, gc.id)
        gc.max_capacity = 0
        db.session.commit()
        ok, msg = WaitlistService.join(member.id, gc.id)
        assert ok is False

    def test_join_rejects_nonexistent_class(self, seeded):
        ok, msg = WaitlistService.join(seeded["member"].id, 9999)
        assert ok is False

    def test_leave_removes_entry(self, seeded):
        gc = self._fill_class(seeded)
        member = seeded["member"]
        WaitlistService.join(member.id, gc.id)
        ok, msg = WaitlistService.leave(member.id, gc.id)
        assert ok is True
        assert Waitlist.query.filter_by(member_id=member.id, class_id=gc.id).first() is None

    def test_leave_rejects_when_not_on_list(self, seeded):
        ok, msg = WaitlistService.leave(seeded["member"].id, seeded["gym_class"].id)
        assert ok is False

    def test_position_returns_correct_rank(self, seeded):
        gc = self._fill_class(seeded)
        m1 = seeded["member"]
        m2 = self._make_extra_member()
        WaitlistService.join(m1.id, gc.id)
        WaitlistService.join(m2.id, gc.id)
        assert WaitlistService.position(m1.id, gc.id) == 1
        assert WaitlistService.position(m2.id, gc.id) == 2

    def test_position_returns_none_when_not_on_list(self, seeded):
        gc = seeded["gym_class"]
        member = seeded["member"]
        assert WaitlistService.position(member.id, gc.id) is None


class TestWaitlistObserver:

    def test_observer_assigns_spot_when_booking_cancelled(self, seeded):
        member = seeded["member"]
        gc = seeded["gym_class"]

        # Zapełnij klasę rezerwacją klienta 1
        gc.max_capacity = 1
        db.session.commit()
        BookingService.book(member.id, gc.id)

        # Klient 2 dołącza do kolejki
        u2 = User(username="klient2", role="client")
        u2.set_password("x")
        db.session.add(u2)
        db.session.flush()
        m2 = Member(user_id=u2.id, first_name="Anna", last_name="X",
                    subscription_type="monthly", subscription_end=date(2027, 1, 1))
        db.session.add(m2)
        db.session.flush()
        db.session.add(Waitlist(member_id=m2.id, class_id=gc.id))
        db.session.commit()

        # Klient 1 anuluje → Observer automatycznie przydziela miejsce klientowi 2
        booking = Booking.query.filter_by(member_id=member.id, class_id=gc.id).first()
        BookingService.cancel(booking.id, member.id)

        new_booking = Booking.query.filter_by(
            member_id=m2.id, class_id=gc.id, status="confirmed"
        ).first()
        assert new_booking is not None

    def test_observer_removes_waitlist_entry_after_assigning(self, seeded):
        member = seeded["member"]
        gc = seeded["gym_class"]
        gc.max_capacity = 1
        db.session.commit()
        BookingService.book(member.id, gc.id)

        u2 = User(username="klient2", role="client")
        u2.set_password("x")
        db.session.add(u2)
        db.session.flush()
        m2 = Member(user_id=u2.id, first_name="Anna", last_name="X",
                    subscription_type="monthly", subscription_end=date(2027, 1, 1))
        db.session.add(m2)
        db.session.flush()
        db.session.add(Waitlist(member_id=m2.id, class_id=gc.id))
        db.session.commit()

        booking = Booking.query.filter_by(member_id=member.id, class_id=gc.id).first()
        BookingService.cancel(booking.id, member.id)

        assert Waitlist.query.filter_by(member_id=m2.id, class_id=gc.id).first() is None

    def test_observer_does_nothing_when_waitlist_empty(self, seeded):
        member = seeded["member"]
        gc = seeded["gym_class"]
        BookingService.book(member.id, gc.id)
        booking = Booking.query.filter_by(member_id=member.id, class_id=gc.id).first()
        ok, _ = BookingService.cancel(booking.id, member.id)
        assert ok is True
        assert Waitlist.query.filter_by(class_id=gc.id).count() == 0

    def test_observer_assigns_first_in_queue_not_second(self, seeded):
        member = seeded["member"]
        gc = seeded["gym_class"]
        gc.max_capacity = 1
        db.session.commit()
        BookingService.book(member.id, gc.id)

        # Dwóch w kolejce
        members_extra = []
        for i, name in enumerate(["klient2", "klient3"]):
            u = User(username=name, role="client")
            u.set_password("x")
            db.session.add(u)
            db.session.flush()
            m = Member(user_id=u.id, first_name=f"Anna{i}", last_name="X",
                       subscription_type="monthly", subscription_end=date(2027, 1, 1))
            db.session.add(m)
            db.session.flush()
            db.session.add(Waitlist(member_id=m.id, class_id=gc.id))
            members_extra.append(m)
        db.session.commit()

        booking = Booking.query.filter_by(member_id=member.id, class_id=gc.id).first()
        BookingService.cancel(booking.id, member.id)

        # Tylko pierwszy z kolejki dostaje miejsce
        first, second = members_extra
        assert Booking.query.filter_by(
            member_id=first.id, class_id=gc.id, status="confirmed"
        ).first() is not None
        assert Booking.query.filter_by(
            member_id=second.id, class_id=gc.id, status="confirmed"
        ).first() is None
        # Drugi nadal w kolejce
        assert Waitlist.query.filter_by(member_id=second.id, class_id=gc.id).first() is not None
