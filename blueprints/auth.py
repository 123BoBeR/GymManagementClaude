from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from extensions import db
from models import User
from services import UserService

bp = Blueprint('auth', __name__)


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
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('auth.index'))
        flash('Nieprawidłowa nazwa użytkownika lub hasło.', 'danger')
    return render_template('login.html')


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


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
