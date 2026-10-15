from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import db, limiter
from ..models import User, utcnow
from ..services.mailer import send_email
from ._helpers import EMAIL_RE, USERNAME_RE

bp = Blueprint("auth", __name__)


def _safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def _maybe_admin(user):
    if user.email in current_app.config["ADMIN_EMAILS"]:
        user.is_admin = True


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tracker.dashboard"))
    form = request.form
    if request.method == "POST":
        username = form.get("username", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        errors = []
        if not USERNAME_RE.match(username):
            errors.append("Username must be 3-30 characters: letters, numbers, dots or underscores.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not form.get("accept_terms"):
            errors.append("Accept the Terms and Privacy Policy to continue.")
        if not errors and User.query.filter((User.email == email) | (User.username == username)).first():
            errors.append("That username or email is already registered. Try logging in.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html", form=form), 400
        user = User(username=username, email=email, accepted_terms_at=utcnow(),
                    marketing_opt_in=bool(form.get("marketing")))
        user.set_password(password)
        _maybe_admin(user)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        return redirect(url_for("tracker.onboarding"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute; 50 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tracker.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if user.has_legacy_hash:
                user.set_password(password)
            user.last_login_at = utcnow()
            _maybe_admin(user)
            db.session.commit()
            login_user(user, remember=bool(request.form.get("remember", "1")))
            nxt = _safe_next(request.args.get("next"))
            if nxt:
                return redirect(nxt)
            return redirect(url_for("tracker.dashboard" if user.profile else "tracker.onboarding"))
        flash("That email and password don't match. Check them and try again.", "error")
        return render_template("auth/login.html", email=email), 401
    return render_template("auth/login.html", email="")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You're logged out.", "info")
    return redirect(url_for("main.index"))


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def make_reset_token(user):
    # Including part of the hash means the link stops working once the password changes
    return _serializer().dumps({"uid": user.id, "h": user.password_hash[-12:]})


@bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            link = url_for("auth.reset", token=make_reset_token(user), _external=True)
            send_email(user.email, f"Reset your {current_app.config['APP_NAME']} password",
                       render_template("emails/reset.txt", user=user, link=link))
        # Same message either way, so the form can't be used to discover accounts
        flash("If that email has an account, a reset link is on its way. It works for 1 hour.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html")


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    try:
        data = _serializer().loads(token, max_age=3600)
    except SignatureExpired:
        flash("That reset link has expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot"))
    except BadSignature:
        flash("That reset link isn't valid. Request a new one.", "error")
        return redirect(url_for("auth.forgot"))
    user = db.session.get(User, data.get("uid"))
    if not user or user.password_hash[-12:] != data.get("h"):
        flash("That reset link has already been used. Request a new one.", "error")
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/reset.html", token=token), 400
        user.set_password(password)
        db.session.commit()
        flash("Password updated. Log in with your new password.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", token=token)
