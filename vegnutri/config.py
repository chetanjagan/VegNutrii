"""Configuration. Every secret comes from the environment (see .env.example)."""
import os
import secrets


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _db_url():
    url = os.environ.get("DATABASE_URL", "sqlite:///vegnutri.db")
    # Heroku/Render style URLs use postgres://, SQLAlchemy needs postgresql+psycopg://
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Config:
    APP_NAME = os.environ.get("APP_NAME", "VegNutri")
    APP_URL = os.environ.get("APP_URL", "http://localhost:5000").rstrip("/")
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@example.com")
    COMPANY_NAME = os.environ.get("COMPANY_NAME", "VegNutri")

    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = _db_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30

    WTF_CSRF_TIME_LIMIT = None  # token valid for the session

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", True)

    # AI coach via Groq (server-side key; users never see or supply it)
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "")  # optional: force a specific model id

    # Payments
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    # Lets you click "upgrade" without paying. Only honoured when DEBUG is on.
    DEMO_BILLING = _bool("DEMO_BILLING", False)

    # Email (password reset). If MAIL_SERVER is empty, emails are printed to the log.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "VegNutri <no-reply@example.com>")
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)

    ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]

    DEBUG = _bool("FLASK_DEBUG", False)
    TESTING = False


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    GROQ_API_KEY = ""
    RAZORPAY_KEY_ID = "rzp_test_key"
    RAZORPAY_KEY_SECRET = "test_secret"
    RAZORPAY_WEBHOOK_SECRET = "whsec_test"
    MAIL_SERVER = ""
