"""VegNutri: nutrition coaching for Indian vegetarians."""
import logging
import os
import secrets
from datetime import datetime

import click
from flask import Flask, g, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, limiter, login_manager, migrate

__version__ = "4.0.0"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if os.environ.get("TRUST_PROXY", "1") == "1" and not app.config["TESTING"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not os.environ.get("SECRET_KEY") and not app.config["TESTING"]:
        app.logger.warning("SECRET_KEY is not set. Sessions will reset on every restart. Set it in production.")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401  (register models with SQLAlchemy)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    from .blueprints import account, admin, auth, billing, coach, explore, main, planner, quicklog, tracker
    for bp in (main.bp, auth.bp, tracker.bp, planner.bp, coach.bp, billing.bp, account.bp, admin.bp, quicklog.bp,
               explore.bp):
        app.register_blueprint(bp)
    csrf.exempt(billing.webhook)  # authenticated by Razorpay's HMAC signature instead
    csrf.exempt(main.weekly_digest_task)  # authenticated by TASK_TOKEN instead

    _register_template_helpers(app)
    _register_security_headers(app)
    _register_errors(app)
    _register_cli(app)
    return app


def _register_template_helpers(app):
    from .data.meals import CUISINES
    from .services import nutrition, plans

    @app.before_request
    def _nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject():
        from flask_login import current_user
        return {
            "csp_nonce": lambda: g.get("csp_nonce", ""),
            "app_name": app.config["APP_NAME"],
            "support_email": app.config["SUPPORT_EMAIL"],
            "company_name": app.config["COMPANY_NAME"],
            "year": datetime.now().year,
            "has_feature": lambda f: plans.has_feature(current_user, f),
            "current_plan": plans.plan_of(current_user),
            "CUISINES": CUISINES,
            "DIET_MODES": nutrition.DIET_MODES,
        }

    @app.template_filter("inr")
    def inr(paise):
        return plans.price_label(paise)

    @app.template_filter("num")
    def num(value, digits=0):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return value
        return f"{value:,.{digits}f}"


def _register_security_headers(app):
    @app.after_request
    def headers(resp):
        nonce = g.get("csp_nonce", "")
        resp.headers.setdefault("Content-Security-Policy", "; ".join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}' https://checkout.razorpay.com",
            "style-src 'self' 'unsafe-inline'",
            "font-src 'self'",
            "img-src 'self' data: https:",
            "connect-src 'self' https://*.razorpay.com",
            "frame-src https://*.razorpay.com",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]))
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
        if request.is_secure:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp


def _register_errors(app):
    def render(code, title, message):
        if request.path.startswith("/api/"):
            return {"error": title, "message": message}, code
        return render_template("errors/error.html", code=code, title=title, message=message), code

    app.register_error_handler(404, lambda e: render(404, "Page not found", "That page doesn't exist. Check the link or go back home."))
    app.register_error_handler(403, lambda e: render(403, "Not allowed", "You don't have access to this page."))
    app.register_error_handler(429, lambda e: render(429, "Slow down", "Too many requests. Wait a minute and try again."))
    app.register_error_handler(413, lambda e: render(413, "That file is too big", "Photos and voice notes must be under 12 MB."))
    app.register_error_handler(400, lambda e: render(400, "Something was off with that request", "Refresh the page and try again."))

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render(500, "Something went wrong on our side", "We've logged it. Try again in a minute.")


def _register_cli(app):
    from .models import User

    @app.cli.command("init-db")
    def init_db():
        """Create all tables (quick local setup; production uses `flask db upgrade`)."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("coach-check")
    def coach_check():
        """Test the Groq connection and show exactly what's wrong if the coach fails."""
        from .services.coach import diagnose, is_configured
        for line in diagnose():
            click.echo(line)
        if is_configured():
            from .services.quicklog import diagnose_lines
            for line in diagnose_lines():
                click.echo(line)

    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin(email):
        """Give an existing user access to /admin."""
        user = User.query.filter_by(email=email.strip().lower()).first()
        if not user:
            raise click.ClickException("No user with that email.")
        user.is_admin = True
        db.session.commit()
        click.echo(f"{email} is now an admin.")
