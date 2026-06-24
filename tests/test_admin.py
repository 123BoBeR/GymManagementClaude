"""Testy operacji administracyjnych: CRUD trenerów/klientów, eksport płatności."""
import pytest
from datetime import date, timedelta
from models import User, Trainer, Member, Payment
from services import UserService, SubscriptionFactory
from tests.conftest import make_user, make_member, make_trainer, make_class


def login_admin(client, db):
    u = make_user(db, 'admin', 'admin123', 'admin')
    db.session.commit()
    client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    return u


class TestTrainerCrud:
    def test_create_trainer_autogenerates_username(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/trainers/new', data={
            'first_name': 'Jan', 'last_name': 'Nowak',
            'password': 'trener123', 'specialization': 'Boks', 'hourly_rate': '150',
        }, follow_redirects=True)
        assert 'dodany' in resp.data.decode()
        t = User.query.filter_by(username='t.jan.nowak').first()
        assert t is not None and t.role == 'trainer'
        assert t.trainer.specialization == 'Boks'

    def test_create_rejects_short_password(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/trainers/new', data={
            'first_name': 'Anna', 'last_name': 'Krotka', 'password': '123',
        }, follow_redirects=True)
        assert '6 znaków' in resp.data.decode()
        assert User.query.filter_by(username='t.anna.krotka').first() is None

    def test_delete_trainer_without_classes(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'dousuniecia', 'pass123', 'trainer')
        t = make_trainer(db, u)
        db.session.commit()
        tid = t.id
        resp = client.post(f'/admin/trainers/{tid}/delete', follow_redirects=True)
        assert 'usunięty' in resp.data.decode()
        assert db.session.get(Trainer, tid) is None
        assert User.query.filter_by(username='dousuniecia').first() is None

    def test_delete_trainer_with_classes_blocked(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'zajety2', 'pass123', 'trainer')
        t = make_trainer(db, u)
        make_class(db, t, status='approved')
        db.session.commit()
        tid = t.id
        resp = client.post(f'/admin/trainers/{tid}/delete', follow_redirects=True)
        assert 'Nie można usunąć' in resp.data.decode()
        assert db.session.get(Trainer, tid) is not None


class TestUsernameGeneration:
    def test_client_username_basic(self, db):
        assert UserService.generate_client_username('Jan', 'Kowalski') == 'j.kowalski'

    def test_client_username_strips_polish_chars(self, db):
        assert UserService.generate_client_username('Łukasz', 'Wójcik') == 'l.wojcik'

    def test_client_username_collision_takes_more_letters(self, db):
        u = make_user(db, 'j.kowalski', 'pass123', 'client')
        make_member(db, u)
        db.session.commit()
        assert UserService.generate_client_username('Jan', 'Kowalski') == 'ja.kowalski'

    def test_client_username_double_collision(self, db):
        for uname in ('j.kowalski', 'ja.kowalski'):
            u = make_user(db, uname, 'pass123', 'client')
            make_member(db, u)
        db.session.commit()
        assert UserService.generate_client_username('Jan', 'Kowalski') == 'jan.kowalski'

    def test_trainer_username_format(self, db):
        assert UserService.generate_trainer_username('Jan', 'Kowalski') == 't.jan.kowalski'

    def test_trainer_username_collision_appends_number(self, db):
        u = make_user(db, 't.jan.kowalski', 'pass123', 'trainer')
        make_trainer(db, u)
        db.session.commit()
        assert UserService.generate_trainer_username('Jan', 'Kowalski') == 't.jan.kowalski2'


class TestClientCreation:
    def test_create_autogenerates_username_and_expiry(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/members/new', data={
            'first_name': 'Ewa', 'last_name': 'Nowak', 'password': 'klient123',
            'phone': '500', 'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert 'Login: e.nowak' in resp.data.decode()
        m = User.query.filter_by(username='e.nowak').first().member
        # nowy karnet miesięczny = aktywny do końca bieżącego miesiąca
        assert m.subscription_end == SubscriptionFactory.create('monthly').extend(None)

    def test_create_annual_expiry(self, client, db):
        login_admin(client, db)
        client.post('/admin/members/new', data={
            'first_name': 'Adam', 'last_name': 'Roczny', 'password': 'klient123',
            'subscription_type': 'annual',
        }, follow_redirects=True)
        m = User.query.filter_by(username='a.roczny').first().member
        assert m.subscription_end == SubscriptionFactory.create('annual').extend(None)

    def test_create_rejects_short_password(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/members/new', data={
            'first_name': 'X', 'last_name': 'Y', 'password': '123',
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert '6 znaków' in resp.data.decode()

    def test_edit_type_change_recomputes_expiry(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'k.test', 'pass123', 'client')
        m = make_member(db, u)   # monthly
        m.subscription_end = date(2020, 1, 1)
        db.session.commit()
        mid = m.id
        client.post(f'/admin/members/{mid}/edit', data={
            'first_name': 'K', 'last_name': 'Test', 'phone': '',
            'subscription_type': 'annual',
        }, follow_redirects=True)
        assert db.session.get(Member, mid).subscription_end == SubscriptionFactory.create('annual').extend(None)

    def test_renew_stacks_from_current_end(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'k.renew', 'pass123', 'client')
        m = make_member(db, u)
        future = date.today() + timedelta(days=40)   # aktywny w przyszłym miesiącu
        m.subscription_end = future
        db.session.commit()
        mid = m.id
        expected = SubscriptionFactory.create('monthly').extend(future)
        client.post(f'/admin/members/{mid}/renew', data={
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert db.session.get(Member, mid).subscription_end == expected


class TestPaymentsExport:
    def test_export_returns_csv(self, client, db):
        login_admin(client, db)
        cu = make_user(db, 'klient', 'pass123', 'client')
        m = make_member(db, cu)
        db.session.add(Payment(member_id=m.id, amount=99.0, month_year='2026-05',
                               status='completed', transfer_number='TRF-1234-5678-9012'))
        db.session.commit()
        resp = client.get('/admin/payments/export')
        assert resp.status_code == 200
        assert 'text/csv' in resp.headers['Content-Type']
        body = resp.data.decode('utf-8-sig')
        assert 'Numer przelewu' in body
        assert 'TRF-1234-5678-9012' in body
