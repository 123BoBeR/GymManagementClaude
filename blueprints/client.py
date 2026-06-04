from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from extensions import db
from models import User, GymClass, ClassSession, Booking
from blueprints.utils import role_required
from datetime import date

bp = Blueprint('client', __name__, url_prefix='/client')

DAY_ORDER = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']


@bp.route('/')
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


@bp.route('/classes')
@role_required('client')
def client_classes():
    user = db.session.get(User, session['user_id'])
    member = user.member
    today = date.today()

    classes = sorted(
        GymClass.query.filter_by(status='approved').all(),
        key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time)
    )

    # Dla każdych zajęć wyznacz najbliższe nadchodzące sesje (max 3)
    booked_session_ids = {b.session_id for b in Booking.query.filter_by(member_id=member.id, status='confirmed').all()}

    classes_data = []
    for c in classes:
        upcoming = [s for s in c.sessions if s.session_date >= today and not s.cancelled][:3]
        booking_counts = {
            s.id: Booking.query.filter_by(session_id=s.id, status='confirmed').count()
            for s in upcoming
        }
        classes_data.append({
            'class': c,
            'upcoming': upcoming,
            'booking_counts': booking_counts,
        })

    return render_template('client/classes.html',
                           classes_data=classes_data,
                           booked_session_ids=booked_session_ids)


@bp.route('/sessions/<int:session_id>/book', methods=['POST'])
@role_required('client')
def client_book(session_id):
    user = db.session.get(User, session['user_id'])
    member = user.member
    class_session = ClassSession.query.get_or_404(session_id)
    gym_class = class_session.gym_class

    if class_session.cancelled:
        flash('Ta sesja została odwołana.', 'danger')
        return redirect(url_for('client.client_classes'))

    if class_session.session_date < date.today():
        flash('Nie można rezerwować przeszłych sesji.', 'danger')
        return redirect(url_for('client.client_classes'))

    confirmed = Booking.query.filter_by(session_id=session_id, status='confirmed').count()
    if confirmed >= gym_class.max_capacity:
        flash('Brak wolnych miejsc na tę sesję.', 'danger')
        return redirect(url_for('client.client_classes'))

    if Booking.query.filter_by(member_id=member.id, session_id=session_id, status='confirmed').first():
        flash('Jesteś już zapisany na tę sesję.', 'warning')
        return redirect(url_for('client.client_classes'))

    # Sprawdź konflikt terminów
    def to_minutes(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    new_start = to_minutes(gym_class.schedule_time)
    new_end = new_start + gym_class.duration_minutes

    conflicting = (Booking.query
                   .filter_by(member_id=member.id, status='confirmed')
                   .join(ClassSession)
                   .filter(ClassSession.session_date == class_session.session_date)
                   .join(GymClass, ClassSession.class_id == GymClass.id)
                   .filter(GymClass.schedule_day == gym_class.schedule_day)
                   .all())
    for b in conflicting:
        ex_start = to_minutes(b.gym_class.schedule_time)
        ex_end = ex_start + b.gym_class.duration_minutes
        if new_start < ex_end and ex_start < new_end:
            flash(
                f'Konflikt terminów: "{b.gym_class.name}" '
                f'({b.gym_class.schedule_day}, {b.gym_class.schedule_time}) '
                f'pokrywa się z wybranymi zajęciami.',
                'danger'
            )
            return redirect(url_for('client.client_classes'))

    db.session.add(Booking(member_id=member.id, session_id=session_id, status='confirmed'))
    db.session.commit()
    flash(f'Zapisano na: {gym_class.name} ({class_session.session_date.strftime("%d.%m.%Y")})!', 'success')
    return redirect(url_for('client.client_bookings'))


@bp.route('/bookings')
@role_required('client')
def client_bookings():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings = Booking.query.filter_by(member_id=member.id).order_by(Booking.booked_at.desc()).all()
    return render_template('client/bookings.html', member=member, bookings=bookings, today=date.today())


@bp.route('/bookings/<int:id>/cancel', methods=['POST'])
@role_required('client')
def client_cancel(id):
    booking = Booking.query.get_or_404(id)
    user = db.session.get(User, session['user_id'])
    if booking.member_id != user.member.id:
        flash('Brak dostępu.', 'danger')
        return redirect(url_for('client.client_bookings'))
    booking.status = 'cancelled'
    db.session.commit()
    flash('Rezerwacja anulowana.', 'success')
    return redirect(url_for('client.client_bookings'))


@bp.route('/profile')
@role_required('client')
def client_profile():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings_count = Booking.query.filter_by(member_id=member.id, status='confirmed').count()
    days_left = (member.subscription_end - date.today()).days if member.subscription_end else None
    return render_template('client/profile.html', member=member, today=date.today(),
                           bookings_count=bookings_count, days_left=days_left)
