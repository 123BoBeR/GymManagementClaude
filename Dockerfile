# GymManagement — obraz produkcyjny
FROM python:3.12-slim

# Nie buforuj pyc, strumieniuj logi
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

WORKDIR /app

# Zależności najpierw (lepsze cache warstw). psycopg2-binary dla Postgresa.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary==2.9.9

# Kod aplikacji
COPY . .

EXPOSE 5000

# Przy starcie: zaktualizuj schemat migracjami, potem serwuj przez waitress.
CMD ["sh", "-c", "flask db upgrade && waitress-serve --host=0.0.0.0 --port=5000 wsgi:app"]
