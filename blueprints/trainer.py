from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from extensions import db
from models import User, GymClass, ClassSession, Booking
from blueprints.utils import role_required
from datetime import datetime, date

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
