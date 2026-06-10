import pytest
from datetime import date

from app import app as flask_app
from models import db as _db, User, Member, Trainer, GymClass, Booking


@pytest.fixture(scope="function")
def app():
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret",
    })
    ctx = flask_app.app_context()
    ctx.push()
    _db.create_all()
    yield flask_app
    _db.drop_all()
    ctx.pop()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def seeded(app):
    """Wypełnia bazę minimalnym zestawem danych testowych."""
    # admin
    admin = User(username="admin", role="admin")
    admin.set_password("admin123")
    _db.session.add(admin)

    # trener
    tu = User(username="trener1", role="trainer")
    tu.set_password("trener123")
    _db.session.add(tu)
    _db.session.flush()
    trainer = Trainer(user_id=tu.id, first_name="Jan", last_name="Kowalski",
                      specialization="Siłownia", hourly_rate=100.0)
    _db.session.add(trainer)
    _db.session.flush()

    # klient
    mu = User(username="klient1", role="client")
    mu.set_password("klient123")
    _db.session.add(mu)
    _db.session.flush()
    member = Member(user_id=mu.id, first_name="Tomasz", last_name="Król",
                    subscription_type="monthly", subscription_end=date(2027, 12, 31))
    _db.session.add(member)
    _db.session.flush()

    # zajęcia
    gym_class = GymClass(trainer_id=trainer.id, name="Trening Siłowy",
                         max_capacity=10, schedule_day="Poniedziałek",
                         schedule_time="10:00", duration_minutes=60)
    _db.session.add(gym_class)
    _db.session.commit()

    return {"admin": admin, "trainer": trainer, "member": member, "gym_class": gym_class}
