import os
from flask import Flask
from dotenv import load_dotenv
from extensions import db, csrf
from blueprints.auth import bp as auth_bp
from blueprints.admin import bp as admin_bp
from blueprints.trainer import bp as trainer_bp
from blueprints.client import bp as client_bp

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///gym.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(trainer_bp)
    app.register_blueprint(client_bp)

    app.jinja_env.globals['enumerate'] = enumerate
    app.jinja_env.filters['enumerate'] = enumerate

    return app


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)
