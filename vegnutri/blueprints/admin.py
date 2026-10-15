from datetime import date, timedelta

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import ChatMessage, MealLog, Payment, User, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@login_required
def guard():
    if not current_user.is_admin:
        abort(403)


@bp.route("/")
def index():
    now = utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    paid = User.query.filter(User.plan.in_(("pro", "family")), User.plan_expires_at > now)
    revenue_30 = db.session.query(func.coalesce(func.sum(Payment.amount_paise), 0)).filter(
        Payment.status == "paid", Payment.paid_at >= month_ago).scalar()
    active_7 = db.session.query(func.count(func.distinct(MealLog.user_id))).filter(
        MealLog.log_date >= date.today() - timedelta(days=6)).scalar()
    total = User.query.count()
    signups = []
    for i in range(13, -1, -1):
        d = date.today() - timedelta(days=i)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        signups.append((d.strftime("%d %b"), User.query.filter(User.created_at >= start,
                                                               User.created_at < start + timedelta(days=1)).count()))
    stats = {
        "users": total,
        "new_7": User.query.filter(User.created_at >= week_ago).count(),
        "active_7": active_7,
        "paid": paid.count(),
        "pro": paid.filter(User.plan == "pro").count(),
        "family": paid.filter(User.plan == "family").count(),
        "conversion": round(paid.count() / total * 100, 1) if total else 0,
        "revenue_30": revenue_30,
        "coach_7": ChatMessage.query.filter(ChatMessage.role == "user", ChatMessage.created_at >= week_ago).count(),
    }
    recent_payments = Payment.query.filter_by(status="paid").order_by(Payment.paid_at.desc()).limit(15).all()
    return render_template("admin/index.html", stats=stats, signups=signups, payments=recent_payments)
