"""Testy autoryzacji i kontroli dostępu."""
import pytest
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
