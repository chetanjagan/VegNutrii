"""Public, indexable pages: the meal library and sample meal plans by diet.

These bring in search traffic ("jain meal plan", "high protein south indian breakfast")
and show what VegNutri does before anyone signs up.
"""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, abort, current_app, render_template, request

from ..data.foods import COMPONENTS
from ..data.meals import CUISINES, MEALS
from ..services import planner
from ..services.nutrition import DIET_MODES

bp = Blueprint("explore", __name__)

RECIPES = json.loads((Path(__file__).resolve().parent.parent / "data" / "recipes.json").read_text(encoding="utf-8"))
SLOTS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snack": "Snacks"}
DIET_FILTERS = {**{k: v[0] for k, v in DIET_MODES.items()}, "vrat": "Vrat / fasting"}

# Sample plans: slug -> (title, intro, diet_mode, cuisine, fasting)
PLAN_PAGES = {
    "jain": ("Jain meal plan", "A full day of Jain meals: no onion, garlic, root vegetables, egg or honey, and still high in protein.", "jain", "gujarati", False),
    "sattvic": ("Sattvic meal plan", "Simple sattvic meals without onion or garlic, built around dal, dairy, grains and fresh vegetables.", "sattvic", "north_indian", False),
    "vegan": ("Vegan Indian meal plan", "Plant-only Indian meals with soya, tofu, dal and seeds to reach your protein without dairy.", "vegan", "south_indian", False),
    "eggetarian": ("Eggetarian meal plan", "Vegetarian Indian meals with eggs for an easy protein boost.", "eggetarian", "north_indian", False),
    "high-protein-vegetarian": ("High-protein vegetarian meal plan", "Indian vegetarian meals that reach 90 g of protein in a day from paneer, dal, curd, chana and soya.", "vegetarian", "north_indian", False),
    "navratri-vrat": ("Navratri vrat meal plan", "A fasting day of sabudana, kuttu, rajgira, samak, fruit and dairy that still keeps your protein up.", "vegetarian", "north_indian", True),
    "south-indian": ("South Indian vegetarian meal plan", "Idli, dosa, sambar, ragi and more, balanced for protein.", "vegetarian", "south_indian", False),
    "gujarati": ("Gujarati vegetarian meal plan", "Thepla, dhokla, kadhi and rotla, planned to your calories and protein.", "vegetarian", "gujarati", False),
    "maharashtrian": ("Maharashtrian vegetarian meal plan", "Poha, bhakri, varan bhaat and usal, balanced across the day.", "vegetarian", "maharashtrian", False),
    "bengali": ("Bengali vegetarian meal plan", "Khichuri, cholar dal and chhanar dalna in a balanced vegetarian day.", "vegetarian", "bengali", False),
}
SAMPLE_KCAL, SAMPLE_PROTEIN = 1900, 80


def suits(meal, diet):
    if diet == "vrat":
        return "fasting" in meal["tags"]
    return diet in DIET_MODES and not (meal["tags"] & DIET_MODES[diet][1])


def meal_diets(meal):
    return [label for key, label in DIET_FILTERS.items() if key != "vegetarian" and suits(meal, key)]


@bp.app_context_processor
def explore_helpers():
    return {"meal_diets": meal_diets, "SLOT_NAMES": SLOTS}


@bp.route("/meals")
def meals():
    diet = request.args.get("diet", "")
    cuisine = request.args.get("cuisine", "")
    slot = request.args.get("slot", "")
    items = list(MEALS.values())
    if diet in DIET_FILTERS:
        items = [m for m in items if suits(m, diet)]
    if cuisine in CUISINES:
        items = [m for m in items if m["cuisine"] in (cuisine, "any")]
    if slot in SLOTS:
        items = [m for m in items if slot in m["slots"]]
    items.sort(key=lambda m: (-m["protein"] / max(m["kcal"], 1), m["name"]))
    return render_template("explore/meals.html", items=items, diet=diet, cuisine=cuisine, slot=slot,
                           diets=DIET_FILTERS, total=len(MEALS))


@bp.route("/meals/<key>")
def meal(key):
    m = MEALS.get(key)
    if not m:
        abort(404)
    parts = [(COMPONENTS[c], q) for c, q in m["parts"]]
    similar = [x for x in MEALS.values() if x["key"] != key and set(x["slots"]) & set(m["slots"])
               and x["cuisine"] in (m["cuisine"], "any")]
    similar.sort(key=lambda x: abs(x["kcal"] - m["kcal"]))
    return render_template("explore/meal.html", meal=m, parts=parts, recipe=RECIPES.get(key),
                           similar=similar[:6], cuisine_name=CUISINES.get(m["cuisine"], "Pan-Indian"))


def sample_day(diet, cuisine, fasting):
    profile = SimpleNamespace(daily_calories=SAMPLE_KCAL, daily_protein=SAMPLE_PROTEIN, daily_budget=0, cuisine=cuisine,
                              cooking_time=30, diet_mode=diet, allergy_list=[], fasting_weekdays=[0] if fasting else [])
    ctx = planner.planning_context(profile)
    day = date(2026, 10, 12)  # a Monday, so fasting=[0] makes it a vrat day
    return planner.describe(planner.plan_day(ctx, day, seed=f"public-{diet}-{cuisine}-{fasting}"))


@bp.route("/meal-plans/<slug>")
def meal_plan_page(slug):
    if slug not in PLAN_PAGES:
        abort(404)
    title, intro, diet, cuisine, fasting = PLAN_PAGES[slug]
    plan = sample_day(diet, cuisine, fasting)
    more_key = "vrat" if fasting else diet
    more = [m for m in MEALS.values() if suits(m, more_key) and m["cuisine"] in (cuisine, "any")
            and m["key"] not in {v["key"] for v in plan["meals"].values()}]
    more.sort(key=lambda m: -m["protein"])
    return render_template("explore/plan.html", slug=slug, title=title, intro=intro, plan=plan, more=more[:8],
                           kcal=SAMPLE_KCAL, protein=SAMPLE_PROTEIN, pages=PLAN_PAGES,
                           diet_label=DIET_FILTERS["vrat" if fasting else diet])


@bp.route("/meal-plans")
def meal_plans_index():
    return render_template("explore/plans_index.html", pages=PLAN_PAGES)


def sitemap_paths():
    return (["/meals", "/meal-plans"] + [f"/meals/{k}" for k in MEALS] + [f"/meal-plans/{s}" for s in PLAN_PAGES])


def canonical(path):
    return current_app.config["APP_URL"] + path
