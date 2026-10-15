from datetime import date, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..data.foods import COMPONENTS, search_components
from ..data.meals import CUISINES
from ..extensions import db
from ..models import CustomFood, MealLog, MealPlan, MoodLog, Profile, WaterLog, WeightLog
from ..services import nutrition, planner, tracking
from ..services.plans import has_feature
from ._helpers import clean_text, parse_day, profile_required, to_float, to_int

bp = Blueprint("tracker", __name__)

MEAL_TYPES = ("breakfast", "lunch", "snack", "dinner")
MOODS = {"great": "Great", "good": "Good", "okay": "Okay", "low": "Low", "stressed": "Stressed"}
MICRO_FIELDS = ("fiber", "iron", "calcium", "b12", "zinc")


# ── Onboarding / profile ─────────────────────────────────────────────────
@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    profile = current_user.profile
    if request.method == "POST":
        f = request.form
        age = to_int(f.get("age"), lo=13, hi=100)
        height = to_float(f.get("height"), lo=100, hi=230)
        weight = to_float(f.get("weight"), lo=25, hi=300)
        gender = f.get("gender") if f.get("gender") in ("male", "female") else None
        goal = f.get("goal") if f.get("goal") in nutrition.GOALS else None
        activity = f.get("activity_level") if f.get("activity_level") in nutrition.ACTIVITY else None
        if None in (age, height, weight, gender, goal, activity):
            flash("Check your details: age 13-100, height 100-230 cm, weight 25-300 kg, and pick each option.", "error")
            return render_template("app/onboarding.html", profile=profile, form=f), 400
        if age < 18:
            flash("VegNutri is built for adults. For anyone under 18, plan meals with a doctor or dietitian.", "info")
        calories, protein = nutrition.calculate_targets(age, height, weight, gender, goal, activity)
        allergies = ",".join(a for a in f.getlist("allergies") if a in nutrition.ALLERGIES)
        fasting = ",".join(str(int(d)) for d in f.getlist("fasting_days") if d.isdigit() and 0 <= int(d) <= 6)
        values = dict(
            age=age, height=height, weight=weight, gender=gender, goal=goal, activity_level=activity,
            cuisine=f.get("cuisine") if f.get("cuisine") in CUISINES else "north_indian",
            diet_mode=f.get("diet_mode") if f.get("diet_mode") in nutrition.DIET_MODES else "vegetarian",
            allergies=allergies, cooking_time=to_int(f.get("cooking_time"), 30, 5, 120),
            daily_budget=to_int(f.get("daily_budget"), 0, 0, 5000), fasting_days=fasting,
            daily_calories=calories, daily_protein=protein,
            water_goal_ml=nutrition.water_goal_ml(weight, activity),
        )
        if profile:
            for k, v in values.items():
                setattr(profile, k, v)
        else:
            profile = Profile(user_id=current_user.id, **values)
            db.session.add(profile)
        # Targets or preferences changed: rebuild plans from today onwards
        MealPlan.query.filter(MealPlan.user_id == current_user.id, MealPlan.plan_date >= date.today()).delete()
        db.session.commit()
        if not WeightLog.query.filter_by(user_id=current_user.id, log_date=date.today()).first():
            db.session.add(WeightLog(user_id=current_user.id, weight=weight, log_date=date.today()))
            db.session.commit()
        flash(f"Saved. Your daily targets: {calories} kcal and {protein} g protein.", "success")
        return redirect(url_for("tracker.dashboard"))
    return render_template("app/onboarding.html", profile=profile, form={})


# ── Dashboard ────────────────────────────────────────────────────────────
@bp.route("/dashboard")
@profile_required
def dashboard():
    p = current_user.profile
    today = date.today()
    totals = tracking.day_totals(current_user.id, today)
    water = tracking.water_today(current_user.id)
    from .planner import ensure_plans  # local import avoids a circular import
    plan_view = planner.describe(ensure_plans(1)[0][1].data)
    rda = nutrition.RDA["female" if p.gender == "female" else "male"]
    labels, protein7 = tracking.daily_series(current_user.id, 7, "protein")
    logs = MealLog.query.filter_by(user_id=current_user.id, log_date=today).order_by(MealLog.created_at).all()
    return render_template(
        "app/dashboard.html", p=p, totals=totals, water=water, plan=plan_view, logs=logs,
        iron_target=rda["iron"], streak=tracking.streak(current_user.id, p.daily_protein),
        tip=tracking.tip_of_day(), labels=labels, protein7=protein7, today=today,
    )


# ── Food logging ─────────────────────────────────────────────────────────
def _log_from_component(key, servings):
    c = COMPONENTS.get(key)
    if not c:
        return None
    return dict(name=c["name"], calories=c["kcal"] * servings, protein=c["protein"] * servings,
                carbs=c["carbs"] * servings, fat=c["fat"] * servings,
                **{m: c[m] * servings for m in MICRO_FIELDS})


