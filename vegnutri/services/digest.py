"""Weekly progress email: what went well, what to work on, one concrete food tip."""
from datetime import date, timedelta

from flask import current_app, render_template, url_for
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import func

from ..extensions import db
from ..models import MealLog, User, WeightLog, utcnow
from . import tracking
from .mailer import send_email

ACTIVE_WITHIN_DAYS = 30  # don't email people who stopped using the app


def _serializer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="weekly-digest-unsubscribe")


def unsubscribe_token(user):
    return _serializer().dumps(user.id)


def user_from_token(token):
    try:
        return db.session.get(User, _serializer().loads(token))
    except BadSignature:
        return None


def build(user):
    """Return the context for one user's weekly email, or None if there's nothing to say."""
    p = user.profile
    if not p:
        return None
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=6)
    last_log = db.session.query(func.max(MealLog.log_date)).filter(MealLog.user_id == user.id).scalar()
    if not last_log or (date.today() - last_log).days > ACTIVE_WITHIN_DAYS:
        return None
    rows = db.session.query(MealLog.log_date, func.sum(MealLog.calories), func.sum(MealLog.protein)).filter(
        MealLog.user_id == user.id, MealLog.log_date.between(start, end)).group_by(MealLog.log_date).all()
    days_logged = len(rows)
    protein_days = sum(1 for _, _, pro in rows if (pro or 0) >= p.daily_protein * 0.8)
    avg_kcal = sum(float(c or 0) for _, c, _ in rows) / days_logged if days_logged else 0
    avg_pro = sum(float(x or 0) for _, _, x in rows) / days_logged if days_logged else 0
    weights = WeightLog.query.filter(WeightLog.user_id == user.id, WeightLog.log_date.between(start - timedelta(days=7), end)
                                     ).order_by(WeightLog.log_date).all()
    weight_change = round(weights[-1].weight - weights[0].weight, 1) if len(weights) >= 2 else None
    report = tracking.micro_report(user.id, p.gender)
    low = [i for i in report["items"] if i["low"]]
    if not user.is_paid:
        low = [i for i in low if i["key"] == "iron"]
    streak = tracking.streak(user.id, p.daily_protein)
    return {
        "user": user, "p": p, "start": start, "end": end, "days_logged": days_logged, "protein_days": protein_days,
        "avg_kcal": round(avg_kcal), "avg_pro": round(avg_pro), "weight_change": weight_change,
        "low": low[:2], "streak": streak["current"], "tip": tracking.tip_of_day(),
        "trial_days_left": user.trial_days_left,
    }


def due_users(limit):
    cutoff = utcnow() - timedelta(days=6)
    q = User.query.filter(User.weekly_digest.is_(True),
                          (User.last_digest_at.is_(None)) | (User.last_digest_at < cutoff)).order_by(User.id)
    return q.limit(limit).all(), q.count()


def send_batch(limit=100):
    """Send to up to `limit` users who are due. Returns counts so the scheduler knows when to stop."""
    users, total_due = due_users(limit)
    sent = skipped = failed = 0
    base = current_app.config["APP_URL"]
    for user in users:
        ctx = build(user)
        if ctx is None:
            user.last_digest_at = utcnow()  # nothing to report; check again next week
            skipped += 1
            continue
        ctx["dashboard_url"] = base + url_for("tracker.dashboard")
        ctx["plan_url"] = base + url_for("planner.meal_plan")
        ctx["pricing_url"] = base + url_for("billing.pricing")
        ctx["unsubscribe_url"] = base + url_for("main.unsubscribe", token=unsubscribe_token(user))
        subject = (f"Your week: protein on target {ctx['protein_days']} of 7 days" if ctx["days_logged"]
                   else f"Your {current_app.config['APP_NAME']} plan is ready for this week")
        if send_email(user.email, subject, render_template("emails/weekly.txt", **ctx)):
            user.last_digest_at = utcnow()
            sent += 1
        else:
            failed += 1
    db.session.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed, "remaining": max(total_due - sent - skipped, 0)}
