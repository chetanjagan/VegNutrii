from datetime import date, timedelta

from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import ChatMessage, Coupon, MealLog, Payment, User, utcnow
from ..services.plans import FEATURE_NAMES, PLANS, price_label

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
    active_paid = User.query.filter(User.plan.in_(("pro", "family")), User.plan_expires_at > now)
    paid = active_paid.filter(User.on_trial.is_(False))
    trials = active_paid.filter(User.on_trial.is_(True)).count()
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
        "trials": trials,
        "referred": User.query.filter(User.referred_by_id.isnot(None)).count(),
        "digest_on": User.query.filter(User.weekly_digest.is_(True)).count(),
    }
    recent_payments = Payment.query.filter_by(status="paid").order_by(Payment.paid_at.desc()).limit(15).all()
    coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return render_template("admin/index.html", stats=stats, signups=signups, payments=recent_payments, coupons=coupons,
                           feature_rows=feature_matrix(), preview=current_user.admin_preview)


def feature_matrix():
    """Rows of (feature, free, pro, family), built from the live plan settings."""
    order = ("free", "pro", "family")

    def price(plan):
        prices = PLANS[plan]["prices"]
        if not prices:
            return "₹0"
        return " or ".join(f"{price_label(v)}/{'month' if k == 'month' else 'year'}" for k, v in prices.items())

    rows = [("Price", *[price(p) for p in order]),
            ("Meal plan length", *[f"{PLANS[p]['plan_days']} days" for p in order]),
            ("Coach questions a day", *[str(PLANS[p]["coach_daily"]) for p in order]),
            ("Photo food logging a day", *[str(PLANS[p]["photo_daily"]) for p in order]),
            ("Voice or typed food logging a day", *[str(PLANS[p]["smart_daily"]) for p in order])]
    rows += [(label, *[key in PLANS[p]["features"] for p in order]) for key, label in FEATURE_NAMES.items()]
    rows.append(("Family members", *[str(PLANS[p].get("max_members", "")) or False for p in order]))
    rows.append(("Grocery list", "2 days", "7 days", "7 days, scaled for household"))
    rows.append(("Weekly email nutrients", "Iron only", "All four", "All four"))
    always = ("Food, water, weight and mood tracking; recipes; My foods; calendar; milestones; "
              "iron tracking; weekly email; data export")
    rows.append(("Included on every plan", always, "Yes", "Yes"))
    trial = current_app.config.get("TRIAL_DAYS", 0)
    if trial:
        rows.append(("New sign-ups", f"Get Pro free for {trial} days "
                     f"({current_app.config.get('REFERRAL_TRIAL_DAYS', trial)} if invited)", "", ""))
    return rows


@bp.route("/preview", methods=["POST"])
def preview():
    """Let an admin see the app exactly as a Free, Pro or Family user would."""
    plan = request.form.get("plan", "")
    if plan in PLANS:
        session["admin_preview"] = plan
        flash(f"You're now seeing the app as a {PLANS[plan]['name']} user. Switch back any time from the bar at the top.", "info")
        return redirect(url_for("tracker.dashboard"))
    session.pop("admin_preview", None)
    flash("Preview off. As an admin you have full access to every feature.", "info")
    return redirect(request.form.get("next") if (request.form.get("next") or "").startswith("/")
                    and not request.form.get("next", "").startswith("//") else url_for("admin.index"))


@bp.route("/coupons", methods=["POST"])
def create_coupon():
    f = request.form
    code = "".join(ch for ch in f.get("code", "").upper() if ch.isalnum())[:30]
    try:
        pct = int(f.get("percent_off", 0))
    except ValueError:
        pct = 0
    plans = ",".join(p for p in ("pro", "family") if f.get(f"plan_{p}")) or "pro,family"
    max_uses = f.get("max_uses", "").strip()
    expires = f.get("expires_at", "").strip()
    if not code or not 1 <= pct <= 90:
        flash("Give the code letters or numbers, and a discount between 1% and 90%.", "error")
    elif Coupon.query.filter_by(code=code).first():
        flash(f"{code} already exists.", "error")
    else:
        db.session.add(Coupon(
            code=code, percent_off=pct, plans=plans,
            max_uses=int(max_uses) if max_uses.isdigit() else None,
            expires_at=datetime.fromisoformat(expires + "T23:59:59") if expires else None,
            note=f.get("note", "").strip()[:120]))
        db.session.commit()
        flash(f"Coupon {code} created: {pct}% off.", "success")
    return redirect(url_for("admin.index") + "#coupons")


@bp.route("/coupons/<int:coupon_id>/toggle", methods=["POST"])
def toggle_coupon(coupon_id):
    c = db.get_or_404(Coupon, coupon_id)
    c.active = not c.active
    db.session.commit()
    flash(f"{c.code} {'turned on' if c.active else 'turned off'}.", "info")
    return redirect(url_for("admin.index") + "#coupons")