@bp.route("/log", methods=["GET", "POST"])
@profile_required
def log_meal():
    if request.method == "POST":
        f = request.form
        meal_type = f.get("meal_type") if f.get("meal_type") in MEAL_TYPES else "snack"
        servings = to_float(f.get("servings"), 1.0, 0.25, 10)
        day = parse_day(f.get("log_date"))
        source = f.get("source")
        values = None
        if source == "food":
            values = _log_from_component(f.get("food_key"), servings)
        elif source == "custom":
            cf = CustomFood.query.filter_by(id=to_int(f.get("custom_id"), 0), user_id=current_user.id).first()
            if cf:
                values = dict(name=cf.name, calories=cf.calories * servings, protein=cf.protein * servings,
                              carbs=cf.carbs * servings, fat=cf.fat * servings, fiber=cf.fiber * servings,
                              iron=cf.iron * servings, calcium=cf.calcium * servings, b12=0, zinc=0)
        else:
            name = clean_text(f.get("name"), 200)
            kcal = to_float(f.get("calories"), None, 0, 5000)
            if name and kcal is not None:
                values = dict(name=name, calories=kcal, protein=to_float(f.get("protein"), 0, 0, 300),
                              carbs=to_float(f.get("carbs"), 0, 0, 1000), fat=to_float(f.get("fat"), 0, 0, 500))
                servings = 1.0
        if not values:
            flash("Pick a food from the search, or fill in a name and calories.", "error")
            return redirect(url_for("tracker.log_meal"))
        db.session.add(MealLog(user_id=current_user.id, meal_type=meal_type, servings=servings, log_date=day, **values))
        db.session.commit()
        flash(f"Logged {values['name']}.", "success")
        return redirect(url_for("tracker.log_meal", d=day.isoformat()))

    day = parse_day(request.args.get("d"))
    logs = MealLog.query.filter_by(user_id=current_user.id, log_date=day).order_by(MealLog.created_at).all()
    customs = CustomFood.query.filter_by(user_id=current_user.id).order_by(CustomFood.name).all()
    return render_template("app/log.html", logs=logs, day=day, totals=tracking.day_totals(current_user.id, day),
                           p=current_user.profile, customs=customs, meal_types=MEAL_TYPES,
                           prev_day=day - timedelta(days=1), next_day=min(day + timedelta(days=1), date.today()))


@bp.route("/log/<int:log_id>/delete", methods=["POST"])
@login_required
def delete_log(log_id):
    log = MealLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    day = log.log_date
    db.session.delete(log)
    db.session.commit()
    flash("Entry removed.", "info")
    nxt = request.form.get("next", "")
    if not (nxt.startswith("/") and not nxt.startswith("//")):
        nxt = url_for("tracker.log_meal", d=day.isoformat())
    return redirect(nxt)


@bp.route("/api/foods")
@login_required
def api_foods():
    q = request.args.get("q", "")
    results = [{"key": c["key"], "name": c["name"], "serving": c["serving"], "kcal": c["kcal"], "protein": c["protein"],
                "source": "food"} for c in search_components(q)]
    if q.strip():
        for cf in CustomFood.query.filter(CustomFood.user_id == current_user.id,
                                          CustomFood.name.ilike(f"%{q.strip()}%")).limit(8):
            results.insert(0, {"key": str(cf.id), "name": cf.name, "serving": cf.serving_size, "kcal": cf.calories,
                               "protein": cf.protein, "source": "custom"})
    return jsonify(results[:15])


# ── Custom foods ─────────────────────────────────────────────────────────
@bp.route("/my-foods", methods=["GET", "POST"])
@profile_required
def my_foods():
    if request.method == "POST":
        f = request.form
        name = clean_text(f.get("name"), 120)
        kcal = to_float(f.get("calories"), None, 0, 5000)
        if not name or kcal is None:
            flash("Give the dish a name and its calories per serving.", "error")
        else:
            db.session.add(CustomFood(
                user_id=current_user.id, name=name, serving_size=clean_text(f.get("serving_size"), 60) or "1 serving",
                calories=kcal, protein=to_float(f.get("protein"), 0, 0, 300), carbs=to_float(f.get("carbs"), 0, 0, 1000),
                fat=to_float(f.get("fat"), 0, 0, 500), fiber=to_float(f.get("fiber"), 0, 0, 200),
                iron=to_float(f.get("iron"), 0, 0, 200), calcium=to_float(f.get("calcium"), 0, 0, 5000)))
            db.session.commit()
            flash(f"Added {name} to your foods.", "success")
        return redirect(url_for("tracker.my_foods"))
    foods = CustomFood.query.filter_by(user_id=current_user.id).order_by(CustomFood.created_at.desc()).all()
    return render_template("app/my_foods.html", foods=foods)


@bp.route("/my-foods/<int:food_id>/delete", methods=["POST"])
@login_required
def delete_food(food_id):
    cf = CustomFood.query.filter_by(id=food_id, user_id=current_user.id).first_or_404()
    db.session.delete(cf)
    db.session.commit()
    flash("Removed.", "info")
    return redirect(url_for("tracker.my_foods"))


