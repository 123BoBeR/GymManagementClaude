from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from extensions import db


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin | trainer | client

    member = db.relationship('Member', backref='user', uselist=False, cascade='all, delete-orphan')
    trainer = db.relationship('Trainer', backref='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(40), default='bell')        # ikona Bootstrap
    url = db.Column(db.String(200))                         # opcjonalny link akcji
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship(
        'User', backref=db.backref('notifications', cascade='all, delete-orphan'))


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    user = db.relationship(
        'User', backref=db.backref('reset_tokens', cascade='all, delete-orphan'))


class Member(db.Model):
    __tablename__ = 'members'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20))
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    subscription_type = db.Column(db.String(30))   # monthly | annual | day_pass
    subscription_end = db.Column(db.Date)

    bookings = db.relationship('Booking', backref='member', cascade='all, delete-orphan')


class Trainer(db.Model):
    __tablename__ = 'trainers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    specialization = db.Column(db.String(100))
    hourly_rate = db.Column(db.Float)

    classes = db.relationship('GymClass', backref='trainer')


class GymClass(db.Model):
    __tablename__ = 'gym_classes'
    id = db.Column(db.Integer, primary_key=True)
    trainer_id = db.Column(db.Integer, db.ForeignKey('trainers.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    max_capacity = db.Column(db.Integer, default=10)
    schedule_day = db.Column(db.String(20))         # Poniedziałek…Niedziela
    schedule_time = db.Column(db.String(10))        # HH:MM
    duration_minutes = db.Column(db.Integer, default=60)
    frequency_weeks = db.Column(db.Integer, default=1, nullable=False)  # co ile tygodni
    start_date = db.Column(db.Date, nullable=True)  # data pierwszej sesji

    # status propozycji: pending | approved | rejected
    status = db.Column(db.String(20), default='pending', nullable=False)
    rejection_note = db.Column(db.Text, nullable=True)

    sessions = db.relationship(
        'ClassSession', backref='gym_class',
        cascade='all, delete-orphan',
        order_by='ClassSession.session_date'
    )


class ClassSession(db.Model):
    __tablename__ = 'class_sessions'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('gym_classes.id'), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    cancelled = db.Column(db.Boolean, default=False)

    bookings = db.relationship('Booking', backref='session', cascade='all, delete-orphan')


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.id'), nullable=False)
    booked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='confirmed')  # confirmed | cancelled
    attended = db.Column(db.Boolean, nullable=True)  # None=nieoznaczone, True=był, False=nieobecny

    @property
    def gym_class(self):
        """Skrót dla wstecznej kompatybilności szablonów."""
        return self.session.gym_class


class WaitlistEntry(db.Model):
    __tablename__ = 'waitlist'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    member = db.relationship(
        'Member',
        backref=db.backref('waitlist_entries', cascade='all, delete-orphan'))
    session = db.relationship(
        'ClassSession',
        backref=db.backref('waitlist', cascade='all, delete-orphan'))


class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    status = db.Column(db.String(20), default='working')  # working | maintenance | broken
    purchase_date = db.Column(db.Date)


class ContactOption(db.Model):
    __tablename__ = 'contact_options'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(80), nullable=False)     # np. "Recepcja", "Email"
    value = db.Column(db.String(200), nullable=False)    # np. "+48 500 100 200"
    icon = db.Column(db.String(40), default='info-circle')  # nazwa ikony Bootstrap


class Payment(db.Model):
    __tablename__ = 'payments'
    __table_args__ = (
        db.UniqueConstraint('member_id', 'month_year', name='uq_payment_member_month'),
    )
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    month_year = db.Column(db.String(7), nullable=False)         # format: "YYYY-MM"
    status = db.Column(db.String(20), default='pending')         # pending | completed
    transfer_number = db.Column(db.String(60))                   # numer przelewu TRF-xxxx-xxxx-xxxx
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = db.Column(db.DateTime)

    member = db.relationship(
        'Member',
        backref=db.backref('payments', cascade='all, delete-orphan'))
