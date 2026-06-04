from flask import Blueprint, render_template, redirect, url_for, request, flash
from extensions import db
from models import User, Member, Trainer, GymClass, Booking, Equipment
from blueprints.utils import role_required
from datetime import datetime, date

bp = Blueprint('admin', __name__, url_prefix='/admin')

DAY_ORDER = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']


@bp.route('/')
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


@bp.route('/members/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_member_delete(id):
    member = Member.query.get_or_404(id)
    db.session.delete(member.user)
    db.session.commit()
    flash('Klient usunięty.', 'success')
    return redirect(url_for('admin.admin_members'))


@bp.route('/trainers')
@role_required('admin')
def admin_trainers():
    trainers = Trainer.query.all()
    return render_template('admin/trainers.html', trainers=trainers)


@bp.route('/classes')
@role_required('admin')
def admin_classes():
    classes = sorted(GymClass.query.all(),
                     key=lambda c: (DAY_ORDER.index(c.schedule_day) if c.schedule_day in DAY_ORDER else 99, c.schedule_time))
    trainers = Trainer.query.all()
    booking_counts = {c.id: Booking.query.filter_by(class_id=c.id, status='confirmed').count() for c in classes}
    return render_template('admin/classes.html', classes=classes, trainers=trainers, booking_counts=booking_counts)


@bp.route('/classes/new', methods=['POST'])
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
    return redirect(url_for('admin.admin_classes'))


@bp.route('/classes/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_class_delete(id):
    gym_class = GymClass.query.get_or_404(id)
    db.session.delete(gym_class)
    db.session.commit()
    flash('Zajęcia usunięte.', 'success')
    return redirect(url_for('admin.admin_classes'))


@bp.route('/equipment')
@role_required('admin')
def admin_equipment():
    equipment = Equipment.query.all()
    return render_template('admin/equipment.html', equipment=equipment)
