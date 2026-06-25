from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from extensions import db
from models import User, GymClass, ClassSession, Booking, WaitlistEntry
from blueprints.utils import role_required
from services import (BookingService, WaitlistService, PaymentService,
                      MemberService, NotificationService, subscription_label,
                      month_label)
from constants import DAY_ORDER
from datetime import date, timedelta

bp = Blueprint('client', __name__, url_prefix='/client')


@bp.route('/')
@role_required('client')
def client_dashboard():
    from services import SubscriptionFactory
    user = db.session.get(User, session['user_id'])
    member = user.member
    subscription_active = MemberService.is_active(member)
    days_left = MemberService.days_left(member)
    NotificationService.notify_expiring(member, days_left)

    # nadchodzące sesje w tym tygodniu (najbliższe 7 dni)
    today = date.today()
    week_end = today + timedelta(days=7)
    upcoming = (Booking.query
                .filter_by(member_id=member.id, status='confirmed')
                .join(ClassSession)
                .filter(ClassSession.session_date >= today,
                        ClassSession.session_date <= week_end,
                        ClassSession.cancelled == False)
                .order_by(ClassSession.session_date)
                .all())

    prices = {s.code: s.price() for s in SubscriptionFactory.all_types()}
    return render_template('client/dashboard.html',
                           member=member,
                           upcoming=upcoming,
                           subscription_active=subscription_active,
                           days_left=days_left,
                           prices=prices,
                           today=today)


@bp.route('/classes')
@role_required('client')
def client_classes():
    from blueprints.sessions import refresh_all_future_sessions
    refresh_all_future_sessions()   # rolling-generacja: utrzymuje zapas przyszłych sesji

    user = db.session.get(User, session['user_id'])
    member = user.member
    today = date.today()

    classes = sorted(
        GymClass.query.filter_by(status='approved').all(),
        key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time)
    )

    # Dla każdych zajęć wyznacz najbliższe nadchodzące sesje (max 3)
    booked_session_ids = {b.session_id for b in Booking.query.filter_by(member_id=member.id, status='confirmed').all()}

    waitlist_session_ids = {
        w.session_id for w in WaitlistEntry.query.filter_by(member_id=member.id).all()
    }

    classes_data = []
    for c in classes:
        upcoming = [s for s in c.sessions if s.session_date >= today and not s.cancelled][:3]
        booking_counts = {
            s.id: Booking.query.filter_by(session_id=s.id, status='confirmed').count()
            for s in upcoming
        }
        waitlist_counts = {
            s.id: WaitlistEntry.query.filter_by(session_id=s.id).count()
            for s in upcoming
        }
        covered = {
            s.id: MemberService.is_active(member, s.session_date)
            for s in upcoming
        }
        classes_data.append({
            'class': c,
            'upcoming': upcoming,
            'booking_counts': booking_counts,
            'waitlist_counts': waitlist_counts,
            'covered': covered,
        })

    return render_template('client/classes.html',
                           classes_data=classes_data,
                           booked_session_ids=booked_session_ids,
                           waitlist_session_ids=waitlist_session_ids)


