"""Testy IDOR / autoryzacji poziomej: klient A nie sięgnie do danych klienta B (B48)."""
import pytest
from datetime import date, timedelta
from models import Payment, Booking
from tests.conftest import (
    make_user, make_member, make_trainer, make_class, make_session, make_booking
)


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


@pytest.fixture
def two_clients(client, db):
    """Dwóch klientów A i B; zalogowany jest A."""
    ua = make_user(db, 'klient.a', 'pass123', 'client')
    ma = make_member(db, ua)
    ub = make_user(db, 'klient.b', 'pass123', 'client')
    mb = make_member(db, ub)
    db.session.commit()
    login(client, 'klient.a', 'pass123')
    return {'a': ma, 'b': mb}


class TestPaymentIdor:
    def test_cannot_open_other_members_payment(self, client, db, two_clients):
        p = Payment(member_id=two_clients['b'].id, amount=99.0, month_year='2026-07',
                    status='pending', transfer_number='TRF-1111-2222-3333')
        db.session.add(p)
        db.session.commit()
        pid = p.id
        resp = client.get(f'/client/payments/{pid}/pay', follow_redirects=True)
        assert 'Brak dostępu' in resp.data.decode()
        assert db.session.get(Payment, pid).status == 'pending'

    def test_cannot_confirm_other_members_payment(self, client, db, two_clients):
        p = Payment(member_id=two_clients['b'].id, amount=99.0, month_year='2026-08',
                    status='pending', transfer_number='TRF-4444-5555-6666')
        db.session.add(p)
        db.session.commit()
        pid = p.id
        resp = client.post(f'/client/payments/{pid}/confirm', follow_redirects=True)
        assert 'Brak dostępu' in resp.data.decode()
        # płatność klienta B nadal nieopłacona
        assert db.session.get(Payment, pid).status == 'pending'


class TestBookingIdor:
    def test_cannot_cancel_other_members_booking(self, client, db, two_clients):
        tu = make_user(db, 'trener.x', 'pass123', 'trainer')
        t = make_trainer(db, tu)
        c = make_class(db, t, status='approved')
        s = make_session(db, c, delta_days=3)
        b = make_booking(db, two_clients['b'], s)        # rezerwacja klienta B
        db.session.commit()
        bid = b.id
        resp = client.post(f'/client/bookings/{bid}/cancel', follow_redirects=True)
        assert 'Brak dostępu' in resp.data.decode()
        # rezerwacja klienta B nadal potwierdzona
        assert db.session.get(Booking, bid).status == 'confirmed'
