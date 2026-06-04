from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from extensions import db
from models import User, GymClass, Booking
from blueprints.utils import role_required
from datetime import datetime, date, timedelta

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
    classes = sorted(GymClass.query.all(),
                     key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    booked_ids = {b.class_id for b in Booking.query.filter_by(member_id=member.id, status='confirmed').all()}
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count() for c in classes}
    return render_template('client/classes.html', classes=classes, booked_ids=booked_ids, booking_counts=booking_counts)


@bp.route('/classes/<int:id>/book', methods=['POST'])
@role_required('client')
def client_book(id):
    user = db.session.get(User, session['user_id'])
    member = user.member
    gym_class = GymClass.query.get_or_404(id)

    confirmed = Booking.query.filter_by(class_id=id, status='confirmed').count()
    if confirmed >= gym_class.max_capacity:
        flash('Brak wolnych miejsc na te zajęcia.', 'danger')
        return redirect(url_for('client.client_classes'))

    if Booking.query.filter_by(member_id=member.id, class_id=id, status='confirmed').first():
        flash('Jesteś już zapisany na te zajęcia.', 'warning')
        return redirect(url_for('client.client_classes'))

    def to_minutes(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    new_start = to_minutes(gym_class.schedule_time)
    new_end = new_start + gym_class.duration_minutes

    existing_bookings = (Booking.query
                         .filter_by(member_id=member.id, status='confirmed')
                         .join(GymClass)
                         .filter(GymClass.schedule_day == gym_class.schedule_day)
                         .all())
    for b in existing_bookings:
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

    db.session.add(Booking(member_id=member.id, class_id=id, status='confirmed'))
    db.session.commit()
    flash(f'Zapisano na: {gym_class.name}!', 'success')
    return redirect(url_for('client.client_bookings'))


@bp.route('/bookings')
@role_required('client')
def client_bookings():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings = Booking.query.filter_by(member_id=member.id).order_by(Booking.booked_at.desc()).all()
    return render_template('client/bookings.html', member=member, bookings=bookings)


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
