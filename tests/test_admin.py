"""Testy operacji administracyjnych: CRUD trenerów."""
import pytest
from models import User, Trainer
from tests.conftest import make_user, make_trainer, make_class


def login_admin(client, db):
    u = make_user(db, 'admin', 'admin123', 'admin')
    db.session.commit()
    client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    return u


class TestTrainerCrud:
    def test_create_trainer(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/trainers/new', data={
            'first_name': 'Jan', 'last_name': 'Nowak', 'username': 'jan.nowak',
            'password': 'trener123', 'specialization': 'Boks', 'hourly_rate': '150',
        }, follow_redirects=True)
        assert 'dodany' in resp.data.decode()
        t = User.query.filter_by(username='jan.nowak').first()
        assert t is not None and t.role == 'trainer'
        assert t.trainer.specialization == 'Boks'

    def test_create_rejects_duplicate_username(self, client, db):
        login_admin(client, db)
        existing = make_user(db, 'zajety', 'pass123', 'trainer')
        make_trainer(db, existing)
        db.session.commit()
        resp = client.post('/admin/trainers/new', data={
            'first_name': 'X', 'last_name': 'Y', 'username': 'zajety',
            'password': 'trener123',
        }, follow_redirects=True)
        assert 'już istnieje' in resp.data.decode()

    def test_create_rejects_short_password(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/trainers/new', data={
            'first_name': 'X', 'last_name': 'Y', 'username': 'krotkie',
            'password': '123',
        }, follow_redirects=True)
        assert '6 znaków' in resp.data.decode()
        assert User.query.filter_by(username='krotkie').first() is None

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
