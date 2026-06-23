import csv
import io
from flask import Blueprint, render_template, redirect, url_for, request, flash, Response
from extensions import db
from models import User, Member, Trainer, GymClass, ClassSession, Booking, Equipment, Payment, WaitlistEntry
from blueprints.utils import role_required
from blueprints.sessions import generate_sessions
from services import PaymentService
from datetime import datetime, date, timedelta
from collections import defaultdict

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
    equipment_issues = Equipment.query.filter(
        Equipment.status.in_(['broken', 'maintenance'])
    ).all()

    # ── Dane do wykresów ──────────────────────────────────────────────────────
    today = date.today()

    # 1) Przychód z ostatnich 6 miesięcy (opłacone płatności)
    rev_labels, rev_data = [], []
    year, month = today.year, today.month
    months_seq = []
    for _ in range(6):
        months_seq.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    for y, m in reversed(months_seq):
        my = f"{y:04d}-{m:02d}"
        total = sum(p.amount for p in Payment.query.filter_by(
            month_year=my, status='completed').all())
        rev_labels.append(my)
        rev_data.append(total)

    # 2) Podział karnetów
    sub_counts = {
        'Miesięczny': Member.query.filter_by(subscription_type='monthly').count(),
        'Roczny': Member.query.filter_by(subscription_type='annual').count(),
        'Dzienny': Member.query.filter_by(subscription_type='day_pass').count(),
    }

    # 3) Top 5 zajęć wg potwierdzonych rezerwacji
    ranking = []
    for c in GymClass.query.filter_by(status='approved').all():
        cnt = (Booking.query.join(ClassSession)
               .filter(ClassSession.class_id == c.id, Booking.status == 'confirmed')
               .count())
        if cnt:
            ranking.append((c.name, cnt))
    ranking.sort(key=lambda x: x[1], reverse=True)
    top = ranking[:5]

    charts = {
        'revenue_labels': rev_labels,
        'revenue_data': rev_data,
        'sub_labels': list(sub_counts.keys()),
        'sub_data': list(sub_counts.values()),
        'top_labels': [t[0] for t in top],
        'top_data': [t[1] for t in top],
    }
    return render_template('admin/dashboard.html', stats=stats,
                           recent_bookings=recent_bookings,
                           equipment_issues=equipment_issues,
                           charts=charts)


# ── Członkowie ────────────────────────────────────────────────────────────────

@bp.route('/members/export')
@role_required('admin')
def admin_members_export():
    members = Member.query.order_by(Member.last_name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Imię', 'Nazwisko', 'Login', 'Telefon',
                     'Karnet', 'Ważny do', 'Status', 'Data dołączenia'])
    sub_labels = {'monthly': 'Miesięczny', 'annual': 'Roczny', 'day_pass': 'Dzienny'}
    today = date.today()
    for m in members:
        status = 'Aktywny' if m.subscription_end and m.subscription_end >= today else 'Wygasły'
        writer.writerow([
            m.id,
            m.first_name,
            m.last_name,
            m.user.username,
            m.phone or '',
            sub_labels.get(m.subscription_type, m.subscription_type),
            m.subscription_end.strftime('%d.%m.%Y') if m.subscription_end else '',
            status,
            m.joined_at.strftime('%d.%m.%Y') if m.joined_at else '',
        ])
    output.seek(0)
    return Response(
        output.getvalue().encode('utf-8-sig'),  # utf-8-sig = BOM dla Excela
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=czlonkowie_{today}.csv'},
    )


@bp.route('/members')
@role_required('admin')
def admin_members():
    members = Member.query.all()
    return render_template('admin/members.html', members=members, today=date.today())


@bp.route('/members/<int:id>/payments')
@role_required('admin')
def admin_member_payments(id):
    member = db.get_or_404(Member, id)
    payments = (Payment.query.filter_by(member_id=member.id)
                .order_by(Payment.month_year.desc()).all())
    paid = [p for p in payments if p.status == 'completed']
    stats = {
        'paid_count': len(paid),
        'pending_count': len(payments) - len(paid),
        'total': sum(p.amount for p in paid),
    }
    return render_template('admin/member_payments.html', member=member,
                           payments=payments, stats=stats)


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
    member = db.get_or_404(Member, id)
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


@bp.route('/members/<int:id>/reset-password', methods=['POST'])
@role_required('admin')
def admin_member_reset_password(id):
    member = db.get_or_404(Member, id)
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('Hasło musi mieć co najmniej 6 znaków.', 'danger')
        return redirect(url_for('admin.admin_members'))
    member.user.set_password(new_password)
    db.session.commit()
    flash(f'Hasło dla {member.first_name} {member.last_name} zostało zresetowane.', 'success')
    return redirect(url_for('admin.admin_members'))


@bp.route('/members/<int:id>/renew', methods=['POST'])
@role_required('admin')
def admin_member_renew(id):
    member = db.get_or_404(Member, id)
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
    member = db.get_or_404(Member, id)
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


