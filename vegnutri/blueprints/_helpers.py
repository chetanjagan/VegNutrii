import re
from datetime import date
from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user, login_required

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


def profile_required(fn):
    """Logged in AND has completed onboarding."""
    @login_required
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.profile:
            flash("Tell us a little about yourself first.", "info")
            return redirect(url_for("tracker.onboarding"))
        return fn(*args, **kwargs)
    return wrapper


def to_float(value, default=None, lo=None, hi=None):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if lo is not None and v < lo:
        return default
    if hi is not None and v > hi:
        return default
    return v


def to_int(value, default=None, lo=None, hi=None):
    v = to_float(value, None, lo, hi)
    return default if v is None else int(v)


def parse_day(value, default=None):
    """ISO date from a form, limited to a sensible range."""
    try:
        d = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return default or date.today()
    if d > date.today() or (date.today() - d).days > 366:
        return default or date.today()
    return d


def clean_text(value, limit):
    return (value or "").strip()[:limit]
