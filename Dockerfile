FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENV FLASK_APP=wsgi.py PORT=8000
EXPOSE 8000
# Apply database migrations, then start the web server
CMD ["sh", "-c", "flask db upgrade && gunicorn -c gunicorn.conf.py wsgi:app"]
