import os
from flask import Flask, render_template
from dotenv import load_dotenv
from extensions import db, csrf
from blueprints.auth import bp as auth_bp
from blueprints.admin import bp as admin_bp
from blueprints.trainer import bp as trainer_bp
from blueprints.client import bp as client_bp

load_dotenv()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///gym.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Nadpisanie konfiguracji (np. z testów) PRZED init_app, żeby silnik
    # bazy zbindował się do właściwego URI (inaczej trzyma się pliku gym.db).
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(trainer_bp)
    app.register_blueprint(client_bp)

    app.jinja_env.globals['enumerate'] = enumerate
    app.jinja_env.filters['enumerate'] = enumerate

    from services import month_label
    app.jinja_env.filters['month_label'] = month_label

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    return app


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)
