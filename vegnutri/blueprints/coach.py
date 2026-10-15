from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db, limiter
from ..models import ChatMessage, MealPlan
from ..services import coach as coach_svc
from ..services import planner, tracking
from ._helpers import profile_required

bp = Blueprint("coach", __name__)

STARTERS = [
    "What should I eat for dinner to hit my protein today?",
    "Give me 3 high-protein breakfasts under 15 minutes",
    "How can I get more iron as a vegetarian?",
    "Suggest a Navratri fasting day menu",
]


@bp.route("/coach")
@profile_required
def page():
    history = (ChatMessage.query.filter_by(user_id=current_user.id, cleared=False)
               .order_by(ChatMessage.created_at.desc()).limit(40).all())[::-1]
    return render_template("app/coach.html", history=history, quota=coach_svc.quota(current_user),
                           configured=coach_svc.is_configured(), starters=STARTERS,
                           prefill=request.args.get("ask", "")[:300])


@bp.route("/api/coach", methods=["POST"])
@profile_required
@limiter.limit("12 per minute")
def chat():
    message = ((request.get_json(silent=True) or {}).get("message") or "").strip()
    if not message:
        return jsonify({"error": "empty", "message": "Type a question first."}), 400
    if len(message) > 1500:
        return jsonify({"error": "too_long", "message": "Keep questions under 1,500 characters."}), 400
    q = coach_svc.quota(current_user)
    if q["left"] <= 0:
        return jsonify({"error": "quota", "message": f"You've used today's {q['limit']} questions.",
                        "upgrade": not current_user.is_paid}), 429

    p = current_user.profile
    today = date.today()
    plan_row = MealPlan.query.filter_by(user_id=current_user.id, plan_date=today).first()
    report = tracking.micro_report(current_user.id, p.gender)
    gaps = [i["label"] for i in report["items"] if i["low"]]
    prompt = coach_svc.system_prompt(current_user, p, tracking.day_totals(current_user.id, today),
                                     planner.describe(plan_row.data) if plan_row else None, gaps)
    try:
        reply = coach_svc.chat(current_user, message, prompt)
    except coach_svc.CoachError as exc:
        return jsonify({"error": "coach", "message": str(exc)}), exc.status
    return jsonify({"reply": reply, "left": q["left"] - 1})


@bp.route("/coach/clear", methods=["POST"])
@profile_required
def clear():
    # Hide rather than delete, so clearing doesn't reset the daily question quota
    ChatMessage.query.filter_by(user_id=current_user.id, cleared=False).update({"cleared": True})
    db.session.commit()
    flash("Conversation cleared.", "info")
    return redirect(url_for("coach.page"))
