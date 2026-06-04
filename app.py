import os
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from models import db, User, Member, Trainer, GymClass, Booking, Equipment
from functools import wraps
from datetime import datetime, date

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///gym.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
csrf = CSRFProtect(app)

DAY_ORDER = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']


# ── Auth decorators ──────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') != role:
                flash('Brak uprawnień.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Root / Auth ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'trainer':
        return redirect(url_for('trainer_dashboard'))
    return redirect(url_for('client_dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        flash('Nieprawidłowa nazwa użytkownika lub hasło.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Admin ────────────────────────────────────────────────────────────────────

@app.route('/admin/')
@role_required('admin')
def admin_dashboard():
    stats = {
        'members': Member.query.count(),
        'trainers': Trainer.query.count(),
        'classes': GymClass.query.count(),
        'bookings': Booking.query.filter_by(status='confirmed').count(),
    }
    recent_bookings = Booking.query.order_by(Booking.booked_at.desc()).limit(8).all()
    return render_template('admin/dashboard.html', stats=stats, recent_bookings=recent_bookings)


@app.route('/admin/members')
@role_required('admin')
def admin_members():
    members = Member.query.all()
    return render_template('admin/members.html', members=members, today=date.today())


@app.route('/admin/members/new', methods=['GET', 'POST'])
@role_required('admin')
def admin_member_new():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if User.query.filter_by(username=username).first():
            flash('Nazwa użytkownika już istnieje.', 'danger')
            return render_template('admin/member_form.html', member=None)

        user = User(username=username, role='client')
        user.set_password(request.form.get('password', ''))
        db.session.add(user)
        db.session.flush()

        sub_end_str = request.form.get('subscription_end', '')
        sub_end = datetime.strptime(sub_end_str, '%Y-%m-%d').date() if sub_end_str else None

        member = Member(
            user_id=user.id,
            first_name=request.form.get('first_name', ''),
            last_name=request.form.get('last_name', ''),
            phone=request.form.get('phone', ''),
            subscription_type=request.form.get('subscription_type', 'monthly'),
            subscription_end=sub_end,
        )
        db.session.add(member)
        db.session.commit()
        flash('Klient dodany pomyślnie.', 'success')
        return redirect(url_for('admin_members'))
    return render_template('admin/member_form.html', member=None)


@app.route('/admin/members/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_member_edit(id):
    member = Member.query.get_or_404(id)
    if request.method == 'POST':
        member.first_name = request.form.get('first_name', member.first_name)
        member.last_name = request.form.get('last_name', member.last_name)
        member.phone = request.form.get('phone', member.phone)
        member.subscription_type = request.form.get('subscription_type', member.subscription_type)
        sub_end_str = request.form.get('subscription_end', '')
        if sub_end_str:
            member.subscription_end = datetime.strptime(sub_end_str, '%Y-%m-%d').date()
        db.session.commit()
        flash('Dane zaktualizowane.', 'success')
        return redirect(url_for('admin_members'))
    return render_template('admin/member_form.html', member=member)


@app.route('/admin/members/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_member_delete(id):
    member = Member.query.get_or_404(id)
    db.session.delete(member.user)  # cascade → member → bookings
    db.session.commit()
    flash('Klient usunięty.', 'success')
    return redirect(url_for('admin_members'))


@app.route('/admin/trainers')
@role_required('admin')
def admin_trainers():
    trainers = Trainer.query.all()
    return render_template('admin/trainers.html', trainers=trainers)


@app.route('/admin/classes')
@role_required('admin')
def admin_classes():
    classes = sorted(GymClass.query.all(),
                     key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    trainers = Trainer.query.all()
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count() for c in classes}
    return render_template('admin/classes.html', classes=classes, trainers=trainers, booking_counts=booking_counts)


@app.route('/admin/classes/new', methods=['POST'])
@role_required('admin')
def admin_class_new():
    gym_class = GymClass(
        trainer_id=int(request.form.get('trainer_id')),
        name=request.form.get('name', ''),
        description=request.form.get('description', ''),
        max_capacity=int(request.form.get('max_capacity', 10)),
        schedule_day=request.form.get('schedule_day', ''),
        schedule_time=request.form.get('schedule_time', ''),
        duration_minutes=int(request.form.get('duration_minutes', 60)),
    )
    db.session.add(gym_class)
    db.session.commit()
    flash('Zajęcia dodane.', 'success')
    return redirect(url_for('admin_classes'))


@app.route('/admin/classes/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_class_delete(id):
    gym_class = GymClass.query.get_or_404(id)
    db.session.delete(gym_class)  # cascade → bookings
    db.session.commit()
    flash('Zajęcia usunięte.', 'success')
    return redirect(url_for('admin_classes'))


@app.route('/admin/equipment')
@role_required('admin')
def admin_equipment():
    equipment = Equipment.query.all()
    return render_template('admin/equipment.html', equipment=equipment)


# ── Trainer ──────────────────────────────────────────────────────────────────

@app.route('/trainer/')
@role_required('trainer')
def trainer_dashboard():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    days_pl = {
        'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa',
        'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Saturday': 'Sobota', 'Sunday': 'Niedziela',
    }
    today_pl = days_pl.get(datetime.now().strftime('%A'), '')
    today_classes = [c for c in trainer.classes if c.schedule_day == today_pl]
    total_members = len({b.member_id for c in trainer.classes for b in c.bookings if b.status == 'confirmed'})
    return render_template('trainer/dashboard.html',
                           trainer=trainer,
                           today_classes=today_classes,
                           today_name=today_pl,
                           total_members=total_members)


@app.route('/trainer/schedule')
@role_required('trainer')
def trainer_schedule():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    classes = sorted(trainer.classes,
                     key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count() for c in classes}
    return render_template('trainer/schedule.html', trainer=trainer, classes=classes, booking_counts=booking_counts)


@app.route('/trainer/members')
@role_required('trainer')
def trainer_members():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    members_dict = {}
    for c in trainer.classes:
        for b in c.bookings:
            if b.status == 'confirmed':
                if b.member_id not in members_dict:
                    members_dict[b.member_id] = {'member': b.member, 'classes': []}
                members_dict[b.member_id]['classes'].append(c.name)
    return render_template('trainer/members.html', trainer=trainer, members_data=list(members_dict.values()), today=date.today())


# ── Client ───────────────────────────────────────────────────────────────────

@app.route('/client/')
@role_required('client')
def client_dashboard():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings = (Booking.query.filter_by(member_id=member.id, status='confirmed')
                .order_by(Booking.booked_at.desc()).limit(5).all())
    subscription_active = (member.subscription_end is not None and member.subscription_end >= date.today())
    days_left = (member.subscription_end - date.today()).days if member.subscription_end else None
    return render_template('client/dashboard.html',
                           member=member,
                           bookings=bookings,
                           subscription_active=subscription_active,
                           days_left=days_left,
                           today=date.today())


@app.route('/client/classes')
@role_required('client')
def client_classes():
    user = db.session.get(User, session['user_id'])
    member = user.member
    classes = sorted(GymClass.query.all(),
                     key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    booked_ids = {b.class_id for b in Booking.query.filter_by(member_id=member.id, status='confirmed').all()}
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count() for c in classes}
    return render_template('client/classes.html', classes=classes, booked_ids=booked_ids, booking_counts=booking_counts)


@app.route('/client/classes/<int:id>/book', methods=['POST'])
@role_required('client')
def client_book(id):
    user = db.session.get(User, session['user_id'])
    member = user.member
    gym_class = GymClass.query.get_or_404(id)

    confirmed = Booking.query.filter_by(class_id=id, status='confirmed').count()
    if confirmed >= gym_class.max_capacity:
        flash('Brak wolnych miejsc na te zajęcia.', 'danger')
        return redirect(url_for('client_classes'))

    if Booking.query.filter_by(member_id=member.id, class_id=id, status='confirmed').first():
        flash('Jesteś już zapisany na te zajęcia.', 'warning')
        return redirect(url_for('client_classes'))

    db.session.add(Booking(member_id=member.id, class_id=id, status='confirmed'))
    db.session.commit()
    flash(f'Zapisano na: {gym_class.name}!', 'success')
    return redirect(url_for('client_bookings'))


@app.route('/client/bookings')
@role_required('client')
def client_bookings():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings = Booking.query.filter_by(member_id=member.id).order_by(Booking.booked_at.desc()).all()
    return render_template('client/bookings.html', member=member, bookings=bookings)


@app.route('/client/bookings/<int:id>/cancel', methods=['POST'])
@role_required('client')
def client_cancel(id):
    booking = Booking.query.get_or_404(id)
    user = db.session.get(User, session['user_id'])
    if booking.member_id != user.member.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('client_bookings'))
    booking.status = 'cancelled'
    db.session.commit()
    flash('Rezerwacja anulowana.', 'success')
    return redirect(url_for('client_bookings'))


@app.route('/client/profile')
@role_required('client')
def client_profile():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings_count = Booking.query.filter_by(member_id=member.id, status='confirmed').count()
    days_left = (member.subscription_end - date.today()).days if member.subscription_end else None
    return render_template('client/profile.html', member=member, today=date.today(),
                           bookings_count=bookings_count, days_left=days_left)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)
