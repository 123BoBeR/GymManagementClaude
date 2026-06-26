"""Testy tras trenera: propozycja/edycja zajęć, obecność, uczestnicy, profil (B48)."""
import pytest
from datetime import date, timedelta
from models import GymClass, Booking
from tests.conftest import (
    make_user, make_member, make_trainer, make_class, make_session, make_booking
)


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


@pytest.fixture
def trainer_ctx(client, db):
    """Zalogowany trener z jednym zatwierdzonym kursem."""
    u = make_user(db, 'trener', 'pass123', 'trainer')
    t = make_trainer(db, u)
    db.session.commit()
    login(client, 'trener', 'pass123')
    return {'user': u, 'trainer': t}


class TestProposeClass:
    def test_propose_creates_pending_class(self, client, db, trainer_ctx):
        resp = client.post('/trainer/classes/propose', data={
            'name': 'Nowy Trening', 'description': 'Opis',
            'max_capacity': '12', 'schedule_day': 'Wtorek', 'schedule_time': '18:00',
            'duration_minutes': '60', 'frequency_weeks': '1',
            'start_date': (date.today() + timedelta(days=7)).strftime('%Y-%m-%d'),
        }, follow_redirects=True)
        assert 'wysłana' in resp.data.decode()
        c = GymClass.query.filter_by(name='Nowy Trening').first()
        assert c is not None
        assert c.status == 'pending'
        assert c.trainer_id == trainer_ctx['trainer'].id

    def test_propose_invalid_date_rejected(self, client, db, trainer_ctx):
        resp = client.post('/trainer/classes/propose', data={
            'name': 'Zła Data', 'schedule_day': 'Wtorek', 'schedule_time': '18:00',
            'start_date': 'nie-data',
        }, follow_redirects=True)
        assert 'Nieprawidłowa data' in resp.data.decode()
        assert GymClass.query.filter_by(name='Zła Data').first() is None


class TestEditClass:
    def test_edit_pending_class(self, client, db, trainer_ctx):
        c = make_class(db, trainer_ctx['trainer'], status='pending')
        db.session.commit()
        cid = c.id
        client.post(f'/trainer/classes/{cid}/edit', data={
            'name': 'Zmieniona Nazwa', 'description': 'x', 'max_capacity': '10',
            'schedule_day': 'Środa', 'schedule_time': '12:00',
            'duration_minutes': '45', 'frequency_weeks': '1',
            'start_date': date.today().strftime('%Y-%m-%d'),
        }, follow_redirects=True)
        assert db.session.get(GymClass, cid).name == 'Zmieniona Nazwa'

    def test_edit_approved_class_blocked(self, client, db, trainer_ctx):
        c = make_class(db, trainer_ctx['trainer'], status='approved')
        db.session.commit()
        cid = c.id
        resp = client.post(f'/trainer/classes/{cid}/edit', data={
            'name': 'Nie Powinno Przejść',
        }, follow_redirects=True)
        assert 'Nie można edytować zatwierdzonych' in resp.data.decode()
        assert db.session.get(GymClass, cid).name == 'Test Yoga'

    def test_edit_rejected_resubmits_as_pending(self, client, db, trainer_ctx):
        c = make_class(db, trainer_ctx['trainer'], status='rejected')
        c.rejection_note = 'Zła godzina'
        db.session.commit()
        cid = c.id
        client.post(f'/trainer/classes/{cid}/edit', data={
            'name': 'Poprawione', 'description': 'x', 'max_capacity': '10',
            'schedule_day': 'Środa', 'schedule_time': '19:00',
            'duration_minutes': '60', 'frequency_weeks': '1',
            'start_date': date.today().strftime('%Y-%m-%d'),
        }, follow_redirects=True)
        updated = db.session.get(GymClass, cid)
        assert updated.status == 'pending'
        assert updated.rejection_note is None

    def test_edit_other_trainers_class_blocked(self, client, db, trainer_ctx):
        ou = make_user(db, 'obcy', 'pass123', 'trainer')
        other = make_trainer(db, ou)
        c = make_class(db, other, status='pending')
        db.session.commit()
        cid = c.id
        resp = client.post(f'/trainer/classes/{cid}/edit', data={
            'name': 'Kradziez',
        }, follow_redirects=True)
        assert 'Brak dostępu' in resp.data.decode()
        assert db.session.get(GymClass, cid).name == 'Test Yoga'


class TestAttendance:
    def test_mark_attendance_past_session(self, client, db, trainer_ctx):
        c = make_class(db, trainer_ctx['trainer'], status='approved')
        s = make_session(db, c, delta_days=-1)          # wczoraj
        cu = make_user(db, 'klient', 'pass123', 'client')
        cm = make_member(db, cu)
        b = make_booking(db, cm, s)
        db.session.commit()
        bid = b.id
        client.post(f'/trainer/sessions/{s.id}/attendance', data={
            f'attended_{bid}': '1',
        }, follow_redirects=True)
        assert db.session.get(Booking, bid).attended is True

    def test_cannot_mark_future_session(self, client, db, trainer_ctx):
        c = make_class(db, trainer_ctx['trainer'], status='approved')
        s = make_session(db, c, delta_days=3)           # przyszłość
        cu = make_user(db, 'klient2', 'pass123', 'client')
        cm = make_member(db, cu)
        b = make_booking(db, cm, s)
        db.session.commit()
        bid = b.id
        resp = client.post(f'/trainer/sessions/{s.id}/attendance', data={
            f'attended_{bid}': '1',
        }, follow_redirects=True)
        assert 'przyszłych sesji' in resp.data.decode()
        assert db.session.get(Booking, bid).attended is None

    def test_cannot_mark_other_trainers_session(self, client, db, trainer_ctx):
        ou = make_user(db, 'obcy2', 'pass123', 'trainer')
        other = make_trainer(db, ou)
        c = make_class(db, other, status='approved')
        s = make_session(db, c, delta_days=-1)
        db.session.commit()
        resp = client.post(f'/trainer/sessions/{s.id}/attendance',
                           data={}, follow_redirects=True)
        assert 'Brak dostępu' in resp.data.decode()


class TestClassMembers:
    def test_own_class_members_ok(self, client, db, trainer_ctx):
        c = make_class(db, trainer_ctx['trainer'], status='approved')
        db.session.commit()
        resp = client.get(f'/trainer/classes/{c.id}/members')
        assert resp.status_code == 200

    def test_other_trainers_class_members_blocked(self, client, db, trainer_ctx):
        ou = make_user(db, 'obcy3', 'pass123', 'trainer')
        other = make_trainer(db, ou)
        c = make_class(db, other, status='approved')
        db.session.commit()
        resp = client.get(f'/trainer/classes/{c.id}/members', follow_redirects=True)
        assert 'Brak dostępu' in resp.data.decode()


class TestTrainerProfile:
    def test_update_profile(self, client, db, trainer_ctx):
        client.post('/trainer/profile', data={
            'specialization': 'Kettlebell', 'hourly_rate': '175,50',
        }, follow_redirects=True)
        t = trainer_ctx['trainer']
        db.session.refresh(t)
        assert t.specialization == 'Kettlebell'
        assert t.hourly_rate == 175.5

    def test_invalid_rate_rejected(self, client, db, trainer_ctx):
        resp = client.post('/trainer/profile', data={
            'specialization': 'Boks', 'hourly_rate': 'abc',
        }, follow_redirects=True)
        assert 'Nieprawidłowa stawka' in resp.data.decode()
