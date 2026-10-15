import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..data.foods import COMPONENTS
from ..data.meals import MEALS
from ..extensions import db
from ..models import HouseholdMember, MealLog, MealPlan
from ..services import nutrition, planner
from ..services.plans import PLANS, has_feature, plan_of, requires_feature
from ._helpers import clean_text, profile_required, to_float, to_int

bp = Blueprint("planner", __name__)

RECIPES = json.loads((Path(__file__).resolve().parent.parent / "data" / "recipes.json").read_text(encoding="utf-8"))
SLOT_LABELS = {"breakfast": "Breakfast", "lunch": "Lunch", "snack": "Snack", "dinner": "Dinner", "extra": "Extra snack"}


def _ctx():
    return planner.planning_context(current_user.profile,
                                    use_budget=has_feature(current_user, "budget"),
                                    use_fasting=has_feature(current_user, "fasting"))


def _horizon():
    return plan_of(current_user)["plan_days"]


def ensure_plans(days):
    """Return {date: MealPlan} for the next `days` days, creating missing ones."""
    start = date.today()
    dates = [start + timedelta(days=i) for i in range(days)]
    rows = {r.plan_date: r for r in MealPlan.query.filter(
        MealPlan.user_id == current_user.id, MealPlan.plan_date.in_(dates)).all()}
    missing = [d for d in dates if d not in rows]
    if missing:
        used = Counter(k for r in rows.values() for k in r.data["meals"].values())
        ctx = _ctx()
        for d, plan in zip(missing, planner.plan_days(ctx, missing, used)):
            rows[d] = _save(d, plan)
        db.session.commit()
    return [(d, rows[d]) for d in dates]


def _save(day, plan, row=None):
    totals = planner.describe(plan)["totals"]
    if row is None:
        row = MealPlan(user_id=current_user.id, plan_date=day)
        db.session.add(row)
    row.data = plan
    row.total_calories = totals["kcal"]
    row.total_protein = totals["protein"]
    row.total_cost = totals["cost"]
    return row


def _get_day(day_str):
    try:
        day = date.fromisoformat(day_str)
    except ValueError:
        abort(404)
    return day, MealPlan.query.filter_by(user_id=current_user.id, plan_date=day).first_or_404()


@bp.route("/plan")
@profile_required
def meal_plan():
    days = ensure_plans(_horizon())
    week = [(d, planner.describe(r.data)) for d, r in days]
    return render_template("app/plan.html", week=week, p=current_user.profile, slot_labels=SLOT_LABELS,
                           locked_days=7 - len(week), today=date.today())


@bp.route("/plan/regenerate", methods=["POST"])
@profile_required
def regenerate():
    MealPlan.query.filter(MealPlan.user_id == current_user.id, MealPlan.plan_date >= date.today()).delete()
    db.session.commit()
    ensure_plans(_horizon())
    flash("Fresh plan ready.", "success")
    return redirect(url_for("planner.meal_plan"))


@bp.route("/api/plan/<day>/swap/<slot>", methods=["POST"])
@profile_required
def swap(day, slot):
    if slot not in SLOT_LABELS:
        abort(404)
    d, row = _get_day(day)
    if d < date.today():
        return jsonify({"error": "past_day", "message": "Past days can't be changed."}), 400
    new = planner.swap_slot(_ctx(), d, row.data, slot)
    _save(d, new, row)
    db.session.commit()
    view = planner.describe(new)
    return jsonify({"meal": view["meals"].get(slot), "totals": view["totals"], "scale": view["scale"]})


@bp.route("/plan/<day>/log/<slot>", methods=["POST"])
@profile_required
def log_planned(day, slot):
    d, row = _get_day(day)
    if d > date.today():
        flash("You can log planned meals once the day arrives.", "info")
        return redirect(url_for("planner.meal_plan"))
    meal = planner.describe(row.data)["meals"].get(slot)
    if not meal:
        abort(404)
    db.session.add(MealLog(
        user_id=current_user.id, name=meal["name"], meal_type="snack" if slot == "extra" else slot,
        servings=row.data.get("scale", 1.0), calories=meal["kcal"], protein=meal["protein"], carbs=meal["carbs"],
        fat=meal["fat"], fiber=meal["fiber"], iron=meal["iron"], calcium=meal["calcium"], b12=meal["b12"],
        zinc=meal["zinc"], log_date=d))
    db.session.commit()
    flash(f"Logged {meal['name']}.", "success")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("tracker.dashboard"))