@bp.route('/trainers/new', methods=['POST'])
@role_required('admin')
def admin_trainer_new():
    username = request.form.get('username', '').strip()
    if not username:
        flash('Nazwa użytkownika jest wymagana.', 'danger')
        return redirect(url_for('admin.admin_trainers'))
    if User.query.filter_by(username=username).first():
        flash('Nazwa użytkownika już istnieje.', 'danger')
        return redirect(url_for('admin.admin_trainers'))

    password = request.form.get('password', '')
    if len(password) < 6:
        flash('Hasło musi mieć co najmniej 6 znaków.', 'danger')
        return redirect(url_for('admin.admin_trainers'))

    user = User(username=username, role='trainer')
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    rate_str = request.form.get('hourly_rate', '').strip()
    try:
        hourly_rate = float(rate_str.replace(',', '.')) if rate_str else None
    except ValueError:
        hourly_rate = None

    trainer = Trainer(
        user_id=user.id,
        first_name=request.form.get('first_name', '').strip(),
        last_name=request.form.get('last_name', '').strip(),
        specialization=request.form.get('specialization', '').strip(),
        hourly_rate=hourly_rate,
    )
    db.session.add(trainer)
    db.session.commit()
    flash(f'Trener {trainer.first_name} {trainer.last_name} dodany.', 'success')
    return redirect(url_for('admin.admin_trainers'))


@bp.route('/trainers/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_trainer_delete(id):
    trainer = db.get_or_404(Trainer, id)
    if trainer.classes:
        flash(f'Nie można usunąć — trener ma przypisane zajęcia ({len(trainer.classes)}). '
              f'Najpierw usuń lub przenieś zajęcia.', 'warning')
        return redirect(url_for('admin.admin_trainers'))
    name = f'{trainer.first_name} {trainer.last_name}'
    db.session.delete(trainer.user)   # cascade usuwa profil trenera
    db.session.commit()
    flash(f'Trener {name} usunięty.', 'success')
    return redirect(url_for('admin.admin_trainers'))


@bp.route('/trainers/<int:id>/edit', methods=['POST'])
@role_required('admin')
def admin_trainer_edit(id):
    trainer = db.get_or_404(Trainer, id)
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


@bp.route('/classes/<int:id>/members')
@role_required('admin')
def admin_class_members(id):
    gym_class = db.get_or_404(GymClass, id)
    # zbierz unikalnych członków z potwierdzonymi rezerwacjami w sesjach tych zajęć
    rows = {}
    for s in gym_class.sessions:
        for b in s.bookings:
            if b.status != 'confirmed':
                continue
            entry = rows.setdefault(b.member_id, {'member': b.member, 'sessions': 0})
            entry['sessions'] += 1
    participants = sorted(rows.values(),
                          key=lambda r: (r['member'].last_name, r['member'].first_name))
    total_confirmed = sum(r['sessions'] for r in participants)
    return render_template('admin/class_members.html', gym_class=gym_class,
                           participants=participants, total_confirmed=total_confirmed,
                           today=date.today())


@bp.route('/classes/<int:id>/approve', methods=['POST'])
@role_required('admin')
def admin_class_approve(id):
    gym_class = db.get_or_404(GymClass, id)
    if gym_class.status == 'approved':
        flash(f'Zajęcia "{gym_class.name}" są już zatwierdzone.', 'warning')
        return redirect(url_for('admin.admin_classes'))
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
    gym_class = db.get_or_404(GymClass, id)
    gym_class.status = 'rejected'
    gym_class.rejection_note = request.form.get('rejection_note', '').strip()
    db.session.commit()
    flash(f'Zajęcia "{gym_class.name}" odrzucone.', 'warning')
    return redirect(url_for('admin.admin_classes'))


@bp.route('/classes/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_class_delete(id):
    gym_class = db.get_or_404(GymClass, id)
    db.session.delete(gym_class)
    db.session.commit()
    flash('Zajęcia usunięte.', 'success')
    return redirect(url_for('admin.admin_classes'))


# ── Raporty ──────────────────────────────────────────────────────────────────

@bp.route('/reports')
@role_required('admin')
def admin_reports():
    today = date.today()
    # Ostatnie 8 tygodni
    weeks = 8
    week_starts = [today - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]

    # Obłożenie tygodniowe - liczba potwierdzonych rezerwacji per tydzień
    occupancy_labels = [f"{w.strftime('%d.%m')}" for w in week_starts]
    occupancy_data = []
    for w in week_starts:
        week_end = w + timedelta(days=6)
        count = (Booking.query
                 .join(ClassSession)
                 .filter(
                     ClassSession.session_date >= w,
                     ClassSession.session_date <= week_end,
                     Booking.status == 'confirmed',
                 ).count())
        occupancy_data.append(count)

    # Ranking zajęć - łączna liczba potwierdzeń
    ranking = []
    for c in GymClass.query.filter_by(status='approved').all():
        total = (Booking.query
                 .join(ClassSession)
                 .filter(ClassSession.class_id == c.id, Booking.status == 'confirmed')
                 .count())
        capacity = sum(1 for s in c.sessions) * c.max_capacity or 1
        booked = sum(
            Booking.query.filter_by(session_id=s.id, status='confirmed').count()
            for s in c.sessions
        )
        fill_pct = round(booked / capacity * 100) if capacity else 0
        ranking.append({
            'name': c.name,
            'trainer': f"{c.trainer.first_name} {c.trainer.last_name}",
            'total_bookings': total,
            'sessions_count': len(c.sessions),
            'fill_pct': fill_pct,
        })
    ranking.sort(key=lambda x: x['total_bookings'], reverse=True)

    return render_template('admin/reports.html',
                           occupancy_labels=occupancy_labels,
                           occupancy_data=occupancy_data,
                           ranking=ranking)


# ── Kolejka oczekujących ──────────────────────────────────────────────────────

@bp.route('/waitlist')
@role_required('admin')
def admin_waitlist():
    # pogrupuj wpisy wg sesji, z pozycją wg kolejności dodania
    entries = WaitlistEntry.query.order_by(WaitlistEntry.added_at).all()
    groups = {}
    for e in entries:
        groups.setdefault(e.session_id, []).append(e)

    rows = []
    for session_id, items in groups.items():
        cs = db.session.get(ClassSession, session_id)
        if cs is None:
            continue
        for pos, e in enumerate(items, start=1):
            rows.append({
                'class_name': cs.gym_class.name,
                'session_date': cs.session_date,
                'schedule_time': cs.gym_class.schedule_time,
                'member': e.member,
                'position': pos,
                'added_at': e.added_at,
            })
    rows.sort(key=lambda r: (r['session_date'], r['schedule_time'], r['position']))
    return render_template('admin/waitlist.html', rows=rows)


# ── Płatności ─────────────────────────────────────────────────────────────────

@bp.route('/payments/export')
@role_required('admin')
def admin_payments_export():
    members = {m.id: m for m in Member.query.all()}
    payments = Payment.query.order_by(Payment.month_year.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Klient', 'Miesiąc', 'Kwota', 'Status',
                     'Numer przelewu', 'Opłacono'])
    status_labels = {'completed': 'Opłacone', 'pending': 'Oczekuje'}
    for p in payments:
        m = members.get(p.member_id)
        writer.writerow([
            p.id,
            f'{m.first_name} {m.last_name}' if m else '—',
            p.month_year,
            f'{p.amount:.2f}',
            status_labels.get(p.status, p.status),
            p.transfer_number or '',
            p.paid_at.strftime('%d.%m.%Y %H:%M') if p.paid_at else '',
        ])
    output.seek(0)
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=platnosci_{date.today()}.csv'},
    )


