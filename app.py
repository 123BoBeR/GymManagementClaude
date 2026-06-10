import csv
import io
import json
import os
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify, Response
from dotenv import load_dotenv
from models import db, User, Member, Trainer, GymClass, Booking, Equipment, Payment, Waitlist
from services import (BookingService, MemberService, TrainerService,
                      EquipmentService, SubscriptionFactory, PaymentService,
                      WaitlistService, UserService)
from functools import wraps
from datetime import datetime, date

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///gym.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

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


# ── Admin — klienci ──────────────────────────────────────────────────────────

@app.route('/admin/')
@role_required('admin')
def admin_dashboard():
    stats = {
        'members': Member.query.count(),
        'trainers': Trainer.query.count(),
        'classes': GymClass.query.count(),
        'bookings': Booking.query.filter_by(status='confirmed').count(),
    }
    recent_bookings = Booking.query.order_by(Booking.booked_at.desc()).limit(6).all()

    # Dochody miesięczne — ostatnie 6 miesięcy
    _PL_SHORT = {1:'Sty',2:'Lut',3:'Mar',4:'Kwi',5:'Maj',6:'Cze',
                 7:'Lip',8:'Sie',9:'Wrz',10:'Paź',11:'Lis',12:'Gru'}
    revenue_map = {}
    for p in Payment.query.filter_by(status='completed').all():
        revenue_map[p.month_year] = revenue_map.get(p.month_year, 0) + p.amount

    cur = date.today().replace(day=1)
    rev_labels, rev_data = [], []
    for _ in range(6):
        key = cur.strftime('%Y-%m')
        rev_labels.insert(0, f"{_PL_SHORT[cur.month]} {cur.year}")
        rev_data.insert(0, round(revenue_map.get(key, 0), 2))
        cur = cur.replace(month=cur.month - 1) if cur.month > 1 else cur.replace(year=cur.year - 1, month=12)

    # Podział typów karnetów
    sub_labels = ['Miesięczny', 'Roczny', 'Dzienny']
    sub_data = [
        Member.query.filter_by(subscription_type='monthly').count(),
        Member.query.filter_by(subscription_type='annual').count(),
        Member.query.filter_by(subscription_type='day_pass').count(),
    ]

    # Top 5 zajęć wg liczby rezerwacji
    class_stats = sorted(
        [(gc.name, Booking.query.filter_by(class_id=gc.id, status='confirmed').count())
         for gc in GymClass.query.all()],
        key=lambda x: -x[1]
    )[:5]

    broken_count = Equipment.query.filter_by(status='broken').count()
    maintenance_count = Equipment.query.filter_by(status='maintenance').count()

    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_bookings=recent_bookings,
        rev_labels=json.dumps(rev_labels),
        rev_data=json.dumps(rev_data),
        sub_labels=json.dumps(sub_labels),
        sub_data=json.dumps(sub_data),
        class_labels=json.dumps([c[0] for c in class_stats]),
        class_data=json.dumps([c[1] for c in class_stats]),
        broken_count=broken_count,
        maintenance_count=maintenance_count,
    )


@app.route('/admin/members')
@role_required('admin')
def admin_members():
    members = Member.query.all()
    return render_template('admin/members.html', members=members, today=date.today())


@app.route('/admin/members/new', methods=['GET', 'POST'])
@role_required('admin')
def admin_member_new():
    if request.method == 'POST':
        sub_end_str = request.form.get('subscription_end', '')
        sub_end = datetime.strptime(sub_end_str, '%Y-%m-%d').date() if sub_end_str else None

        ok, msg = MemberService.create(
            username=request.form.get('username', '').strip(),
            password=request.form.get('password', ''),
            first_name=request.form.get('first_name', ''),
            last_name=request.form.get('last_name', ''),
            phone=request.form.get('phone', ''),
            sub_type=request.form.get('subscription_type', 'monthly'),
            sub_end=sub_end,
        )
        flash(msg, 'success' if ok else 'danger')
        if ok:
            return redirect(url_for('admin_members'))
    return render_template('admin/member_form.html', member=None)


