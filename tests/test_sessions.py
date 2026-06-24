"""Testy odwoływania sesji (B30) i generowania sesji (B31)."""
import pytest
from datetime import date, timedelta
from models import ClassSession, Booking
from services import BookingService
from tests.conftest import (
    make_user, make_member, make_trainer, make_class, make_session
)


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


@pytest.fixture
def setup(db):
    tu = make_user(db, 'trener', 'pass', 'trainer')
    trainer = make_trainer(db, tu)
    gym_class = make_class(db, trainer)
    sess = make_session(db, gym_class, delta_days=3)
    db.session.commit()
    return {'trainer': trainer, 'class': gym_class, 'session': sess, 'user': tu}


class TestSessionCancel:
    def test_trainer_cancels_own_session(self, client, db, setup):
        login(client, 'trener', 'pass')
        resp = client.post(f"/trainer/sessions/{setup['session'].id}/cancel",
                           follow_redirects=True)
        assert 'odwołana' in resp.data.decode().lower()
        assert db.session.get(ClassSession, setup['session'].id).cancelled is True

    def test_cannot_cancel_past_session(self, client, db, setup):
        past = make_session(db, setup['class'], delta_days=-2)
        db.session.commit()
        login(client, 'trener', 'pass')
        client.post(f"/trainer/sessions/{past.id}/cancel", follow_redirects=True)
        assert db.session.get(ClassSession, past.id).cancelled is False

    def test_cannot_cancel_other_trainers_session(self, client, db, setup):
        ou = make_user(db, 'trener2', 'pass', 'trainer')
        other = make_trainer(db, ou)
        oc = make_class(db, other)
        osess = make_session(db, oc, delta_days=4)
        db.session.commit()
        login(client, 'trener', 'pass')   # zalogowany jako pierwszy trener
        client.post(f"/trainer/sessions/{osess.id}/cancel", follow_redirects=True)
        assert db.session.get(ClassSession, osess.id).cancelled is False

    def test_cancelled_session_not_bookable(self, client, db, setup):
        cu = make_user(db, 'klient', 'pass', 'client')
        cm = make_member(db, cu)
        setup['session'].cancelled = True
        db.session.commit()
        ok, msg = BookingService.book(cm.id, setup['session'].id)
        assert ok is False
        assert 'odwołana' in msg.lower()


class TestSessionGeneration:
    def test_ensure_future_sessions_fills_and_is_idempotent(self, db):
        from blueprints.sessions import ensure_future_sessions
        tu = make_user(db, 'trener.gen', 'pass', 'trainer')
        t = make_trainer(db, tu)
        c = make_class(db, t)   # start_date=dziś, approved, co tydzień
        db.session.commit()

        added = ensure_future_sessions(c, horizon_weeks=4)
        db.session.commit()
        assert added > 0
        count = ClassSession.query.filter_by(class_id=c.id).count()
        assert count == added

        # ponowne wywołanie nic nie dodaje (idempotencja)
        again = ensure_future_sessions(c, horizon_weeks=4)
        db.session.commit()
        assert again == 0
        assert ClassSession.query.filter_by(class_id=c.id).count() == count

    def test_ensure_skips_cancelled_dates(self, db):
        from blueprints.sessions import ensure_future_sessions, _first_occurrence
        tu = make_user(db, 'trener.gen2', 'pass', 'trainer')
        t = make_trainer(db, tu)
        c = make_class(db, t)
        first = _first_occurrence(c)
        db.session.add(ClassSession(class_id=c.id, session_date=first, cancelled=True))
        db.session.commit()

        ensure_future_sessions(c, horizon_weeks=4)
        db.session.commit()
        # odwołana data nie została odtworzona — dokładnie jedna sesja w tej dacie
        assert ClassSession.query.filter_by(class_id=c.id, session_date=first).count() == 1

    def test_ensure_ignores_non_approved(self, db):
        from blueprints.sessions import ensure_future_sessions
        tu = make_user(db, 'trener.gen3', 'pass', 'trainer')
        t = make_trainer(db, tu)
        c = make_class(db, t, status='pending')
        db.session.commit()
        assert ensure_future_sessions(c) == 0
