"""Import users and history from a VegNutri v3 database (the old single-file app's nutrition.db).

Usage:
    python scripts/import_v3_sqlite.py path/to/nutrition.db [--dry-run]

Reads DATABASE_URL from the environment / .env for the NEW database, which must already be
migrated (`flask --app wsgi db upgrade`). Safe to run twice: users whose email already exists
are skipped.

What is imported: users (passwords keep working, old SHA-256 hashes are upgraded at next login),
profiles (targets recalculated with the v4 formula), meal, weight, water and mood logs, custom
foods and coach chat history.
What is NOT imported: stored Gemini API keys (v4 uses one server key; the old keys should be
considered exposed and users can revoke them), and old meal plans (v4 regenerates them).
"""
import argparse
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from vegnutri import create_app  # noqa: E402
from vegnutri.data.meals import CUISINES  # noqa: E402
from vegnutri.extensions import db  # noqa: E402
from vegnutri.models import (ChatMessage, CustomFood, MealLog, MoodLog, Profile, User, WaterLog,  # noqa: E402
                             WeightLog)
from vegnutri.services.nutrition import ACTIVITY, GOALS, calculate_targets, water_goal_ml  # noqa: E402

MOODS = {"great": "great", "happy": "great", "excellent": "great", "good": "good", "okay": "okay", "ok": "okay",
         "neutral": "okay", "meh": "okay", "sad": "low", "low": "low", "tired": "low", "stressed": "stressed",
         "anxious": "stressed", "angry": "stressed"}
ALLERGY_WORDS = {"peanut": "peanut", "groundnut": "peanut", "nut": "nuts", "almond": "nuts", "cashew": "nuts",
                 "gluten": "gluten", "wheat": "gluten", "soy": "soy", "soya": "soy", "dairy": "dairy",
                 "milk": "dairy", "lactose": "dairy", "sesame": "sesame", "til": "sesame", "coconut": "coconut"}


def _rows(conn, table, user_id=None):
    try:
        if user_id is None:
            return conn.execute(f"SELECT * FROM {table}").fetchall()
        return conn.execute(f"SELECT * FROM {table} WHERE user_id=?", (user_id,)).fetchall()
    except sqlite3.OperationalError:
        return []  # table didn't exist in that version


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return date.today()


def _dt(value):
    try:
        return datetime.fromisoformat(str(value).replace("T", " ")[:19])
    except (TypeError, ValueError):
        return datetime.now()


def _allergies(text):
    text = (text or "").lower()
    found = {tag for word, tag in ALLERGY_WORDS.items() if word in text}
    if "peanut" in found and text.count("nut") == text.count("peanut"):
        found.discard("nuts")  # "peanut" alone shouldn't also exclude tree nuts
    return ",".join(sorted(found))


def _get(row, key, default=None):
    return row[key] if key in row.keys() and row[key] is not None else default


def import_db(path, dry_run=False):
    old = sqlite3.connect(path)
    old.row_factory = sqlite3.Row
    stats = {"users": 0, "skipped": 0, "meal_logs": 0, "weights": 0, "water": 0, "moods": 0, "foods": 0, "chats": 0}

    for u in _rows(old, "users"):
        email = (u["email"] or "").strip().lower()
        if not email or User.query.filter_by(email=email).first():
            stats["skipped"] += 1
            continue
        username = u["username"]
        if User.query.filter_by(username=username).first():
            username = f"{username}_{u['id']}"
        user = User(username=username[:40], email=email, password_hash=u["password"],
                    created_at=_dt(_get(u, "created_at")), accepted_terms_at=None)
        db.session.add(user)
        db.session.flush()
        stats["users"] += 1

        for p in _rows(old, "profiles", u["id"])[:1]:
            age, height, weight = _get(p, "age", 30), _get(p, "height", 165.0), _get(p, "weight", 65.0)
            gender = "female" if _get(p, "gender") == "female" else "male"
            goal = _get(p, "goal") if _get(p, "goal") in GOALS else "maintenance"
            activity = _get(p, "activity_level") if _get(p, "activity_level") in ACTIVITY else "light"
            kcal, protein = calculate_targets(age, height, weight, gender, goal, activity)
            cuisine = _get(p, "cuisine_preference")
            db.session.add(Profile(
                user_id=user.id, age=age, height=height, weight=weight, gender=gender, goal=goal,
                activity_level=activity, cuisine=cuisine if cuisine in CUISINES else "north_indian",
                diet_mode="vegetarian", allergies=_allergies(_get(p, "allergies")),
                cooking_time=_get(p, "cooking_time", 30), daily_calories=kcal, daily_protein=protein,
                water_goal_ml=water_goal_ml(weight, activity)))

        for r in _rows(old, "meal_logs", u["id"]):
            db.session.add(MealLog(user_id=user.id, name=(r["meal_name"] or "Meal")[:200],
                                   meal_type=r["meal_type"] if r["meal_type"] in ("breakfast", "lunch", "snack", "dinner") else "snack",
                                   calories=_get(r, "calories", 0), protein=_get(r, "protein", 0),
                                   carbs=_get(r, "carbs", 0), fat=_get(r, "fat", 0), log_date=_day(_get(r, "log_date"))))
            stats["meal_logs"] += 1

        seen_weight_days = set()
        for r in _rows(old, "weight_logs", u["id"]):
            d = _day(_get(r, "log_date"))
            if d in seen_weight_days:
                continue
            seen_weight_days.add(d)
            db.session.add(WeightLog(user_id=user.id, weight=r["weight"], log_date=d))
            stats["weights"] += 1

        for r in _rows(old, "water_logs", u["id"]):
            db.session.add(WaterLog(user_id=user.id, amount_ml=r["amount_ml"], log_date=_day(_get(r, "log_date"))))
            stats["water"] += 1

        seen_mood_days = set()
        for r in _rows(old, "mood_logs", u["id"]):
            d = _day(_get(r, "log_date"))
            if d in seen_mood_days:
                continue
            seen_mood_days.add(d)
            db.session.add(MoodLog(user_id=user.id, mood=MOODS.get(str(r["mood"]).lower(), "okay"),
                                   energy_level=_get(r, "energy_level", 3), note=(_get(r, "note", "") or "")[:500], log_date=d))
            stats["moods"] += 1

        for r in _rows(old, "custom_foods", u["id"]):
            db.session.add(CustomFood(user_id=user.id, name=r["name"][:120], serving_size=_get(r, "serving_size", "1 serving"),
                                      calories=_get(r, "calories", 0), protein=_get(r, "protein", 0),
                                      carbs=_get(r, "carbs", 0), fat=_get(r, "fat", 0)))
            stats["foods"] += 1

        for r in _rows(old, "chat_history", u["id"]):
            db.session.add(ChatMessage(user_id=user.id, role="assistant" if r["role"] == "assistant" else "user",
                                       content=r["content"], created_at=_dt(_get(r, "created_at"))))
            stats["chats"] += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="Path to the v3 nutrition.db")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be imported without saving")
    args = parser.parse_args()
    if not Path(args.path).exists():
        sys.exit(f"File not found: {args.path}")
    app = create_app()
    with app.app_context():
        stats = import_db(args.path, args.dry_run)
    print(("Dry run, nothing saved. " if args.dry_run else "Imported. ") + ", ".join(f"{k}: {v}" for k, v in stats.items()))
    print("Ask imported users to check 'Targets and diet': v4 recalculated their targets and set diet to vegetarian.")


if __name__ == "__main__":
    main()