@app.route('/admin/members/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_member_edit(id):
    member = Member.query.get_or_404(id)
    if request.method == 'POST':
        sub_end_str = request.form.get('subscription_end', '')
        sub_end = datetime.strptime(sub_end_str, '%Y-%m-%d').date() if sub_end_str else None

        ok, msg = MemberService.update(
            member=member,
            first_name=request.form.get('first_name', member.first_name),
            last_name=request.form.get('last_name', member.last_name),
            phone=request.form.get('phone', member.phone),
            sub_type=request.form.get('subscription_type', member.subscription_type),
            sub_end=sub_end,
        )
        flash(msg, 'success' if ok else 'danger')
        if ok:
            return redirect(url_for('admin_members'))
    return render_template('admin/member_form.html', member=member)


@app.route('/admin/members/export')
@role_required('admin')
def admin_members_export():
    members = Member.query.all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['ID', 'Imię', 'Nazwisko', 'Login', 'Telefon',
                'Typ karnetu', 'Wygasa', 'Status'])
    for m in members:
        active = 'Aktywny' if MemberService.is_active(m) else 'Nieaktywny'
        sub_label = {'monthly': 'Miesięczny', 'annual': 'Roczny',
                     'day_pass': 'Dzienny'}.get(m.subscription_type or '', '—')
        w.writerow([m.id, m.first_name, m.last_name, m.user.username,
                    m.phone or '', sub_label,
                    m.subscription_end.strftime('%Y-%m-%d') if m.subscription_end else '',
                    active])
    buf.seek(0)
    return Response(
        buf.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=klienci.csv'},
    )


@app.route('/admin/members/<int:id>/reset-password', methods=['POST'])
@role_required('admin')
def admin_member_reset_password(id):
    member = Member.query.get_or_404(id)
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('Hasło musi mieć co najmniej 6 znaków.', 'danger')
        return redirect(url_for('admin_members'))
    member.user.set_password(new_password)
    db.session.commit()
    flash(f'Hasło dla {member.first_name} {member.last_name} zostało zresetowane.', 'success')
    return redirect(url_for('admin_members'))


@app.route('/admin/members/<int:id>/renew', methods=['POST'])
@role_required('admin')
def admin_member_renew(id):
    member = Member.query.get_or_404(id)
    months = int(request.form.get('months', 1))
    base = max(member.subscription_end, date.today()) if member.subscription_end else date.today()
    # Dodaj miesiące ręcznie (unikamy dateutil)
    year = base.year + (base.month - 1 + months) // 12
    month = (base.month - 1 + months) % 12 + 1
    import calendar
    day = min(base.day, calendar.monthrange(year, month)[1])
    member.subscription_end = date(year, month, day)
    db.session.commit()
    flash(
        f'Karnet {member.first_name} {member.last_name} przedłużony do '
        f'{member.subscription_end.strftime("%d.%m.%Y")}.',
        'success'
    )
    return redirect(url_for('admin_members'))


