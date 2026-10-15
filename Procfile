release: flask --app wsgi db upgrade
web: gunicorn -c gunicorn.conf.py wsgi:app