@bp.route('/payments')
@role_required('admin')
def admin_payments():
    payments = (Payment.query
                .order_by(Payment.status, Payment.month_year.desc())
                .all())
    completed = [p for p in payments if p.status == 'completed']
    stats = {
        'total_revenue': sum(p.amount for p in completed),
        'completed_count': len(completed),
        'pending_count': len(payments) - len(completed),
    }
    # mapowanie member_id -> member dla wyświetlenia nazwiska
    members = {m.id: m for m in Member.query.all()}
    return render_template('admin/payments.html', payments=payments,
                           stats=stats, members=members)


# ── Sprzęt ────────────────────────────────────────────────────────────────────

@bp.route('/equipment')
@role_required('admin')
def admin_equipment():
    equipment = Equipment.query.all()
    return render_template('admin/equipment.html', equipment=equipment)


@bp.route('/equipment/new', methods=['POST'])
@role_required('admin')
def admin_equipment_new():
    purchase_date_str = request.form.get('purchase_date', '')
    purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date() if purchase_date_str else None
    equip = Equipment(
        name=request.form.get('name', '').strip(),
        category=request.form.get('category', '').strip(),
        status=request.form.get('status', 'working'),
        purchase_date=purchase_date,
    )
    db.session.add(equip)
    db.session.commit()
    flash(f'Sprzęt "{equip.name}" dodany.', 'success')
    return redirect(url_for('admin.admin_equipment'))


@bp.route('/equipment/<int:id>/edit', methods=['POST'])
@role_required('admin')
def admin_equipment_edit(id):
    equip = db.get_or_404(Equipment, id)
    equip.name = request.form.get('name', equip.name).strip()
    equip.category = request.form.get('category', equip.category).strip()
    equip.status = request.form.get('status', equip.status)
    purchase_date_str = request.form.get('purchase_date', '')
    if purchase_date_str:
        equip.purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
    db.session.commit()
    flash(f'Sprzęt "{equip.name}" zaktualizowany.', 'success')
    return redirect(url_for('admin.admin_equipment'))


@bp.route('/equipment/<int:id>/delete', methods=['POST'])
@role_required('admin')
def admin_equipment_delete(id):
    equip = db.get_or_404(Equipment, id)
    name = equip.name
    db.session.delete(equip)
    db.session.commit()
    flash(f'Sprzęt "{name}" usunięty.', 'success')
    return redirect(url_for('admin.admin_equipment'))
