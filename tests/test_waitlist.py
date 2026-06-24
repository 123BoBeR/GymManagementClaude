"""Testy WaitlistService oraz wzorca Observer (awans z kolejki)."""
import pytest
from datetime import date, timedelta
from models import Booking, WaitlistEntry
from services import WaitlistService, BookingService
from tests.conftest import (
    make_user, make_member, make_trainer, make_class, make_session, make_booking
)


@pytest.fixture
def setup(db):
    tu = make_user(db, 'klient', 'pass', 'client')
    member = make_member(db, tu)
    tru = make_user(db, 'trener', 'pass', 'trainer')
    trainer = make_trainer(db, tru)
    gym_class = make_class(db, trainer, capacity=1)   # mała pojemność → łatwy waitlist
    sess = make_session(db, gym_class, delta_days=2)
    db.session.commit()
    return {'member': member, 'trainer': trainer, 'class': gym_class, 'session': sess}


class TestWaitlistService:
    def test_join_adds_entry(self, db, setup):
        ok, msg = WaitlistService.join(setup['member'].id, setup['session'].id)
        assert ok is True
        assert WaitlistEntry.query.count() == 1

    def test_join_twice_rejected(self, db, setup):
        WaitlistService.join(setup['member'].id, setup['session'].id)
        ok, msg = WaitlistService.join(setup['member'].id, setup['session'].id)
        assert ok is False
        assert WaitlistEntry.query.count() == 1

    def test_leave_removes_entry(self, db, setup):
        WaitlistService.join(setup['member'].id, setup['session'].id)
        ok, msg = WaitlistService.leave(setup['member'].id, setup['session'].id)
        assert ok is True
        assert WaitlistEntry.query.count() == 0

    def test_leave_when_not_on_list(self, db, setup):
        ok, msg = WaitlistService.leave(setup['member'].id, setup['session'].id)
        assert ok is False

    def test_position_reflects_order(self, db, setup):
        u2 = make_user(db, 'k2', 'pass', 'client')
        m2 = make_member(db, u2)
        db.session.commit()
        WaitlistService.join(setup['member'].id, setup['session'].id)
        WaitlistService.join(m2.id, setup['session'].id)
        assert WaitlistService.position(setup['member'].id, setup['session'].id) == 1
        assert WaitlistService.position(m2.id, setup['session'].id) == 2

    def test_position_none_when_absent(self, db, setup):
        assert WaitlistService.position(setup['member'].id, setup['session'].id) is None

    def test_join_inactive_subscription_rejected(self, db, setup):
        setup['member'].subscription_end = date.today() - timedelta(days=1)
        db.session.commit()
        ok, msg = WaitlistService.join(setup['member'].id, setup['session'].id)
        assert ok is False
        assert WaitlistEntry.query.count() == 0


class TestWaitlistObserver:
    def test_cancel_promotes_first_in_line(self, db, setup):
        # member zajmuje jedyne miejsce
        booking = make_booking(db, setup['member'], setup['session'])
        # drugi klient na liście oczekujących
        u2 = make_user(db, 'k2', 'pass', 'client')
        m2 = make_member(db, u2)
        db.session.commit()
        WaitlistService.join(m2.id, setup['session'].id)

        ok, msg = BookingService.cancel(setup['member'].id, booking.id)
        assert ok is True
        assert 'listy oczekujących' in msg
        # m2 dostał potwierdzoną rezerwację, kolejka pusta
        promoted = Booking.query.filter_by(member_id=m2.id, status='confirmed').first()
        assert promoted is not None
        assert WaitlistEntry.query.filter_by(session_id=setup['session'].id).count() == 0

    def test_cancel_without_waitlist(self, db, setup):
        booking = make_booking(db, setup['member'], setup['session'])
        ok, msg = BookingService.cancel(setup['member'].id, booking.id)
        assert ok is True
        assert 'listy oczekujących' not in msg
