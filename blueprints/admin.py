from flask import Blueprint, render_template, redirect, url_for, request, flash
from extensions import db
from models import User, Member, Trainer, GymClass, ClassSession, Booking, Equipment
from blueprints.utils import role_required
from blueprints.sessions import generate_sessions
from datetime import datetime, date

bp = Blueprint('admin', __name__, url_prefix='/admin')

DAY_ORDER = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']


@bp.route('/')
@role_required('admin')
def admin_dashboard():
    stats = {
        'members': Member.query.count(),
        'trainers': Trainer.query.count(),
        'classes': GymClass.query.filter_by(status='approved').count(),
        'bookings': Booking.query.filter_by(status='confirmed').count(),
        'pending': GymClass.query.filter_by(status='pending').count(),
    }
    recent_bookings = Booking.query.order_by(Booking.booked_at.desc()).limit(8).all()
    return render_template('admin/dashboard.html', stats=stats, recent_bookings=recent_bookings)


# ── Członkowie ────────────────────────────────────────────────────────────────

@bp.route('/members')
@role_required('admin')
def admin_members():
    members = Member.query.all()
    return render_template('admin/members.html', members=members, today=date.today())


@bp.route('/members/new', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.admin_members'))
    return render_template('admin/member_form.html', member=None)


@bp.route('/members/<int:id>/edit', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.admin_members'))
    return render_template('admin/member_form.html', member=member)


@bp.route('/members/<int:id>/renew', methods=['POST'])
@role_required('admin')
def admin_member_renew(id):
    member = Member.query.get_or_404(id)
    member.subscription_type = request.form.get('subscription_type', member.subscription_type)
    sub_end_str = request.form.get('subscription_end', '')
    if sub_end_str:
        member.subscription_end = datetime.strptime(sub_end_str, '%Y-%m-%d').date()
    db.session.commit()
    flash(f'Karnet dla {member.first_name} {member.last_name} zaktualizowany do {member.subscription_end.strftime("%d.%m.%Y")}.', 'success')
    return redirect(url_for('admin.admin_members'))


@bp.route('/members/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_member_delete(id):
    member = Member.query.get_or_404(id)
    db.session.delete(member.user)
    db.session.commit()
    flash('Klient usunięty.', 'success')
    return redirect(url_for('admin.admin_members'))


# ── Trenerzy ──────────────────────────────────────────────────────────────────

@bp.route('/trainers')
@role_required('admin')
def admin_trainers():
    trainers = Trainer.query.all()
    return render_template('admin/trainers.html', trainers=trainers)


@bp.route('/trainers/<int:id>/edit', methods=['POST'])
@role_required('admin')
def admin_trainer_edit(id):
    trainer = Trainer.query.get_or_404(id)
    trainer.first_name = request.form.get('first_name', trainer.first_name).strip()
    trainer.last_name = request.form.get('last_name', trainer.last_name).strip()
    trainer.specialization = request.form.get('specialization', trainer.specialization).strip()
    rate_str = request.form.get('hourly_rate', '').strip()
    if rate_str:
        try:
            trainer.hourly_rate = float(rate_str)
        except ValueError:
            pass
    db.session.commit()
    flash(f'Dane trenera {trainer.first_name} {trainer.last_name} zaktualizowane.', 'success')
    return redirect(url_for('admin.admin_trainers'))


# ── Zajęcia ───────────────────────────────────────────────────────────────────

@bp.route('/classes')
@role_required('admin')
def admin_classes():
    pending = GymClass.query.filter_by(status='pending').order_by(GymClass.id.desc()).all()
    approved = sorted(
        GymClass.query.filter_by(status='approved').all(),
        key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time)
    )
    rejected = GymClass.query.filter_by(status='rejected').order_by(GymClass.id.desc()).all()

    def booking_count(c):
        return (Booking.query
                .join(ClassSession)
                .filter(ClassSession.class_id == c.id, Booking.status == 'confirmed')
                .count())

    booking_counts = {c.id: booking_count(c) for c in approved}
    return render_template('admin/classes.html',
                           pending=pending, approved=approved, rejected=rejected,
                           booking_counts=booking_counts)


@bp.route('/classes/<int:id>/approve', methods=['POST'])
@role_required('admin')
def admin_class_approve(id):
    gym_class = GymClass.query.get_or_404(id)
    gym_class.status = 'approved'
    gym_class.rejection_note = None
    sessions = generate_sessions(gym_class, weeks=12)
    for s in sessions:
        db.session.add(s)
    db.session.commit()
    flash(f'Zajęcia "{gym_class.name}" zatwierdzone. Wygenerowano {len(sessions)} sesji.', 'success')
    return redirect(url_for('admin.admin_classes'))


@bp.route('/classes/<int:id>/reject', methods=['POST'])
@role_required('admin')
def admin_class_reject(id):
    gym_class = GymClass.query.get_or_404(id)
    gym_class.status = 'rejected'
    gym_class.rejection_note = request.form.get('rejection_note', '').strip()
    db.session.commit()
    flash(f'Zajęcia "{gym_class.name}" odrzucone.', 'warning')
    return redirect(url_for('admin.admin_classes'))


@bp.route('/classes/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_class_delete(id):
    gym_class = GymClass.query.get_or_404(id)
    db.session.delete(gym_class)
    db.session.commit()
    flash('Zajęcia usunięte.', 'success')
    return redirect(url_for('admin.admin_classes'))


# ── Sprzęt ────────────────────────────────────────────────────────────────────

@bp.route('/equipment')
@role_required('admin')
def admin_equipment():
    equipment = Equipment.query.all()
    return render_template('admin/equipment.html', equipment=equipment)
