"""Testy autoryzacji i kontroli dostępu."""
import pytest
from models import User
from tests.conftest import make_user, make_member, make_trainer


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


def logout(client):
    return client.get('/logout', follow_redirects=True)


class TestLogin:
    def test_login_valid_credentials(self, client, db):
        make_user(db, 'admin1', 'secret', 'admin')
        db.session.commit()
        resp = login(client, 'admin1', 'secret')
        assert resp.status_code == 200
        assert 'GymApp' in resp.data.decode()

    def test_login_wrong_password(self, client, db):
        make_user(db, 'user1', 'correct', 'client')
        db.session.commit()
        resp = login(client, 'user1', 'wrong')
        assert 'Nieprawidłowa' in resp.data.decode()

    def test_login_unknown_user(self, client, db):
        resp = login(client, 'nobody', 'pass')
        assert 'Nieprawidłowa' in resp.data.decode()

    def test_logout_clears_session(self, client, db):
        u = make_user(db, 'user2', 'pass123', 'client')
        make_member(db, u)
        db.session.commit()
        login(client, 'user2', 'pass123')
        resp = logout(client)
        # Po wylogowaniu powinien wrócić do logowania
        assert b'Zaloguj' in resp.data


class TestRegistration:
    def test_register_creates_account_and_logs_in(self, client, db):
        resp = client.post('/register', data={
            'first_name': 'Adam', 'last_name': 'Nowak', 'phone': '500',
            'password': 'haslo123', 'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert 'a.nowak' in resp.data.decode()          # login pokazany we flashu
        u = User.query.filter_by(username='a.nowak').first()
        assert u is not None and u.role == 'client'
        assert u.member is not None
        assert u.member.subscription_end is not None     # karnet aktywny

    def test_register_short_password_rejected(self, client, db):
        resp = client.post('/register', data={
            'first_name': 'Ewa', 'last_name': 'Kort', 'password': '123',
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert '6 znaków' in resp.data.decode()
        assert User.query.filter_by(username='e.kort').first() is None

    def test_register_collision_generates_unique_login(self, client, db):
        client.post('/register', data={
            'first_name': 'Jan', 'last_name': 'Kowalski', 'password': 'haslo123',
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        client.get('/logout')
        client.post('/register', data={
            'first_name': 'Jan', 'last_name': 'Kowalski', 'password': 'haslo123',
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert User.query.filter_by(role='client').count() == 2
        assert User.query.filter_by(username='j.kowalski').first() is not None
        assert User.query.filter_by(username='ja.kowalski').first() is not None

    def test_register_invalid_subscription_rejected(self, client, db):
        resp = client.post('/register', data={
            'first_name': 'X', 'last_name': 'Y', 'password': 'haslo123',
            'subscription_type': 'bogus',
        }, follow_redirects=True)
        assert 'karnet' in resp.data.decode().lower()


class TestPasswordReset:
    def test_forgot_shows_link_for_existing_user(self, client, db):
        make_user(db, 'reset.me', 'oldpass', 'client')
        db.session.commit()
        resp = client.post('/forgot-password', data={'username': 'reset.me'},
                           follow_redirects=True)
        assert '/reset-password/' in resp.data.decode()

    def test_forgot_unknown_user_no_link(self, client, db):
        resp = client.post('/forgot-password', data={'username': 'nieistnieje'},
                           follow_redirects=True)
        body = resp.data.decode()
        assert '/reset-password/' not in body          # brak linku
        assert 'konto istnieje' in body                # komunikat jednakowy

    def test_reset_changes_password(self, client, db):
        from services import UserService
        u = make_user(db, 'reset.ok', 'oldpass', 'client')
        db.session.commit()
        token = UserService.create_reset_token('reset.ok')
        resp = client.post(f'/reset-password/{token}', data={
            'new_password': 'noweHaslo', 'confirm_password': 'noweHaslo',
        }, follow_redirects=True)
        assert 'zmienione' in resp.data.decode().lower()
        assert db.session.get(User, u.id).check_password('noweHaslo')

    def test_token_single_use(self, db):
        from services import UserService
        make_user(db, 'reset.once', 'oldpass', 'client')
        db.session.commit()
        token = UserService.create_reset_token('reset.once')
        ok1, _ = UserService.reset_password_with_token(token, 'haslo1', 'haslo1')
        ok2, _ = UserService.reset_password_with_token(token, 'haslo2', 'haslo2')
        assert ok1 is True and ok2 is False

    def test_expired_token_rejected(self, db):
        from datetime import datetime, timezone, timedelta
        from models import PasswordResetToken
        from services import UserService
        u = make_user(db, 'reset.exp', 'oldpass', 'client')
        db.session.commit()
        db.session.add(PasswordResetToken(
            user_id=u.id, token='expired-token',
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.session.commit()
        ok, msg = UserService.reset_password_with_token('expired-token', 'haslo1', 'haslo1')
        assert ok is False
        assert 'wygas' in msg.lower()


class TestHardening:
    def test_security_headers_present(self, client, db):
        resp = client.get('/login')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
        assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'
        assert resp.headers.get('Referrer-Policy') == 'same-origin'

    def test_secret_key_required_in_production(self, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        monkeypatch.delenv('SECRET_KEY', raising=False)
        from app import create_app
        with pytest.raises(RuntimeError):
            create_app()


class TestRoleAccess:
    def test_client_cannot_access_admin(self, client, db):
        u = make_user(db, 'klient1', 'pass', 'client')
        make_member(db, u)
        db.session.commit()
        login(client, 'klient1', 'pass')
        resp = client.get('/admin/', follow_redirects=True)
        assert 'Brak uprawnień' in resp.data.decode()

    def test_trainer_cannot_access_admin(self, client, db):
        u = make_user(db, 'trener1', 'pass', 'trainer')
        make_trainer(db, u)
        db.session.commit()
        login(client, 'trener1', 'pass')
        resp = client.get('/admin/', follow_redirects=True)
        assert 'Brak uprawnień' in resp.data.decode()

    def test_unauthenticated_redirects_to_login(self, client, db):
        resp = client.get('/admin/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_admin_can_access_admin(self, client, db):
        make_user(db, 'admin2', 'pass', 'admin')
        db.session.commit()
        login(client, 'admin2', 'pass')
        resp = client.get('/admin/')
        assert resp.status_code == 200