@bp.route("/recipes/<meal_key>")
@login_required
def recipe(meal_key):
    meal = MEALS.get(meal_key)
    if not meal:
        abort(404)
    parts = [(COMPONENTS[c], q) for c, q in meal["parts"]]
    return render_template("app/recipe.html", meal=meal, parts=parts, recipe=RECIPES.get(meal_key))


def _family_multiplier(plan_kcal):
    """How many 'portions of the owner's plan' the household needs."""
    if not has_feature(current_user, "family"):
        return 1.0, []
    members = HouseholdMember.query.filter_by(owner_id=current_user.id).all()
    shares = [(m, round(m.daily_calories / plan_kcal, 2) if plan_kcal else 1.0) for m in members]
    return 1.0 + sum(s for _, s in shares), shares


@bp.route("/grocery")
@profile_required
def grocery():
    days = 7 if has_feature(current_user, "grocery_week") else 2
    rows = ensure_plans(min(days, _horizon()))
    plans = [r.data for _, r in rows]
    avg_kcal = sum(r.total_calories for _, r in rows) / len(rows) if rows else 0
    mult, _ = _family_multiplier(avg_kcal)
    return render_template("app/grocery.html", grocery=planner.grocery_list(plans, mult), days=len(rows),
                           multiplier=mult, cost=sum(r.total_cost for _, r in rows) * mult,
                           full=has_feature(current_user, "grocery_week"))


@bp.route("/family", methods=["GET", "POST"])
@profile_required
@requires_feature("family")
def family():
    max_members = PLANS["family"]["max_members"]
    members = HouseholdMember.query.filter_by(owner_id=current_user.id).order_by(HouseholdMember.created_at).all()
    if request.method == "POST":
        f = request.form
        if len(members) >= max_members:
            flash(f"The Family plan covers you plus {max_members} people.", "error")
            return redirect(url_for("planner.family"))
        name = clean_text(f.get("name"), 60)
        age = to_int(f.get("age"), None, 2, 100)
        height = to_float(f.get("height"), None, 60, 230)
        weight = to_float(f.get("weight"), None, 10, 300)
        gender = f.get("gender") if f.get("gender") in ("male", "female") else None
        activity = f.get("activity_level") if f.get("activity_level") in nutrition.ACTIVITY else "light"
        goal = f.get("goal") if f.get("goal") in nutrition.GOALS else "maintenance"
        if not name or None in (age, height, weight, gender):
            flash("Fill in name, age, height, weight and gender.", "error")
            return redirect(url_for("planner.family"))
        if age < 18:
            goal = "maintenance"  # never plan a deficit for a child
        kcal, protein = nutrition.member_targets(age, height, weight, gender, goal, activity)
        db.session.add(HouseholdMember(owner_id=current_user.id, name=name, age=age, gender=gender, height=height,
                                       weight=weight, activity_level=activity, goal=goal,
                                       daily_calories=kcal, daily_protein=protein))
        db.session.commit()
        flash(f"Added {name}. Their portions now appear in the family kitchen.", "success")
        return redirect(url_for("planner.family"))

    rows = ensure_plans(1)
    today_view = planner.describe(rows[0][1].data)
    _, shares = _family_multiplier(today_view["totals"]["kcal"])
    return render_template("app/family.html", members=members, shares=shares, plan=today_view,
                           slot_labels=SLOT_LABELS, max_members=max_members, p=current_user.profile)


@bp.route("/family/<int:member_id>/delete", methods=["POST"])
@login_required
def delete_member(member_id):
    m = HouseholdMember.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    db.session.delete(m)
    db.session.commit()
    flash(f"Removed {m.name}.", "info")
    return redirect(url_for("planner.family"))
