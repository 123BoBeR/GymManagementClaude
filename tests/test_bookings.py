"""Testy logiki rezerwacji."""
import pytest
from datetime import date, timedelta
from models import Booking, WaitlistEntry
from tests.conftest import (
    make_user, make_member, make_trainer, make_class, make_session, make_booking
)


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


def book(client, session_id):
    return client.post(f'/client/sessions/{session_id}/book', follow_redirects=True)


def cancel(client, booking_id):
    return client.post(f'/client/bookings/{booking_id}/cancel', follow_redirects=True)


def join_waitlist(client, session_id):
    return client.post(f'/client/sessions/{session_id}/waitlist', follow_redirects=True)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def setup(db):
    tu = make_user(db, 'klient', 'pass', 'client')
    member = make_member(db, tu)
    tru = make_user(db, 'trener', 'pass', 'trainer')
    trainer = make_trainer(db, tru)
    gym_class = make_class(db, trainer)
    sess = make_session(db, gym_class, delta_days=2)
    db.session.commit()
    return {'member': member, 'trainer': trainer, 'class': gym_class, 'session': sess}


class TestBooking:
    def test_successful_booking(self, client, db, setup):
        login(client, 'klient', 'pass')
        resp = book(client, setup['session'].id)
        assert 'Zapisano na' in resp.data.decode()
        assert Booking.query.filter_by(session_id=setup['session'].id, status='confirmed').count() == 1

    def test_cannot_book_twice(self, client, db, setup):
        login(client, 'klient', 'pass')
        book(client, setup['session'].id)
        resp = book(client, setup['session'].id)
        assert 'już zapisany' in resp.data.decode()
        assert Booking.query.filter_by(session_id=setup['session'].id, status='confirmed').count() == 1

    def test_cannot_book_full_session(self, client, db):
        tu = make_user(db, 'k_full', 'pass', 'client')
        member = make_member(db, tu)
        tru = make_user(db, 't_full', 'pass', 'trainer')
        trainer = make_trainer(db, tru)
        c = make_class(db, trainer, capacity=2)
        s = make_session(db, c, delta_days=3)

        # Wypełnij do limitu innymi klientami
        for i in range(2):
            ou = make_user(db, f'other_full_{i}', 'p', 'client')
            om = make_member(db, ou)
            make_booking(db, om, s)
        db.session.commit()

        login(client, 'k_full', 'pass')
        resp = book(client, s.id)
        assert 'Brak wolnych miejsc' in resp.data.decode()

    def test_cancel_booking(self, client, db, setup):
        login(client, 'klient', 'pass')
        book(client, setup['session'].id)
        b = Booking.query.filter_by(member_id=setup['member'].id, status='confirmed').first()
        resp = cancel(client, b.id)
        assert 'anulowana' in resp.data.decode()
        assert db.session.get(Booking, b.id).status == 'cancelled'

    def test_cannot_cancel_other_members_booking(self, client, db, setup):
        # Utwórz drugiego klienta i zarezerwuj dla niego
        ou = make_user(db, 'inny', 'pass', 'client')
        om = make_member(db, ou)
        b = make_booking(db, om, setup['session'])
        db.session.commit()

        login(client, 'klient', 'pass')
        resp = cancel(client, b.id)
        assert 'Brak dostępu' in resp.data.decode()
        assert db.session.get(Booking, b.id).status == 'confirmed'

    def test_conflict_same_day_same_time(self, client, db):
        tu = make_user(db, 'k_conflict', 'pass', 'client')
        member = make_member(db, tu)
        tru = make_user(db, 't_conflict', 'pass', 'trainer')
        trainer = make_trainer(db, tru)

        c1 = make_class(db, trainer, day='Poniedziałek', time='10:00', duration=60)
        c2 = make_class(db, trainer, day='Poniedziałek', time='10:30', duration=60)

        tomorrow = date.today() + timedelta(days=1)
        from models import ClassSession
        s1 = ClassSession(class_id=c1.id, session_date=tomorrow)
        s2 = ClassSession(class_id=c2.id, session_date=tomorrow)
        from extensions import db as _db
        _db.session.add_all([s1, s2])
        _db.session.flush()
        db.session.commit()

        login(client, 'k_conflict', 'pass')
        book(client, s1.id)
        resp = book(client, s2.id)
        assert 'Konflikt terminów' in resp.data.decode()

    def test_bookings_paginated(self, client, db, setup):
        member, gym_class = setup['member'], setup['class']
        for i in range(18):
            make_booking(db, member, make_session(db, gym_class, delta_days=i + 1))
        db.session.commit()
        login(client, 'klient', 'pass')
        page1 = client.get('/client/bookings?status=all').data.decode()
        page2 = client.get('/client/bookings?status=all&page=2').data.decode()
        assert page1.count('Anuluj') == 15                   # per_page=15
        assert page2.count('Anuluj') == 3


class TestWaitlist:
    def test_join_waitlist_when_full(self, client, db):
        tu = make_user(db, 'k_wl', 'pass', 'client')
        member = make_member(db, tu)
        tru = make_user(db, 't_wl', 'pass', 'trainer')
        trainer = make_trainer(db, tru)
        c = make_class(db, trainer, capacity=1)
        s = make_session(db, c, delta_days=4)

        ou = make_user(db, 'other_wl', 'p', 'client')
        om = make_member(db, ou)
        make_booking(db, om, s)
        db.session.commit()

        login(client, 'k_wl', 'pass')
        resp = join_waitlist(client, s.id)
        assert 'listę oczekujących' in resp.data.decode()
        assert WaitlistEntry.query.filter_by(session_id=s.id).count() == 1

    def test_cancel_promotes_waitlist(self, client, db):
        tu = make_user(db, 'k_holder', 'pass', 'client')
        holder = make_member(db, tu)
        wu = make_user(db, 'k_waiter', 'pass', 'client')
        waiter = make_member(db, wu)
        tru = make_user(db, 't_wl2', 'pass', 'trainer')
        trainer = make_trainer(db, tru)
        c = make_class(db, trainer, capacity=1)
        s = make_session(db, c, delta_days=5)

        b = make_booking(db, holder, s)
        wl = WaitlistEntry(member_id=waiter.id, session_id=s.id)
        from extensions import db as _db
        _db.session.add(wl)
        db.session.commit()

        login(client, 'k_holder', 'pass')
        cancel(client, b.id)

        # Waiter powinien teraz mieć rezerwację
        assert Booking.query.filter_by(member_id=waiter.id, session_id=s.id,
                                       status='confirmed').count() == 1
        assert WaitlistEntry.query.filter_by(session_id=s.id).count() == 0
