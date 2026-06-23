from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from extensions import db
from models import User, GymClass, ClassSession, Booking
from blueprints.utils import role_required
from datetime import datetime, date, timedelta

bp = Blueprint('trainer', __name__, url_prefix='/trainer')

DAY_ORDER = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']
DAYS = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']


@bp.route('/')
@role_required('trainer')
def trainer_dashboard():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    days_pl = {
        'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa',
        'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Saturday': 'Sobota', 'Sunday': 'Niedziela',
    }
    today_pl = days_pl.get(datetime.now().strftime('%A'), '')
    approved_classes = [c for c in trainer.classes if c.status == 'approved']
    today_classes = [c for c in approved_classes if c.schedule_day == today_pl]

    total_members = len({
        b.member_id
        for c in approved_classes
        for s in c.sessions
        for b in s.bookings
        if b.status == 'confirmed'
    })
    pending_count = sum(1 for c in trainer.classes if c.status == 'pending')

    return render_template('trainer/dashboard.html',
                           trainer=trainer,
                           today_classes=today_classes,
                           today_name=today_pl,
                           total_members=total_members,
                           pending_count=pending_count)


@bp.route('/schedule')
@role_required('trainer')
def trainer_schedule():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    approved = sorted(
        [c for c in trainer.classes if c.status == 'approved'],
        key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time)
    )
    pending = [c for c in trainer.classes if c.status == 'pending']
    rejected = [c for c in trainer.classes if c.status == 'rejected']

    def booking_count(c):
        return (Booking.query
                .join(ClassSession)
                .filter(ClassSession.class_id == c.id, Booking.status == 'confirmed')
                .count())

    booking_counts = {c.id: booking_count(c) for c in approved}
    return render_template('trainer/schedule.html',
                           trainer=trainer,
                           approved=approved,
                           pending=pending,
                           rejected=rejected,
                           booking_counts=booking_counts)


@bp.route('/classes/propose', methods=['GET', 'POST'])
@role_required('trainer')
def trainer_propose_class():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer

    if request.method == 'POST':
        start_date_str = request.form.get('start_date', '')
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Nieprawidłowa data startu.', 'danger')
            return render_template('trainer/class_propose.html', trainer=trainer, days=DAYS)

        gym_class = GymClass(
            trainer_id=trainer.id,
            name=request.form.get('name', '').strip(),
            description=request.form.get('description', '').strip(),
            max_capacity=int(request.form.get('max_capacity', 10)),
            schedule_day=request.form.get('schedule_day', ''),
            schedule_time=request.form.get('schedule_time', ''),
            duration_minutes=int(request.form.get('duration_minutes', 60)),
            frequency_weeks=int(request.form.get('frequency_weeks', 1)),
            start_date=start_date,
            status='pending',
        )
        db.session.add(gym_class)
        db.session.commit()
        flash('Propozycja zajęć wysłana do zatwierdzenia przez administratora.', 'success')
        return redirect(url_for('trainer.trainer_schedule'))

    return render_template('trainer/class_propose.html', trainer=trainer, days=DAYS)


@bp.route('/sessions')
@role_required('trainer')
def trainer_sessions():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    today = date.today()
    week_ago = today - timedelta(days=7)

    # Sesje z ostatniego tygodnia + nadchodzące 14 dni
    upcoming_sessions = (
        ClassSession.query
        .join(GymClass)
        .filter(
            GymClass.trainer_id == trainer.id,
            GymClass.status == 'approved',
            ClassSession.session_date >= week_ago,
            ClassSession.session_date <= today + timedelta(days=14),
            ClassSession.cancelled == False,
        )
        .order_by(ClassSession.session_date)
        .all()
    )
    return render_template('trainer/sessions.html', trainer=trainer,
                           sessions=upcoming_sessions, today=today)


@bp.route('/sessions/<int:session_id>/attendance', methods=['GET', 'POST'])
@role_required('trainer')
def trainer_attendance(session_id):
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    class_session = db.get_or_404(ClassSession, session_id)

    if class_session.gym_class.trainer_id != trainer.id:
        flash('Brak dostępu do tej sesji.', 'danger')
        return redirect(url_for('trainer.trainer_sessions'))

    if request.method == 'POST':
        bookings = Booking.query.filter_by(session_id=session_id, status='confirmed').all()
        for b in bookings:
            val = request.form.get(f'attended_{b.id}')
            if val == '1':
                b.attended = True
            elif val == '0':
                b.attended = False
            else:
                b.attended = None
        db.session.commit()
        flash('Obecność zapisana.', 'success')
        return redirect(url_for('trainer.trainer_sessions'))

    bookings = Booking.query.filter_by(session_id=session_id, status='confirmed').all()
    return render_template('trainer/attendance.html', trainer=trainer,
                           class_session=class_session, bookings=bookings)


