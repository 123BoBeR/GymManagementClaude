"""Testy warstwy serwisowej: BookingService, MemberService, UserService."""
import pytest
from datetime import date, timedelta
from models import Booking
from services import BookingService, MemberService, UserService
from tests.conftest import (
    make_user, make_member, make_trainer, make_class, make_session, make_booking
)


@pytest.fixture
def setup(db):
    tu = make_user(db, 'klient', 'pass', 'client')
    member = make_member(db, tu)
    tru = make_user(db, 'trener', 'pass', 'trainer')
    trainer = make_trainer(db, tru)
    gym_class = make_class(db, trainer, capacity=2)
    sess = make_session(db, gym_class, delta_days=2)
    db.session.commit()
    return {'member': member, 'trainer': trainer, 'class': gym_class, 'session': sess, 'user': tu}


class TestBookingService:
    def test_book_success(self, db, setup):
        ok, msg = BookingService.book(setup['member'].id, setup['session'].id)
        assert ok is True
        assert Booking.query.filter_by(status='confirmed').count() == 1

    def test_book_duplicate_rejected(self, db, setup):
        BookingService.book(setup['member'].id, setup['session'].id)
        ok, msg = BookingService.book(setup['member'].id, setup['session'].id)
        assert ok is False
        assert 'już zapisany' in msg

    def test_book_full_session_rejected(self, db, setup):
        gym_class = make_class(db, setup['trainer'], capacity=1, time='12:00')
        sess = make_session(db, gym_class, delta_days=3)
        db.session.commit()
        u2 = make_user(db, 'k2', 'pass', 'client'); m2 = make_member(db, u2); db.session.commit()
        BookingService.book(setup['member'].id, sess.id)
        ok, msg = BookingService.book(m2.id, sess.id)
        assert ok is False
        assert 'Brak wolnych miejsc' in msg

    def test_book_past_session_rejected(self, db, setup):
        past = make_session(db, setup['class'], delta_days=-3)
        db.session.commit()
        ok, msg = BookingService.book(setup['member'].id, past.id)
        assert ok is False
        assert 'przeszł' in msg.lower()

    def test_book_time_conflict_rejected(self, db, setup):
        # te same zajęcia (ten sam dzień+godzina), inna sesja tej samej daty
        BookingService.book(setup['member'].id, setup['session'].id)
        same_time_class = make_class(db, setup['trainer'], day='Poniedziałek',
                                     time='10:00', capacity=5)
        # ta sama data sesji co setup['session']
        conflicting = make_session(db, same_time_class, delta_days=2)
        db.session.commit()
        ok, msg = BookingService.book(setup['member'].id, conflicting.id)
        assert ok is False
        assert 'Konflikt' in msg

    def test_cancel_success(self, db, setup):
        b = make_booking(db, setup['member'], setup['session']); db.session.commit()
        ok, msg = BookingService.cancel(setup['member'].id, b.id)
        assert ok is True
        assert db.session.get(Booking, b.id).status == 'cancelled'

    def test_cancel_wrong_member_rejected(self, db, setup):
        b = make_booking(db, setup['member'], setup['session']); db.session.commit()
        ok, msg = BookingService.cancel(setup['member'].id + 999, b.id)
        assert ok is False
        assert db.session.get(Booking, b.id).status == 'confirmed'


class TestMemberService:
    def test_update_profile(self, db, setup):
        ok, msg = MemberService.update_profile(setup['member'], first_name='Nowy',
                                               last_name='Klient', phone='123')
        assert ok is True
        assert setup['member'].first_name == 'Nowy'
        assert setup['member'].phone == '123'

    def test_renew_subscription_stacks_by_month(self, db, setup):
        # aktywny do końca lipca → po odnowieniu miesięcznym do końca sierpnia
        setup['member'].subscription_end = date(2026, 7, 31)
        new_end = MemberService.renew_subscription(setup['member'], 'monthly',
                                                   today=date(2026, 7, 10))
        assert new_end == date(2026, 8, 31)
        assert setup['member'].subscription_type == 'monthly'

    def test_renew_subscription_expired_resets_to_month(self, db, setup):
        setup['member'].subscription_end = date(2026, 1, 31)
        new_end = MemberService.renew_subscription(setup['member'], 'monthly',
                                                   today=date(2026, 6, 24))
        assert new_end == date(2026, 6, 30)

    def test_is_active_true_for_future_end(self, db, setup):
        setup['member'].subscription_end = date.today() + timedelta(days=5)
        assert MemberService.is_active(setup['member']) is True

    def test_is_active_false_for_past_end(self, db, setup):
        setup['member'].subscription_end = date.today() - timedelta(days=1)
        assert MemberService.is_active(setup['member']) is False

    def test_days_left(self, db, setup):
        setup['member'].subscription_end = date.today() + timedelta(days=10)
        assert MemberService.days_left(setup['member']) == 10


class TestUserService:
    def test_change_password_success(self, db, setup):
        ok, msg = UserService.change_password(setup['user'], 'pass', 'newpass', 'newpass')
        assert ok is True
        assert setup['user'].check_password('newpass')

    def test_change_password_wrong_current(self, db, setup):
        ok, msg = UserService.change_password(setup['user'], 'zle', 'newpass', 'newpass')
        assert ok is False
        assert 'nieprawidłowe' in msg.lower()

    def test_change_password_too_short(self, db, setup):
        ok, msg = UserService.change_password(setup['user'], 'pass', '123', '123')
        assert ok is False

    def test_change_password_mismatch(self, db, setup):
        ok, msg = UserService.change_password(setup['user'], 'pass', 'newpass', 'inne')
        assert ok is False