@app.route('/admin/members/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_member_delete(id):
    member = Member.query.get_or_404(id)
    _, msg = MemberService.delete(member)
    flash(msg, 'success')
    return redirect(url_for('admin_members'))


# ── Admin — trenerzy ─────────────────────────────────────────────────────────

@app.route('/admin/trainers')
@role_required('admin')
def admin_trainers():
    trainers = Trainer.query.all()
    return render_template('admin/trainers.html', trainers=trainers)


@app.route('/admin/trainers/new', methods=['GET', 'POST'])
@role_required('admin')
def admin_trainer_new():
    if request.method == 'POST':
        ok, msg = TrainerService.create(
            username=request.form.get('username', '').strip(),
            password=request.form.get('password', ''),
            first_name=request.form.get('first_name', ''),
            last_name=request.form.get('last_name', ''),
            specialization=request.form.get('specialization', ''),
            hourly_rate=float(request.form.get('hourly_rate') or 0),
        )
        flash(msg, 'success' if ok else 'danger')
        if ok:
            return redirect(url_for('admin_trainers'))
    return render_template('admin/trainer_form.html', trainer=None)


@app.route('/admin/trainers/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_trainer_edit(id):
    trainer = Trainer.query.get_or_404(id)
    if request.method == 'POST':
        ok, msg = TrainerService.update(
            trainer=trainer,
            first_name=request.form.get('first_name', trainer.first_name),
            last_name=request.form.get('last_name', trainer.last_name),
            specialization=request.form.get('specialization', trainer.specialization),
            hourly_rate=float(request.form.get('hourly_rate') or 0),
        )
        flash(msg, 'success' if ok else 'danger')
        if ok:
            return redirect(url_for('admin_trainers'))
    return render_template('admin/trainer_form.html', trainer=trainer)


@app.route('/admin/trainers/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_trainer_delete(id):
    trainer = Trainer.query.get_or_404(id)
    _, msg = TrainerService.delete(trainer)
    flash(msg, 'success')
    return redirect(url_for('admin_trainers'))


# ── Admin — zajęcia ──────────────────────────────────────────────────────────

@app.route('/admin/classes')
@role_required('admin')
def admin_classes():
    classes = sorted(GymClass.query.all(),
                     key=lambda c: (DAY_ORDER.index(c.schedule_day)
                                    if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    trainers = Trainer.query.all()
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count()
                      for c in classes}
    return render_template('admin/classes.html', classes=classes, trainers=trainers,
                           booking_counts=booking_counts)


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


@app.route('/admin/classes/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_class_edit(id):
    gym_class = GymClass.query.get_or_404(id)
    trainers = Trainer.query.all()
    if request.method == 'POST':
        gym_class.name = request.form.get('name', gym_class.name)
        gym_class.description = request.form.get('description', '')
        gym_class.trainer_id = int(request.form.get('trainer_id', gym_class.trainer_id))
        gym_class.schedule_day = request.form.get('schedule_day', gym_class.schedule_day)
        gym_class.schedule_time = request.form.get('schedule_time', gym_class.schedule_time)
        gym_class.duration_minutes = int(request.form.get('duration_minutes', gym_class.duration_minutes))
        gym_class.max_capacity = int(request.form.get('max_capacity', gym_class.max_capacity))
        db.session.commit()
        flash('Zajęcia zaktualizowane.', 'success')
        return redirect(url_for('admin_classes'))
    return render_template('admin/class_edit.html', gym_class=gym_class, trainers=trainers)


@app.route('/admin/classes/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_class_delete(id):
    gym_class = GymClass.query.get_or_404(id)
    db.session.delete(gym_class)
    db.session.commit()
    flash('Zajęcia usunięte.', 'success')
    return redirect(url_for('admin_classes'))


# ── Admin — sprzęt ───────────────────────────────────────────────────────────

@app.route('/admin/equipment')
@role_required('admin')
def admin_equipment():
    equipment = Equipment.query.all()
    return render_template('admin/equipment.html', equipment=equipment)


@app.route('/admin/equipment/new', methods=['POST'])
@role_required('admin')
def admin_equipment_new():
    pd_str = request.form.get('purchase_date', '')
    purchase_date = datetime.strptime(pd_str, '%Y-%m-%d').date() if pd_str else None
    ok, msg = EquipmentService.create(
        name=request.form.get('name', ''),
        category=request.form.get('category', ''),
        status=request.form.get('status', 'working'),
        purchase_date=purchase_date,
    )
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('admin_equipment'))


@app.route('/admin/equipment/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_equipment_edit(id):
    equipment = Equipment.query.get_or_404(id)
    if request.method == 'POST':
        pd_str = request.form.get('purchase_date', '')
        purchase_date = datetime.strptime(pd_str, '%Y-%m-%d').date() if pd_str else None
        ok, msg = EquipmentService.update(
            equipment=equipment,
            name=request.form.get('name', equipment.name),
            category=request.form.get('category', equipment.category),
            status=request.form.get('status', equipment.status),
            purchase_date=purchase_date,
        )
        flash(msg, 'success' if ok else 'danger')
        if ok:
            return redirect(url_for('admin_equipment'))
    return render_template('admin/equipment_form.html', equipment=equipment)


@app.route('/admin/equipment/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_equipment_delete(id):
    equipment = Equipment.query.get_or_404(id)
    _, msg = EquipmentService.delete(equipment)
    flash(msg, 'success')
    return redirect(url_for('admin_equipment'))


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
    total_members = len({b.member_id for c in trainer.classes
                         for b in c.bookings if b.status == 'confirmed'})
    return render_template('trainer/dashboard.html', trainer=trainer,
                           today_classes=today_classes, today_name=today_pl,
                           total_members=total_members)


@app.route('/trainer/schedule')
@role_required('trainer')
def trainer_schedule():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    classes = sorted(trainer.classes,
                     key=lambda c: (DAY_ORDER.index(c.schedule_day)
                                    if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count()
                      for c in classes}
    return render_template('trainer/schedule.html', trainer=trainer,
                           classes=classes, booking_counts=booking_counts)


@app.route('/trainer/profile', methods=['GET', 'POST'])
@role_required('trainer')
def trainer_profile():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    if request.method == 'POST':
        ok, msg = TrainerService.update(
            trainer=trainer,
            first_name=trainer.first_name,
            last_name=trainer.last_name,
            specialization=request.form.get('specialization', ''),
            hourly_rate=float(request.form.get('hourly_rate') or 0),
        )
        flash(msg, 'success' if ok else 'danger')
        return redirect(url_for('trainer_profile'))
    return render_template('trainer/profile.html', trainer=trainer)


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
    return render_template('trainer/members.html', trainer=trainer,
                           members_data=list(members_dict.values()), today=date.today())


# ── Client ───────────────────────────────────────────────────────────────────

@app.route('/client/')
@role_required('client')
def client_dashboard():
    user = db.session.get(User, session['user_id'])
    member = user.member
    subscription_active = MemberService.is_active(member)
    days_left = (member.subscription_end - date.today()).days if member.subscription_end else None

    # Zajęcia w tym tygodniu (od dziś do niedzieli włącznie)
    today_idx = date.today().weekday()  # 0=pon, 6=nd
    confirmed = Booking.query.filter_by(member_id=member.id, status='confirmed').all()
    upcoming = sorted(
        [b for b in confirmed if DAY_ORDER.index(b.gym_class.schedule_day) >= today_idx
         if b.gym_class.schedule_day in DAY_ORDER],
        key=lambda b: (DAY_ORDER.index(b.gym_class.schedule_day), b.gym_class.schedule_time)
    )

    return render_template('client/dashboard.html', member=member,
                           upcoming=upcoming, subscription_active=subscription_active,
                           days_left=days_left, today=date.today())


@app.route('/client/classes')
@role_required('client')
def client_classes():
    user = db.session.get(User, session['user_id'])
    member = user.member
    view = request.args.get('view', 'grid')
    classes = sorted(GymClass.query.all(),
                     key=lambda c: (DAY_ORDER.index(c.schedule_day)
                                    if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    booked_ids = {b.class_id for b in
                  Booking.query.filter_by(member_id=member.id, status='confirmed').all()}
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count()
                      for c in classes}
    waitlist_ids = {w.class_id for w in Waitlist.query.filter_by(member_id=member.id).all()}
    waitlist_pos = {cid: WaitlistService.position(member.id, cid) for cid in waitlist_ids}
    waitlist_counts = {c.id: Waitlist.query.filter_by(class_id=c.id).count() for c in classes}
    # Grupowanie po dniach dla widoku tygodniowego
    week = {day: [] for day in DAY_ORDER}
    for c in classes:
        if c.schedule_day in week:
            week[c.schedule_day].append(c)
    return render_template('client/classes.html', classes=classes,
                           booked_ids=booked_ids, booking_counts=booking_counts,
                           waitlist_ids=waitlist_ids, waitlist_pos=waitlist_pos,
                           waitlist_counts=waitlist_counts, week=week,
                           day_order=DAY_ORDER, view=view)


@app.route('/client/classes/<int:id>/book', methods=['POST'])
@role_required('client')
def client_book(id):
    user = db.session.get(User, session['user_id'])
    ok, msg = BookingService.book(user.member.id, id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client_bookings') if ok else url_for('client_classes'))


@app.route('/client/classes/<int:id>/waitlist', methods=['POST'])
@role_required('client')
def client_waitlist_join(id):
    user = db.session.get(User, session['user_id'])
    ok, msg = WaitlistService.join(user.member.id, id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client_classes'))


@app.route('/client/classes/<int:id>/waitlist/leave', methods=['POST'])
@role_required('client')
def client_waitlist_leave(id):
    user = db.session.get(User, session['user_id'])
    ok, msg = WaitlistService.leave(user.member.id, id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client_classes'))


@app.route('/client/bookings')
@role_required('client')
def client_bookings():
    user = db.session.get(User, session['user_id'])
    member = user.member
    status_filter = request.args.get('status', 'active')
    query = Booking.query.filter_by(member_id=member.id)
    if status_filter == 'active':
        query = query.filter_by(status='confirmed')
    elif status_filter == 'cancelled':
        query = query.filter_by(status='cancelled')
    bookings = query.order_by(Booking.booked_at.desc()).all()
    return render_template('client/bookings.html', member=member,
                           bookings=bookings, status_filter=status_filter)


@app.route('/client/bookings/<int:id>/cancel', methods=['POST'])
@role_required('client')
def client_cancel(id):
    user = db.session.get(User, session['user_id'])
    ok, msg = BookingService.cancel(id, user.member.id)
    flash(msg, 'success' if ok else 'danger')
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


@app.route('/client/profile/change-password', methods=['POST'])
@role_required('client')
def client_change_password():
    user = db.session.get(User, session['user_id'])
    ok, msg = UserService.change_password(
        user,
        request.form.get('old_password', ''),
        request.form.get('new_password', ''),
        request.form.get('confirm_password', ''),
    )
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client_profile'))


@app.route('/client/profile/edit', methods=['POST'])
@role_required('client')
def client_profile_edit():
    user = db.session.get(User, session['user_id'])
    member = user.member
    ok, msg = MemberService.update(
        member=member,
        first_name=request.form.get('first_name', member.first_name).strip(),
        last_name=request.form.get('last_name', member.last_name).strip(),
        phone=request.form.get('phone', '').strip(),
        sub_type=member.subscription_type,
        sub_end=member.subscription_end,
    )
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client_profile'))


@app.route('/trainer/profile/change-password', methods=['POST'])
@role_required('trainer')
def trainer_change_password():
    user = db.session.get(User, session['user_id'])
    ok, msg = UserService.change_password(
        user,
        request.form.get('old_password', ''),
        request.form.get('new_password', ''),
        request.form.get('confirm_password', ''),
    )
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('trainer_profile'))


@app.route('/admin/profile/change-password', methods=['POST'])
@role_required('admin')
def admin_change_password():
    user = db.session.get(User, session['user_id'])
    ok, msg = UserService.change_password(
        user,
        request.form.get('old_password', ''),
        request.form.get('new_password', ''),
        request.form.get('confirm_password', ''),
    )
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('admin_dashboard'))


# ── Admin — kolejka oczekujących ─────────────────────────────────────────────

@app.route('/admin/waitlist')
@role_required('admin')
def admin_waitlist():
    entries = (Waitlist.query
               .order_by(Waitlist.class_id, Waitlist.added_at)
               .all())
    return render_template('admin/waitlist.html', entries=entries)


# ── Client — płatności ───────────────────────────────────────────────────────

@app.route('/client/payments')
@role_required('client')
def client_payments():
    user = db.session.get(User, session['user_id'])
    member = user.member
    months = PaymentService.months_for_member(member)
    return render_template('client/payments.html', member=member, months=months)


@app.route('/client/payments/initiate', methods=['POST'])
@role_required('client')
def client_payment_initiate():
    user = db.session.get(User, session['user_id'])
    data = request.get_json() or {}
    ok, result = PaymentService.initiate(user.member.id, data.get('month_year', ''))
    return jsonify({"ok": ok, **result})


@app.route('/client/payments/<int:payment_id>/confirm', methods=['POST'])
@role_required('client')
def client_payment_confirm(payment_id):
    user = db.session.get(User, session['user_id'])
    ok, msg = PaymentService.confirm(payment_id, user.member.id)
    return jsonify({"ok": ok, "message": msg})


# ── Admin — płatności ────────────────────────────────────────────────────────

@app.route('/admin/payments')
@role_required('admin')
def admin_payments():
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    return render_template('admin/payments.html', payments=payments)


# ── Client — szczegóły zajęć ────────────────────────────────────────────────

@app.route('/client/classes/<int:id>')
@role_required('client')
def client_class_detail(id):
    user = db.session.get(User, session['user_id'])
    member = user.member
    gym_class = GymClass.query.get_or_404(id)
    cnt = Booking.query.filter_by(class_id=id, status='confirmed').count()
    booked = Booking.query.filter_by(member_id=member.id, class_id=id, status='confirmed').first() is not None
    in_waitlist = Waitlist.query.filter_by(member_id=member.id, class_id=id).first() is not None
    wpos = WaitlistService.position(member.id, id) if in_waitlist else None
    wcnt = Waitlist.query.filter_by(class_id=id).count()
    return render_template('client/class_detail.html',
                           gym_class=gym_class, cnt=cnt, booked=booked,
                           in_waitlist=in_waitlist, wpos=wpos, wcnt=wcnt)


# ── Admin — płatności klienta ────────────────────────────────────────────────

@app.route('/admin/members/<int:id>/payments')
@role_required('admin')
def admin_member_payments(id):
    member = Member.query.get_or_404(id)
    payments = (Payment.query.filter_by(member_id=id)
                .order_by(Payment.created_at.desc()).all())
    total_paid = sum(p.amount for p in payments if p.status == 'completed')
    return render_template('admin/member_payments.html',
                           member=member, payments=payments, total_paid=total_paid)


# ── Admin — uczestnicy zajęć ─────────────────────────────────────────────────

@app.route('/admin/classes/<int:id>/members')
@role_required('admin')
def admin_class_members(id):
    gym_class = GymClass.query.get_or_404(id)
    bookings = (Booking.query.filter_by(class_id=id, status='confirmed')
                .order_by(Booking.booked_at).all())
    return render_template('admin/class_members.html',
                           gym_class=gym_class, bookings=bookings, today=date.today())


# ── Trainer — uczestnicy zajęć ───────────────────────────────────────────────

@app.route('/trainer/classes/<int:id>/members')
@role_required('trainer')
def trainer_class_members(id):
    user = db.session.get(User, session['user_id'])
    gym_class = GymClass.query.get_or_404(id)
    if gym_class.trainer_id != user.trainer.id:
        flash('Brak dostępu do tych zajęć.', 'danger')
        return redirect(url_for('trainer_schedule'))
    bookings = (Booking.query.filter_by(class_id=id, status='confirmed')
                .order_by(Booking.booked_at).all())
    return render_template('trainer/class_members.html',
                           gym_class=gym_class, bookings=bookings, today=date.today())


# ── Błędy ────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)