@bp.route('/classes/<int:id>/edit', methods=['GET', 'POST'])
@role_required('trainer')
def trainer_class_edit(id):
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    gym_class = db.get_or_404(GymClass, id)

    if gym_class.trainer_id != trainer.id:
        flash('Brak dostępu do tych zajęć.', 'danger')
        return redirect(url_for('trainer.trainer_schedule'))

    if gym_class.status == 'approved':
        flash('Nie można edytować zatwierdzonych zajęć - skontaktuj się z administratorem.', 'warning')
        return redirect(url_for('trainer.trainer_schedule'))

    if request.method == 'POST':
        gym_class.name = request.form.get('name', gym_class.name).strip()
        gym_class.description = request.form.get('description', gym_class.description).strip()
        gym_class.max_capacity = int(request.form.get('max_capacity', gym_class.max_capacity))
        gym_class.schedule_day = request.form.get('schedule_day', gym_class.schedule_day)
        gym_class.schedule_time = request.form.get('schedule_time', gym_class.schedule_time)
        gym_class.duration_minutes = int(request.form.get('duration_minutes', gym_class.duration_minutes))
        gym_class.frequency_weeks = int(request.form.get('frequency_weeks', gym_class.frequency_weeks))
        start_date_str = request.form.get('start_date', '')
        if start_date_str:
            gym_class.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        # Cofnij odrzucenie jeśli trener poprawił i ponownie wysyła
        if gym_class.status == 'rejected':
            gym_class.status = 'pending'
            gym_class.rejection_note = None
            flash('Zajęcia zaktualizowane i ponownie wysłane do zatwierdzenia.', 'success')
        else:
            flash('Propozycja zaktualizowana.', 'success')
        db.session.commit()
        return redirect(url_for('trainer.trainer_schedule'))

    return render_template('trainer/class_propose.html', trainer=trainer, days=DAYS, edit=gym_class)


@bp.route('/classes/<int:id>/members')
@role_required('trainer')
def trainer_class_members(id):
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    gym_class = db.get_or_404(GymClass, id)
    if gym_class.trainer_id != trainer.id:
        flash('Brak dostępu do tych zajęć.', 'danger')
        return redirect(url_for('trainer.trainer_schedule'))

    rows = {}
    for s in gym_class.sessions:
        for b in s.bookings:
            if b.status != 'confirmed':
                continue
            entry = rows.setdefault(b.member_id, {
                'member': b.member, 'sessions': 0, 'attended': 0,
            })
            entry['sessions'] += 1
            if b.attended:
                entry['attended'] += 1
    participants = sorted(rows.values(),
                          key=lambda r: (r['member'].last_name, r['member'].first_name))
    return render_template('trainer/class_members.html', trainer=trainer,
                           gym_class=gym_class, participants=participants,
                           today=date.today())


@bp.route('/profile', methods=['GET', 'POST'])
@role_required('trainer')
def trainer_profile():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer

    if request.method == 'POST':
        trainer.specialization = request.form.get('specialization', trainer.specialization).strip()
        rate_str = request.form.get('hourly_rate', '').strip()
        if rate_str:
            try:
                trainer.hourly_rate = float(rate_str.replace(',', '.'))
            except ValueError:
                flash('Nieprawidłowa stawka godzinowa.', 'danger')
                return redirect(url_for('trainer.trainer_profile'))
        db.session.commit()
        flash('Profil zaktualizowany.', 'success')
        return redirect(url_for('trainer.trainer_profile'))

    approved = [c for c in trainer.classes if c.status == 'approved']
    total_members = len({
        b.member_id for c in approved for s in c.sessions
        for b in s.bookings if b.status == 'confirmed'
    })
    return render_template('trainer/profile.html', trainer=trainer,
                           classes_count=len(approved), total_members=total_members)


@bp.route('/members')
@role_required('trainer')
def trainer_members():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    members_dict = {}
    for c in trainer.classes:
        if c.status != 'approved':
            continue
        for s in c.sessions:
            for b in s.bookings:
                if b.status == 'confirmed':
                    if b.member_id not in members_dict:
                        members_dict[b.member_id] = {'member': b.member, 'classes': []}
                    if c.name not in members_dict[b.member_id]['classes']:
                        members_dict[b.member_id]['classes'].append(c.name)
    return render_template('trainer/members.html', trainer=trainer,
                           members_data=list(members_dict.values()), today=date.today())
