import json
from datetime import datetime

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from ..extensions import db
from ..models import (ChatMessage, CustomFood, HouseholdMember, MealLog, MealPlan, MoodLog, Payment, Profile,
                      User, WaterLog, WeightLog)

bp = Blueprint("account", __name__, url_prefix="/account")

USER_TABLES = (MealLog, WeightLog, WaterLog, MoodLog, CustomFood, MealPlan, ChatMessage)


@bp.route("/")
@login_required
def settings():
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).limit(20).all()
    if not current_user.referral_code:
        current_user.ensure_referral_code()
        db.session.commit()
    invited = User.query.filter_by(referred_by_id=current_user.id).count()
    return render_template("app/account.html", payments=payments, invited=invited,
                           invite_url=current_app.config["APP_URL"] + url_for("auth.referral", code=current_user.referral_code),
                           reward_days=current_app.config["REFERRAL_REWARD_DAYS"],
                           friend_days=current_app.config["REFERRAL_TRIAL_DAYS"] if current_app.config["TRIAL_DAYS"] else 0)


@bp.route("/password", methods=["POST"])
@login_required
def change_password():
    if not current_user.check_password(request.form.get("current", "")):
        flash("Your current password isn't right.", "error")
    elif len(request.form.get("new", "")) < 8:
        flash("New password must be at least 8 characters.", "error")
    else:
        current_user.set_password(request.form["new"])
        db.session.commit()
        flash("Password changed.", "success")
    return redirect(url_for("account.settings"))


@bp.route("/preferences", methods=["POST"])
@login_required
def preferences():
    current_user.marketing_opt_in = bool(request.form.get("marketing"))
    current_user.weekly_digest = bool(request.form.get("weekly_digest"))
    db.session.commit()
    flash("Email preferences saved.", "success")
    return redirect(url_for("account.settings"))


def _rows(model, **filters):
    out = []
    for row in model.query.filter_by(**filters).all():
        item = {}
        for col in row.__table__.columns:
            v = getattr(row, col.name)
            item[col.name] = v.isoformat() if hasattr(v, "isoformat") else v
        out.append(item)
    return out


@bp.route("/export")
@login_required
def export():
    """Everything we hold about the user, as JSON (right to access under India's DPDP Act)."""
    uid = current_user.id
    data = {
        "exported_at": datetime.now().isoformat(),
        "account": {"username": current_user.username, "email": current_user.email,
                    "created_at": current_user.created_at.isoformat(), "plan": current_user.active_plan,
                    "plan_expires_at": current_user.plan_expires_at.isoformat() if current_user.plan_expires_at else None,
                    "marketing_opt_in": current_user.marketing_opt_in},
        "profile": _rows(Profile, user_id=uid),
        "household_members": _rows(HouseholdMember, owner_id=uid),
        "payments": _rows(Payment, user_id=uid),
    }
    for model in USER_TABLES:
        data[model.__tablename__] = _rows(model, user_id=uid)
    return Response(json.dumps(data, indent=2, ensure_ascii=False), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=vegnutri-my-data.json"})


@bp.route("/delete", methods=["POST"])
@login_required
def delete():
    if not current_user.check_password(request.form.get("password", "")):
        flash("Enter your password to delete your account.", "error")
        return redirect(url_for("account.settings"))
    uid = current_user.id
    user = current_user._get_current_object()
    for model in USER_TABLES:
        model.query.filter_by(user_id=uid).delete()
    HouseholdMember.query.filter_by(owner_id=uid).delete()
    # Payment records are kept (without the link to you) because tax law requires them
    Payment.query.filter_by(user_id=uid).update({"user_id": None})
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("Your account and data have been deleted.", "info")
    return redirect(url_for("main.index"))
