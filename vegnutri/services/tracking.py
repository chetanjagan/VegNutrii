"""Aggregates over a user's logs: daily totals, streaks, achievements, micronutrient gaps."""
import calendar as calmod
import json
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func

from ..extensions import db
from ..models import CustomFood, MealLog, MealPlan, MoodLog, WaterLog, WeightLog
from .nutrition import MICRO_LABELS, RDA

TIPS = json.loads((Path(__file__).resolve().parent.parent / "data" / "tips.json").read_text(encoding="utf-8"))
NUTR = ("calories", "protein", "carbs", "fat", "fiber", "iron", "calcium", "b12", "zinc")


def tip_of_day(day=None):
    day = day or date.today()
    return TIPS[day.timetuple().tm_yday % len(TIPS)]


def day_totals(user_id, day):
    row = db.session.query(*[func.coalesce(func.sum(getattr(MealLog, n)), 0) for n in NUTR]).filter(
        MealLog.user_id == user_id, MealLog.log_date == day).one()
    t = dict(zip(NUTR, (float(v) for v in row)))
    t["kcal"] = t["calories"]
    return t


def daily_series(user_id, days, field="protein"):
    start = date.today() - timedelta(days=days - 1)
    col = getattr(MealLog, field)
    rows = dict(db.session.query(MealLog.log_date, func.sum(col)).filter(
        MealLog.user_id == user_id, MealLog.log_date >= start).group_by(MealLog.log_date).all())
    labels, values = [], []
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%d %b"))
        values.append(round(float(rows.get(d) or 0), 1))
    return labels, values


def water_today(user_id, day=None):
    day = day or date.today()
    return int(db.session.query(func.coalesce(func.sum(WaterLog.amount_ml), 0)).filter(
        WaterLog.user_id == user_id, WaterLog.log_date == day).scalar())


def water_series(user_id, days=7):
    start = date.today() - timedelta(days=days - 1)
    rows = dict(db.session.query(WaterLog.log_date, func.sum(WaterLog.amount_ml)).filter(
        WaterLog.user_id == user_id, WaterLog.log_date >= start).group_by(WaterLog.log_date).all())
    return ([(start + timedelta(days=i)).strftime("%a") for i in range(days)],
            [int(rows.get(start + timedelta(days=i)) or 0) for i in range(days)])


def _protein_days(user_id, target):
    rows = db.session.query(MealLog.log_date, func.sum(MealLog.protein)).filter(
        MealLog.user_id == user_id).group_by(MealLog.log_date).all()
    return {d for d, p in rows if (p or 0) >= target}, len(rows)


def streak(user_id, protein_target):
    hit, logged_days = _protein_days(user_id, protein_target * 0.8)
    current, check = 0, date.today()
    if check not in hit:
        check -= timedelta(days=1)  # today isn't over yet
    while check in hit:
        current += 1
        check -= timedelta(days=1)
    longest = run = 0
    prev = None
    for d in sorted(hit):
        run = run + 1 if prev and (d - prev).days == 1 else 1
        longest = max(longest, run)
        prev = d
    return {"current": current, "longest": longest, "days_logged": logged_days, "protein_days": len(hit)}


ACHIEVEMENTS = [
    ("streak_3", "Sprouting", "Hit your protein goal 3 days in a row", "streak", 3),
    ("streak_7", "Full week", "Hit your protein goal 7 days in a row", "streak", 7),
    ("streak_14", "Two strong weeks", "A 14-day protein streak", "streak", 14),
    ("streak_30", "Habit for life", "A 30-day protein streak", "streak", 30),
    ("log_1", "First entry", "Log your first meal", "logs", 1),
    ("log_50", "Regular", "Log 50 meals", "logs", 50),
    ("log_200", "Devoted", "Log 200 meals", "logs", 200),
    ("pro_7", "Protein week", "Reach your protein goal on 7 days", "protein_days", 7),
    ("pro_30", "Protein month", "Reach your protein goal on 30 days", "protein_days", 30),
    ("water_7", "Well watered", "Reach your water goal on 7 days", "water_days", 7),
    ("weight_10", "Steady scale", "Log your weight 10 times", "weights", 10),
    ("custom_1", "Home chef", "Add a dish of your own", "custom", 1),
    ("mood_7", "Checked in", "Log your mood on 7 days", "moods", 7),
    ("plan_1", "Planner", "Create your first meal plan", "plans", 1),
]


def achievements(user_id, profile):
    s = streak(user_id, profile.daily_protein)
    water_rows = db.session.query(WaterLog.log_date, func.sum(WaterLog.amount_ml)).filter(
        WaterLog.user_id == user_id).group_by(WaterLog.log_date).all()
    counts = {
        "streak": s["longest"],
        "protein_days": s["protein_days"],
        "logs": MealLog.query.filter_by(user_id=user_id).count(),
        "water_days": sum(1 for _, ml in water_rows if (ml or 0) >= profile.water_goal_ml),
        "weights": WeightLog.query.filter_by(user_id=user_id).count(),
        "custom": CustomFood.query.filter_by(user_id=user_id).count(),
        "moods": MoodLog.query.filter_by(user_id=user_id).count(),
        "plans": MealPlan.query.filter_by(user_id=user_id).count(),
    }
    out = []
    for key, name, desc, metric, target in ACHIEVEMENTS:
        cur = min(counts[metric], target)
        out.append({"key": key, "name": name, "desc": desc, "current": cur, "target": target,
                    "unlocked": cur >= target, "pct": int(cur / target * 100)})
    return out, s


def micro_report(user_id, gender, days=7):
    """Average daily intake over logged days vs ICMR-NIN reference intakes."""
    start = date.today() - timedelta(days=days - 1)
    rows = db.session.query(MealLog.log_date, *[func.sum(getattr(MealLog, n)) for n in MICRO_LABELS]).filter(
        MealLog.user_id == user_id, MealLog.log_date >= start).group_by(MealLog.log_date).all()
    rda = RDA["female" if gender == "female" else "male"]
    logged = len(rows)
    report = []
    for i, key in enumerate(MICRO_LABELS):
        avg = sum(float(r[i + 1] or 0) for r in rows) / logged if logged else 0
        pct = int(avg / rda[key] * 100) if rda[key] else 0
        label, unit, advice = MICRO_LABELS[key]
        report.append({"key": key, "label": label, "unit": unit, "avg": round(avg, 1), "target": rda[key],
                       "pct": pct, "low": logged >= 3 and pct < 70, "advice": advice})
    return {"days_logged": logged, "items": report}


def calendar_month(user_id, year, month, kcal_target, protein_target):
    first = date(year, month, 1)
    last = date(year, month, calmod.monthrange(year, month)[1])
    rows = {d: (c or 0, p or 0) for d, c, p in db.session.query(
        MealLog.log_date, func.sum(MealLog.calories), func.sum(MealLog.protein)).filter(
        MealLog.user_id == user_id, MealLog.log_date.between(first, last)).group_by(MealLog.log_date).all()}
    days = []
    for n in range(1, last.day + 1):
        d = date(year, month, n)
        cal, pro = rows.get(d, (0, 0))
        if d not in rows:
            status = "none"
        elif pro >= protein_target * 0.8 and kcal_target * 0.8 <= cal <= kcal_target * 1.15:
            status = "great"
        elif pro >= protein_target * 0.8 or cal >= kcal_target * 0.7:
            status = "good"
        else:
            status = "logged"
        days.append({"date": d, "day": n, "status": status, "kcal": int(cal), "protein": round(float(pro), 1)})
    return days, first.weekday()
