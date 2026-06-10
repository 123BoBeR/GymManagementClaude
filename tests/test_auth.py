"""Testy warstwy autoryzacji — logowanie, wylogowanie, kontrola dostępu."""


class TestLoginPage:

    def test_login_page_loads(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert "GymApp" in r.data.decode()

    def test_root_redirects_to_login_when_unauthenticated(self, client):
        r = client.get("/")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_admin_panel_blocked_without_login(self, client):
        r = client.get("/admin/")
        assert r.status_code == 302

    def test_trainer_panel_blocked_without_login(self, client):
        r = client.get("/trainer/")
        assert r.status_code == 302

    def test_client_panel_blocked_without_login(self, client):
        r = client.get("/client/")
        assert r.status_code == 302


class TestLogin:

    def test_admin_login_success(self, client, seeded):
        r = client.post("/login",
                        data={"username": "admin", "password": "admin123"},
                        follow_redirects=True)
        assert r.status_code == 200
        assert "Dashboard" in r.data.decode()

    def test_login_wrong_password(self, client, seeded):
        r = client.post("/login",
                        data={"username": "admin", "password": "zle_haslo"},
                        follow_redirects=True)
        assert "Nieprawid" in r.data.decode()

    def test_login_nonexistent_user(self, client, seeded):
        r = client.post("/login",
                        data={"username": "ghost", "password": "abc"},
                        follow_redirects=True)
        assert "Nieprawid" in r.data.decode()

    def test_trainer_login_redirects_to_trainer_dashboard(self, client, seeded):
        r = client.post("/login",
                        data={"username": "trener1", "password": "trener123"},
                        follow_redirects=True)
        assert r.status_code == 200
        assert r.request.path == "/trainer/"

    def test_client_login_redirects_to_client_dashboard(self, client, seeded):
        r = client.post("/login",
                        data={"username": "klient1", "password": "klient123"},
                        follow_redirects=True)
        assert r.status_code == 200
        assert r.request.path == "/client/"


class TestRoleAccess:

    def _login(self, client, username, password):
        client.post("/login", data={"username": username, "password": password})

    def test_client_cannot_access_admin_panel(self, client, seeded):
        self._login(client, "klient1", "klient123")
        r = client.get("/admin/", follow_redirects=True)
        assert "Brak uprawnień" in r.data.decode()

    def test_trainer_cannot_access_admin_panel(self, client, seeded):
        self._login(client, "trener1", "trener123")
        r = client.get("/admin/", follow_redirects=True)
        assert "Brak uprawnień" in r.data.decode()

    def test_admin_cannot_access_client_panel(self, client, seeded):
        self._login(client, "admin", "admin123")
        r = client.get("/client/", follow_redirects=True)
        assert "Brak uprawnień" in r.data.decode()


class TestLogout:

    def test_logout_clears_session(self, client, seeded):
        client.post("/login", data={"username": "admin", "password": "admin123"})
        client.get("/logout")
        r = client.get("/admin/")
        assert r.status_code == 302
