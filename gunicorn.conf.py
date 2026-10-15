import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = 60  # coach replies can take a while
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "*"
