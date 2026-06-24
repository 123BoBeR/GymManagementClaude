import sqlite3
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Wymusza egzekwowanie kluczy obcych w SQLite (domyślnie wyłączone).

    Dzięki temu kaskady ON DELETE działają, a osierocone wiersze nie powstają.
    Dla innych silników (np. PostgreSQL) listener nic nie robi.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
