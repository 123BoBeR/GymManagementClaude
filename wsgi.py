"""Punkt wejścia dla produkcyjnego serwera WSGI (waitress).

Produkcyjnie schemat bazy zakładamy migracjami (`flask db upgrade`), a nie
`db.create_all()` — dlatego ten plik tylko udostępnia obiekt `app`.

Uruchomienie (lokalnie lub w kontenerze):
    waitress-serve --host=0.0.0.0 --port=5000 wsgi:app

albo bezpośrednio:
    python wsgi.py
"""
from app import app

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
