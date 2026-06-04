import pytest
from datetime import date, timedelta
from app import create_app
from extensions import db as _db
from models import User, Member, Trainer, GymClass, ClassSession, Booking, WaitlistEntry


@pytest.fixture(scope='session')
def app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret',
    })
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope='function')
def db(app):
    with app.app_context():
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


# ── Pomocnicze fabryki ────────────────────────────────────────────────────────

def make_user(db, username='testuser', password='pass123', role='client'):
    u = User(username=username, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    return u


def make_member(db, user):
    m = Member(
        user_id=user.id,
        first_name='Jan', last_name='Testowy',
        subscription_type='monthly',
        subscription_end=date.today() + timedelta(days=30),
    )
    db.session.add(m)
    db.session.flush()
    return m


def make_trainer(db, user):
    t = Trainer(user_id=user.id, first_name='Anna', last_name='Trener',
                specialization='Yoga', hourly_rate=100)
    db.session.add(t)
    db.session.flush()
    return t


def make_class(db, trainer, status='approved', day='Poniedziałek', time='10:00',
               duration=60, capacity=10, freq=1):
    c = GymClass(
        trainer_id=trainer.id, name='Test Yoga', description='Opis',
        max_capacity=capacity, schedule_day=day, schedule_time=time,
        duration_minutes=duration, frequency_weeks=freq,
        start_date=date.today(), status=status,
    )
    db.session.add(c)
    db.session.flush()
    return c


def make_session(db, gym_class, delta_days=1):
    s = ClassSession(
        class_id=gym_class.id,
        session_date=date.today() + timedelta(days=delta_days),
    )
    db.session.add(s)
    db.session.flush()
    return s


def make_booking(db, member, session, status='confirmed'):
    b = Booking(member_id=member.id, session_id=session.id, status=status)
    db.session.add(b)
    db.session.flush()
    return b
