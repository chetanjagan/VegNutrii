from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from vegnutri.data.foods import COMPONENTS
from vegnutri.data.meals import MEALS
from vegnutri.services import planner
from vegnutri.services.nutrition import DIET_MODES, calculate_targets

WEEK = [date(2026, 10, 12) + timedelta(days=i) for i in range(7)]


def profile(**kw):
    kcal, protein = calculate_targets(30, 165, 65, "female", "maintenance", "light")
    base = dict(daily_calories=kcal, daily_protein=protein, daily_budget=0, cuisine="north_indian", cooking_time=30,
                diet_mode="vegetarian", allergy_list=[], fasting_weekdays=[])
    base.update(kw)
    return SimpleNamespace(**base)


def test_catalogue_is_consistent():
    for meal in MEALS.values():
        assert meal["parts"], meal["key"]
        for ckey, qty in meal["parts"]:
            assert ckey in COMPONENTS and qty > 0
        assert set(meal["slots"]) <= {"breakfast", "lunch", "snack", "dinner"}


@pytest.mark.parametrize("mode", list(DIET_MODES))
@pytest.mark.parametrize("cuisine", ["north_indian", "south_indian", "gujarati", "maharashtrian", "bengali"])
def test_plans_never_break_diet_rules(mode, cuisine):
    ctx = planner.planning_context(profile(diet_mode=mode, cuisine=cuisine))
    for plan in planner.plan_days(ctx, WEEK, seed=1):
        for key in plan["meals"].values():
            assert not (MEALS[key]["tags"] & ctx["excluded"]), (mode, key)


@pytest.mark.parametrize("allergy", ["peanut", "nuts", "gluten", "soy", "dairy"])
def test_allergies_respected(allergy):
    ctx = planner.planning_context(profile(allergy_list=[allergy]))
    for plan in planner.plan_days(ctx, WEEK, seed=2):
        for key in plan["meals"].values():
            assert allergy not in MEALS[key]["tags"], key


def test_fasting_days_use_vrat_meals():
    ctx = planner.planning_context(profile(fasting_weekdays=[0, 3]))
    plans = planner.plan_days(ctx, WEEK, seed=3)
    for day, plan in zip(WEEK, plans):
        assert plan["fasting"] == (day.weekday() in (0, 3))
        if plan["fasting"]:
            for key in plan["meals"].values():
                assert "fasting" in MEALS[key]["tags"], key


def test_calories_close_to_target_and_no_same_day_repeats():
    p = profile()
    ctx = planner.planning_context(p)
    for plan in planner.plan_days(ctx, WEEK, seed=4):
        totals = planner.describe(plan)["totals"]
        assert abs(totals["kcal"] - p.daily_calories) / p.daily_calories < 0.12
        keys = list(plan["meals"].values())
        assert len(keys) == len(set(keys))


def test_budget_is_respected_when_possible():
    ctx = planner.planning_context(profile(daily_budget=180))
    plans = planner.plan_days(ctx, WEEK, seed=5)
    avg_cost = sum(planner.describe(p)["totals"]["cost"] for p in plans) / len(plans)
    assert avg_cost <= 200


def test_budget_ignored_when_feature_off():
    ctx = planner.planning_context(profile(daily_budget=50), use_budget=False)
    assert ctx["budget"] == 0


def test_swap_changes_only_that_slot_and_stays_compliant():
    ctx = planner.planning_context(profile(diet_mode="jain"))
    plan = planner.plan_day(ctx, WEEK[1], seed=6)
    new = planner.swap_slot(ctx, WEEK[1], plan, "lunch", seed=7)
    assert new["meals"]["lunch"] != plan["meals"]["lunch"]
    assert new["meals"]["breakfast"] == plan["meals"]["breakfast"]
    assert not (MEALS[new["meals"]["lunch"]]["tags"] & ctx["excluded"])


def test_grocery_list_scales_with_household():
    ctx = planner.planning_context(profile())
    plans = planner.plan_days(ctx, WEEK[:2], seed=8)
    one = planner.grocery_list(plans, 1.0)
    assert one and all(items for items in one.values())