@bp.route('/sessions/<int:session_id>/book', methods=['POST'])
@role_required('client')
def client_book(session_id):
    user = db.session.get(User, session['user_id'])
    ok, msg = BookingService.book(user.member.id, session_id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client.client_bookings' if ok else 'client.client_classes'))


@bp.route('/sessions/<int:session_id>/waitlist', methods=['POST'])
@role_required('client')
def client_waitlist(session_id):
    user = db.session.get(User, session['user_id'])
    ok, msg = WaitlistService.join(user.member.id, session_id)
    flash(msg, 'info' if ok else 'warning')
    return redirect(url_for('client.client_classes'))


@bp.route('/sessions/<int:id>')
@role_required('client')
def client_session_detail(id):
    user = db.session.get(User, session['user_id'])
    member = user.member
    class_session = db.get_or_404(ClassSession, id)
    gym_class = class_session.gym_class

    confirmed = Booking.query.filter_by(session_id=id, status='confirmed').count()
    waitlist_count = WaitlistEntry.query.filter_by(session_id=id).count()
    is_booked = Booking.query.filter_by(
        member_id=member.id, session_id=id, status='confirmed').first() is not None
    on_waitlist = WaitlistEntry.query.filter_by(
        member_id=member.id, session_id=id).first() is not None

    return render_template('client/session_detail.html',
                           cs=class_session, gym_class=gym_class,
                           confirmed=confirmed, waitlist_count=waitlist_count,
                           is_booked=is_booked, on_waitlist=on_waitlist,
                           is_full=confirmed >= gym_class.max_capacity,
                           is_past=class_session.session_date < date.today(),
                           sub_covered=MemberService.is_active(member, class_session.session_date),
                           today=date.today())


@bp.route('/bookings')
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
    # 'all' → bez filtra statusu
    page = request.args.get('page', 1, type=int)
    pagination = (query.order_by(Booking.booked_at.desc())
                  .paginate(page=page, per_page=15, error_out=False))

    return render_template('client/bookings.html', member=member, pagination=pagination,
                           status_filter=status_filter, today=date.today())


@bp.route('/bookings/<int:id>/cancel', methods=['POST'])
@role_required('client')
def client_cancel(id):
    user = db.session.get(User, session['user_id'])
    ok, msg = BookingService.cancel(user.member.id, id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client.client_bookings'))


@bp.route('/attendance')
@role_required('client')
def client_attendance():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings = BookingService.past_attendance(member)
    stats = BookingService.attendance_summary(member)
    return render_template('client/attendance.html', member=member,
                           bookings=bookings, stats=stats)


@bp.route('/profile')
@role_required('client')
def client_profile():
    user = db.session.get(User, session['user_id'])
    member = user.member
    bookings_count = Booking.query.filter_by(member_id=member.id, status='confirmed').count()
    days_left = (member.subscription_end - date.today()).days if member.subscription_end else None
    return render_template('client/profile.html', member=member, today=date.today(),
                           bookings_count=bookings_count, days_left=days_left)


@bp.route('/profile/edit', methods=['POST'])
@role_required('client')
def client_profile_edit():
    user = db.session.get(User, session['user_id'])
    ok, msg = MemberService.update_profile(
        user.member,
        first_name=request.form.get('first_name'),
        last_name=request.form.get('last_name'),
        phone=request.form.get('phone'),
    )
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client.client_profile'))


# ── Płatności ─────────────────────────────────────────────────────────────────

@bp.route('/payments')
@role_required('client')
def client_payments():
    user = db.session.get(User, session['user_id'])
    member = user.member
    is_daypass = member.subscription_type == 'day_pass'
    periods = PaymentService.payable_periods(member, count=3)
    day_amount = PaymentService.amount_for(member) if is_daypass else None
    return render_template('client/payments.html', member=member, periods=periods,
                           is_daypass=is_daypass, day_amount=day_amount,
                           sub_label=subscription_label(member.subscription_type))


@bp.route('/payments/daypass', methods=['POST'])
@role_required('client')
def client_buy_daypass():
    user = db.session.get(User, session['user_id'])
    member = user.member
    if member.subscription_type != 'day_pass':
        flash('Wejściówka dotyczy tylko karnetu dziennego.', 'warning')
        return redirect(url_for('client.client_payments'))
    p = PaymentService.settle_next_period(member)
    flash(f'Wejściówka na dziś opłacona ({p["amount"]:.0f} zł).', 'success')
    return redirect(url_for('client.client_payments'))


@bp.route('/payments/initiate', methods=['POST'])
@role_required('client')
def client_payment_initiate():
    user = db.session.get(User, session['user_id'])
    member = user.member
    month_year = request.form.get('month_year', '')
    ok, data = PaymentService.initiate(member.id, month_year)
    if not ok:
        flash(data.get('error', 'Nie udało się rozpocząć płatności.'), 'danger')
        return redirect(url_for('client.client_payments'))
    return redirect(url_for('client.client_payment_pay', id=data['payment_id']))


@bp.route('/payments/<int:id>/pay')
@role_required('client')
def client_payment_pay(id):
    from models import Payment
    from services import BANK_ACCOUNT
    user = db.session.get(User, session['user_id'])
    payment = db.get_or_404(Payment, id)
    if payment.member_id != user.member.id:
        flash('Brak dostępu do tej płatności.', 'danger')
        return redirect(url_for('client.client_payments'))
    if payment.status == 'completed':
        flash('Ta płatność jest już opłacona.', 'info')
        return redirect(url_for('client.client_payments'))
    return render_template('client/payment_pay.html', payment=payment,
                           bank_account=BANK_ACCOUNT)


@bp.route('/payments/<int:id>/confirm', methods=['POST'])
@role_required('client')
def client_payment_confirm(id):
    user = db.session.get(User, session['user_id'])
    ok, msg = PaymentService.confirm(id, user.member.id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('client.client_payments'))


# ── Przedłużanie karnetu przez klienta ───────────────────────────────────────

@bp.route('/subscription/renew', methods=['POST'])
@role_required('client')
def client_subscription_renew():
    user = db.session.get(User, session['user_id'])
    member = user.member

    sub_type = request.form.get('subscription_type', member.subscription_type)
    if sub_type != member.subscription_type:
        member.subscription_type = sub_type
        db.session.commit()

    # Jeden mechanizm: „przedłuż" = opłać najbliższy okres (przedłuża ważność).
    period = PaymentService.settle_next_period(member)

    if member.subscription_type == 'day_pass':
        flash(f'Wejściówka na dziś opłacona ({period["amount"]:.0f} zł).', 'success')
    else:
        flash(f'Opłacono okres ({subscription_label(member.subscription_type)}, '
              f'{period["amount"]:.0f} zł) — karnet aktywny do końca '
              f'{month_label(member.subscription_end)}.', 'success')
    return redirect(url_for('client.client_dashboard'))