# ── Water ────────────────────────────────────────────────────────────────
@bp.route("/water", methods=["GET", "POST"])
@profile_required
def water():
    if request.method == "POST":
        amount = to_int((request.get_json(silent=True) or request.form).get("amount"), None, 50, 2000)
        if amount:
            db.session.add(WaterLog(user_id=current_user.id, amount_ml=amount, log_date=date.today()))
            db.session.commit()
        total = tracking.water_today(current_user.id)
        if request.is_json:
            return jsonify({"total": total, "goal": current_user.profile.water_goal_ml})
        return redirect(url_for("tracker.water"))
    logs = WaterLog.query.filter_by(user_id=current_user.id, log_date=date.today()).order_by(WaterLog.created_at.desc()).all()
    labels, values = tracking.water_series(current_user.id)
    return render_template("app/water.html", logs=logs, total=tracking.water_today(current_user.id),
                           goal=current_user.profile.water_goal_ml, labels=labels, values=values)


@bp.route("/water/<int:log_id>/delete", methods=["POST"])
@login_required
def delete_water(log_id):
    w = WaterLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    db.session.delete(w)
    db.session.commit()
    return redirect(url_for("tracker.water"))


# ── Weight & progress ────────────────────────────────────────────────────
@bp.route("/progress", methods=["GET", "POST"])
@profile_required
def progress():
    p = current_user.profile
    if request.method == "POST":
        w = to_float(request.form.get("weight"), None, 25, 300)
        day = parse_day(request.form.get("log_date"))
        if w is None:
            flash("Enter a weight between 25 and 300 kg.", "error")
        else:
            row = WeightLog.query.filter_by(user_id=current_user.id, log_date=day).first()
            if row:
                row.weight = w
            else:
                db.session.add(WeightLog(user_id=current_user.id, weight=w, log_date=day))
            db.session.commit()
            flash("Weight saved.", "success")
        return redirect(url_for("tracker.progress"))
    weights = WeightLog.query.filter_by(user_id=current_user.id).order_by(WeightLog.log_date.desc()).limit(60).all()[::-1]
    labels, protein30 = tracking.daily_series(current_user.id, 30, "protein")
    _, kcal30 = tracking.daily_series(current_user.id, 30, "calories")
    current = weights[-1].weight if weights else p.weight
    return render_template("app/progress.html", p=p, weights=weights, labels=labels, protein30=protein30,
                           kcal30=kcal30, bmi=nutrition.bmi_stats(p.height, current), current=current,
                           today=date.today())


# ── Mood ─────────────────────────────────────────────────────────────────
@bp.route("/mood", methods=["GET", "POST"])
@profile_required
def mood():
    if request.method == "POST":
        m = request.form.get("mood")
        if m not in MOODS:
            flash("Pick how you feel.", "error")
            return redirect(url_for("tracker.mood"))
        row = MoodLog.query.filter_by(user_id=current_user.id, log_date=date.today()).first()
        if not row:
            row = MoodLog(user_id=current_user.id, log_date=date.today())
            db.session.add(row)
        row.mood = m
        row.energy_level = to_int(request.form.get("energy"), 3, 1, 5)
        row.note = clean_text(request.form.get("note"), 500)
        db.session.commit()
        flash("Check-in saved.", "success")
        return redirect(url_for("tracker.mood"))
    logs = MoodLog.query.filter_by(user_id=current_user.id).order_by(MoodLog.log_date.desc()).limit(30).all()
    today_log = next((l for l in logs if l.log_date == date.today()), None)
    return render_template("app/mood.html", logs=logs, moods=MOODS, today_log=today_log)


# ── Calendar ─────────────────────────────────────────────────────────────
@bp.route("/calendar")
@profile_required
def calendar():
    p = current_user.profile
    today = date.today()
    year = to_int(request.args.get("y"), today.year, 2020, 2100)
    month = to_int(request.args.get("m"), today.month, 1, 12)
    days, offset = tracking.calendar_month(current_user.id, year, month, p.daily_calories, p.daily_protein)
    prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    return render_template("app/calendar.html", days=days, offset=offset, first=date(year, month, 1),
                           prev_m=prev_m, next_m=next_m, today=today)


# ── Nutrients ────────────────────────────────────────────────────────────
@bp.route("/nutrients")
@profile_required
def nutrients():
    report = tracking.micro_report(current_user.id, current_user.profile.gender)
    full = has_feature(current_user, "micros_full")
    if not full:
        report["items"] = [i for i in report["items"] if i["key"] == "iron"] + \
                          [dict(i, locked=True) for i in report["items"] if i["key"] != "iron"]
    return render_template("app/nutrients.html", report=report, full=full)


# ── Achievements ─────────────────────────────────────────────────────────
@bp.route("/achievements")
@profile_required
def achievements():
    items, streak = tracking.achievements(current_user.id, current_user.profile)
    return render_template("app/achievements.html", items=items, streak=streak)


@bp.route("/api/today")
@login_required
def api_today():
    p = current_user.profile
    if not p:
        abort(404)
    t = tracking.day_totals(current_user.id, date.today())
    return jsonify({"kcal": round(t["kcal"]), "protein": round(t["protein"], 1),
                    "kcal_target": p.daily_calories, "protein_target": p.daily_protein,
                    "water": tracking.water_today(current_user.id), "water_goal": p.water_goal_ml})
