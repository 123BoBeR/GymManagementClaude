import os
from flask import Flask, render_template, session
from dotenv import load_dotenv
from extensions import db, csrf, migrate, limiter
from blueprints.auth import bp as auth_bp
from blueprints.admin import bp as admin_bp
from blueprints.trainer import bp as trainer_bp
from blueprints.client import bp as client_bp

load_dotenv()


def _is_production():
    return os.environ.get('FLASK_ENV') == 'production'


def create_app(test_config=None):
    app = Flask(__name__)

    # SECRET_KEY: w produkcji wymagany (brak = błąd startu, by nie wyciekł
    # przewidywalny klucz). W trybie deweloperskim dozwolony fallback.
    secret = os.environ.get('SECRET_KEY')
    if not secret and not test_config:
        if _is_production():
            raise RuntimeError(
                "SECRET_KEY musi być ustawiony w środowisku produkcyjnym "
                "(FLASK_ENV=production).")
        secret = 'dev-secret-change-me'
    app.config['SECRET_KEY'] = secret or 'dev-secret-change-me'

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///gym.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Hardening ciasteczka sesji (B37). SECURE tylko w produkcji (https),
    # żeby nie psuć lokalnego http.
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = _is_production()

    # Nadpisanie konfiguracji (np. z testów) PRZED init_app, żeby silnik
    # bazy zbindował się do właściwego URI (inaczej trzyma się pliku gym.db).
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(trainer_bp)
    app.register_blueprint(client_bp)

    app.jinja_env.globals['enumerate'] = enumerate
    app.jinja_env.filters['enumerate'] = enumerate

    from services import month_label
    app.jinja_env.filters['month_label'] = month_label

    @app.context_processor
    def inject_nav_notifications():
        uid = session.get('user_id')
        if not uid:
            return {'nav_unread_count': 0}
        from services import NotificationService
        return {'nav_unread_count': NotificationService.unread_count(uid)}

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        resp.headers.setdefault('Referrer-Policy', 'same-origin')
        return resp

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('429.html'), 429

    @app.cli.command('sessions-refresh')
    def sessions_refresh():
        """Dogenerowuje brakujące przyszłe sesje (do uruchamiania z crona)."""
        from blueprints.sessions import refresh_all_future_sessions
        n = refresh_all_future_sessions()
        print(f'Dogenerowano {n} sesji.')

    return app


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='127.0.0.1', port=5000)
