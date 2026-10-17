"""Snap, say or type what you ate. Review the recognised items, then log them."""
from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import current_user

from ..extensions import db, limiter
from ..models import MealLog, utcnow
from ..services import coach, quicklog
from ._helpers import parse_day, profile_required

bp = Blueprint("quicklog", __name__)

MEAL_TYPES = ("breakfast", "lunch", "snack", "dinner")


def _default_meal_type():
    hour = (utcnow() + timedelta(hours=5, minutes=30)).hour  # India time
    return "breakfast" if hour < 11 else "lunch" if hour < 16 else "snack" if hour < 19 else "dinner"


@bp.route("/quick-log")
@profile_required
def page():
    return render_template("app/quicklog.html", configured=coach.is_configured(),
                           photo=quicklog.usage(current_user, "photo"), smart=quicklog.usage(current_user, "smart"),
                           meal_types=MEAL_TYPES, default_type=_default_meal_type(), today=date.today())


def _respond(fn, *args):
    try:
        result = fn(current_user, *args)
    except quicklog.QuickLogError as exc:
        body = {"error": "quicklog", "message": str(exc)}
        if exc.status == 429 and not current_user.is_paid:
            body["upgrade"] = url_for("billing.pricing")
        return jsonify(body), exc.status
    result["photo_left"] = quicklog.usage(current_user, "photo")["left"]
    result["smart_left"] = quicklog.usage(current_user, "smart")["left"]
    return jsonify(result)


@bp.route("/api/quick-log/photo", methods=["POST"])
@profile_required
@limiter.limit("10 per minute")
def photo():
    f = request.files.get("image")
    return _respond(quicklog.from_photo, f.read() if f else b"")


@bp.route("/api/quick-log/voice", methods=["POST"])
@profile_required
@limiter.limit("10 per minute")
def voice():
    f = request.files.get("audio")
    return _respond(quicklog.from_voice, f.read() if f else b"", f.mimetype if f else "")


@bp.route("/api/quick-log/text", methods=["POST"])
@profile_required
@limiter.limit("15 per minute")
def text():
    return _respond(quicklog.from_text, (request.get_json(silent=True) or {}).get("text", ""))


@bp.route("/api/quick-log/save", methods=["POST"])
@profile_required
def save():
    data = request.get_json(silent=True) or {}
    meal_type = data.get("meal_type") if data.get("meal_type") in MEAL_TYPES else "snack"
    day = parse_day(data.get("log_date"))
    logs = quicklog.build_logs(data.get("items"))
    if not logs:
        return jsonify({"error": "empty", "message": "Tick at least one item to log."}), 400
    for values in logs:
        db.session.add(MealLog(user_id=current_user.id, meal_type=meal_type, log_date=day, **values))
    db.session.commit()
    total = round(sum(v["calories"] for v in logs))
    return jsonify({"ok": True, "count": len(logs), "kcal": total, "redirect": url_for("tracker.dashboard")})
