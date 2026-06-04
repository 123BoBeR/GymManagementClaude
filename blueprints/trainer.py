from flask import Blueprint, render_template, session
from extensions import db
from models import User, Booking, GymClass
from blueprints.utils import role_required
from datetime import datetime, date

bp = Blueprint('trainer', __name__, url_prefix='/trainer')

DAY_ORDER = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']


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
    today_classes = [c for c in trainer.classes if c.schedule_day == today_pl]
    total_members = len({b.member_id for c in trainer.classes for b in c.bookings if b.status == 'confirmed'})
    return render_template('trainer/dashboard.html',
                           trainer=trainer,
                           today_classes=today_classes,
                           today_name=today_pl,
                           total_members=total_members)


@bp.route('/schedule')
@role_required('trainer')
def trainer_schedule():
    user = db.session.get(User, session['user_id'])
    trainer = user.trainer
    classes = sorted(trainer.classes,
                     key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count() for c in classes}
    return render_template('trainer/schedule.html', trainer=trainer, classes=classes, booking_counts=booking_counts)


@bp.route('/members')
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
