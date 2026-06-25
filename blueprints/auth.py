from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from extensions import db, limiter
from models import User, ContactOption
from services import UserService, SubscriptionFactory, NotificationService

bp = Blueprint('auth', __name__)


def _login_session(user):
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role


@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin.admin_dashboard'))
    elif role == 'trainer':
        return redirect(url_for('trainer.trainer_dashboard'))
    return redirect(url_for('client.client_dashboard'))


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            _login_session(user)
            return redirect(url_for('auth.index'))
        flash('Nieprawidłowa nazwa użytkownika lub hasło.', 'danger')
    return render_template('login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('auth.index'))
    if request.method == 'POST':
        ok, result = UserService.register_client(
            request.form.get('first_name', ''),
            request.form.get('last_name', ''),
            request.form.get('password', ''),
            request.form.get('phone', ''),
            request.form.get('subscription_type', 'monthly'),
        )
        if not ok:
            flash(result, 'danger')
            return render_template('register.html', sub_types=SubscriptionFactory.all_types())
        _login_session(result)
        flash(f'Konto utworzone! Twój login: {result.username}', 'success')
        return redirect(url_for('auth.index'))
    return render_template('register.html', sub_types=SubscriptionFactory.all_types())


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('auth.index'))
    reset_link = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        token = UserService.create_reset_token(username)
        if token:
            # Brak e-maila: w devie pokazujemy link wprost (w produkcji wysłany mailem).
            reset_link = url_for('auth.reset_password', token=token)
        # Komunikat jednakowy niezależnie od istnienia konta (anty-enumeracja).
        flash('Jeśli konto istnieje, link do zresetowania hasła jest gotowy.', 'info')
    return render_template('forgot_password.html', reset_link=reset_link)


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        ok, msg = UserService.reset_password_with_token(
            token,
            request.form.get('new_password', ''),
            request.form.get('confirm_password', ''),
        )
        flash(msg, 'success' if ok else 'danger')
        if ok:
            return redirect(url_for('auth.login'))
    return render_template('reset_password.html', token=token)


@bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session['user_id'])
    if request.method == 'POST':
        ok, msg = UserService.change_password(
            user,
            request.form.get('current_password', ''),
            request.form.get('new_password', ''),
            request.form.get('confirm_password', ''),
        )
        flash(msg, 'success' if ok else 'danger')
        if ok:
            return redirect(url_for('auth.index'))
    return render_template('change_password.html')


@bp.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    notes = NotificationService.for_user(session['user_id'])
    return render_template('notifications.html', notes=notes)


@bp.route('/notifications/read', methods=['POST'])
def notifications_read():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    NotificationService.mark_all_read(session['user_id'])
    return redirect(url_for('auth.notifications'))


@bp.route('/contact')
def contact():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    options = ContactOption.query.all()
    return render_template('contact.html', options=options)


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
