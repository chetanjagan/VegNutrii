"""Meal planner.

Picks breakfast, lunch, snack and dinner for each day so that the day lands
close to the calorie target, meets protein, stays within budget, respects the
diet mode / allergies / cooking time, and avoids repeating meals in a week.

It is a small local search (random restarts + coordinate descent). It runs in
well under 100 ms per week on a laptop and needs no extra dependencies.
"""
import math
import random
from collections import Counter, defaultdict

from ..data.foods import AISLE_OF, AISLES, COMPONENTS
from ..data.meals import MEALS, NUTRIENTS
from .nutrition import excluded_tags

SLOTS = ("breakfast", "lunch", "snack", "dinner")
ALL_SLOTS = SLOTS + ("extra",)  # "extra" is an optional second snack for high targets
SCALE_MIN, SCALE_MAX = 0.75, 1.5
VRAT_DISHES = {"sabudana_curd", "kuttu_cheela_curd", "rajgira_paratha_raita", "vrat_milk_fruit", "samak_aloo_curd", "kuttu_paneer"}


def _candidates(slot, excluded, cooking_time, cuisine, fasting):
    pool = [m for m in MEALS.values() if slot in m["slots"] and not (m["tags"] & excluded)]
    if fasting:
        fasting_pool = [m for m in pool if "fasting" in m["tags"]]
        pool = fasting_pool or pool
    quick = [m for m in pool if m["mins"] <= cooking_time]
    # Cuisine is a soft preference (see _score), so every eligible meal stays in the pool
    return quick if len(quick) >= 3 else pool


def _scale_for(total_kcal, target_kcal):
    if total_kcal <= 0:
        return 1.0
    s = target_kcal / total_kcal
    s = min(max(s, SCALE_MIN), SCALE_MAX)
    return round(s * 20) / 20  # nearest 0.05


def _score(combo, ctx, used):
    kcal = sum(m["kcal"] for m in combo)
    pro = sum(m["protein"] for m in combo)
    cost = sum(m["cost"] for m in combo)
    s = _scale_for(kcal, ctx["kcal"])
    kcal, pro, cost = kcal * s, pro * s, cost * s
    score = abs(kcal - ctx["kcal"]) / ctx["kcal"]
    score += 2.0 * max(0.0, ctx["protein"] - pro) / max(ctx["protein"], 1)
    if ctx["budget"]:
        score += 1.5 * max(0.0, cost - ctx["budget"]) / ctx["budget"]
    keys = [m["key"] for m in combo]
    score += 0.6 * (len(keys) - len(set(keys)))  # same dish twice in one day
    for i, m in enumerate(combo):
        score += 0.18 * used.get(m["key"], 0)
        # Prefer the user's own cuisine for main meals; snacks are mostly pan-Indian anyway
        is_snack = i in (2, 4)
        if m["cuisine"] == "any":
            score += 0.0 if is_snack else 0.08
        elif m["cuisine"] != ctx["cuisine"]:
            score += 0.15
        if m["key"] in VRAT_DISHES and not ctx.get("fasting_today"):
            score += 0.15
    return score, s


def _best_day(cands, ctx, used, rng, restarts=12):
    best, best_score, best_scale = None, math.inf, 1.0
    for _ in range(restarts):
        combo = [rng.choice(cands[slot]) for slot in SLOTS]
        score, scale = _score(combo, ctx, used)
        improved = True
        while improved:
            improved = False
            for i, slot in enumerate(SLOTS):
                for alt in cands[slot]:
                    if alt is combo[i]:
                        continue
                    trial = combo[:i] + [alt] + combo[i + 1:]
                    t_score, t_scale = _score(trial, ctx, used)
                    if t_score + 1e-9 < score:
                        combo, score, scale, improved = trial, t_score, t_scale, True
        if score < best_score:
            best, best_score, best_scale = combo, score, scale
    return best, best_scale


def planning_context(profile, *, use_budget=True, use_fasting=True):
    return {
        "kcal": profile.daily_calories,
        "protein": profile.daily_protein,
        "budget": profile.daily_budget if use_budget else 0,
        "cuisine": profile.cuisine,
        "cooking_time": profile.cooking_time,
        "excluded": excluded_tags(profile.diet_mode, profile.allergy_list),
        "fasting_weekdays": profile.fasting_weekdays if use_fasting else [],
    }


def _cands_for(ctx, fasting):
    return {slot: _candidates(slot, ctx["excluded"], ctx["cooking_time"], ctx["cuisine"], fasting) for slot in SLOTS}


def _needs_extra(combo, scale, ctx):
    kcal = sum(m["kcal"] for m in combo) * scale
    pro = sum(m["protein"] for m in combo) * scale
    return kcal < ctx["kcal"] * 0.93 or pro < ctx["protein"] * 0.9


def plan_day(ctx, day, used=None, seed=None):
    rng = random.Random(seed)
    used = used or {}
    fasting = day.weekday() in ctx["fasting_weekdays"]
    ctx = {**ctx, "fasting_today": fasting}
    cands = _cands_for(ctx, fasting)
    combo, scale = _best_day(cands, ctx, used, rng)
    meals = {slot: combo[i]["key"] for i, slot in enumerate(SLOTS)}
    if _needs_extra(combo, scale, ctx):
        best = min(((_score(combo + [alt], ctx, used), alt) for alt in cands["snack"] if alt is not combo[2]),
                   key=lambda t: t[0][0], default=None)
        if best and best[0][0] < _score(combo, ctx, used)[0]:
            (_, scale), alt = best
            meals["extra"] = alt["key"]
    return {"meals": meals, "scale": scale, "fasting": fasting}


def plan_days(ctx, days, used=None, seed=None):
    """Plan consecutive days, discouraging repeats across the whole range."""
    used = Counter(used or {})
    plans = []
    for i, day in enumerate(days):
        p = plan_day(ctx, day, used, seed=None if seed is None else f"{seed}-{i}")
        used.update(p["meals"].values())
        plans.append(p)
    return plans


def swap_slot(ctx, day, plan, slot, seed=None):
    """Replace one meal with a good alternative, keeping the rest of the day."""
    rng = random.Random(seed)
    fasting = plan.get("fasting", False)
    ctx = {**ctx, "fasting_today": fasting}
    cands = _cands_for(ctx, fasting)["snack" if slot == "extra" else slot]
    current = plan["meals"].get(slot)
    others = [MEALS[k] for s, k in plan["meals"].items() if s != slot and k in MEALS]
    scored = []
    for alt in cands:
        if alt["key"] == current:
            continue
        sc, scale = _score(others + [alt], ctx, {})
        scored.append((sc, scale, alt))
    if not scored:
        return plan
    scored.sort(key=lambda t: t[0])
    sc, scale, alt = rng.choice(scored[:4])
    new = {"meals": dict(plan["meals"]), "scale": scale, "fasting": fasting}
    new["meals"][slot] = alt["key"]
    return new


def describe(plan):
    """Expand a stored plan into display values (scaled portions)."""
    scale = plan.get("scale", 1.0)
    out = {"scale": scale, "fasting": plan.get("fasting", False), "meals": {}, "totals": {n: 0.0 for n in NUTRIENTS}}
    for slot in ALL_SLOTS:
        meal = MEALS.get(plan["meals"].get(slot))
        if not meal:
            continue
        view = {"key": meal["key"], "name": meal["name"], "mins": meal["mins"], "tags": sorted(meal["tags"]),
                "parts": [(COMPONENTS[c]["name"], COMPONENTS[c]["serving"], round(q * scale, 2)) for c, q in meal["parts"]]}
        for n in NUTRIENTS:
            view[n] = round(meal[n] * scale, 1)
            out["totals"][n] += meal[n] * scale
        out["meals"][slot] = view
    out["totals"] = {k: round(v, 1) for k, v in out["totals"].items()}
    return out


def grocery_list(plans, multiplier=1.0):
    """Aggregate raw ingredients for a list of stored plans, grouped by aisle."""
    totals = defaultdict(float)
    for plan in plans:
        scale = plan.get("scale", 1.0) * multiplier
        for slot in ALL_SLOTS:
            meal = MEALS.get(plan["meals"].get(slot))
            if not meal:
                continue
            for ckey, qty in meal["parts"]:
                for item, amount in COMPONENTS[ckey]["grocery"].items():
                    totals[item] += amount * qty * scale
    grouped = {aisle: [] for aisle in AISLES}
    for item, amount in totals.items():
        grouped.setdefault(AISLE_OF.get(item, "Other"), []).append((_clean_name(item), _fmt_amount(item, amount)))
    return {aisle: sorted(items) for aisle, items in grouped.items() if items}


def _clean_name(item):
    return item.replace(" (pcs)", "").replace(" (ml)", "")


def _fmt_amount(item, amount):
    if item.endswith("(pcs)"):
        return f"{math.ceil(amount)} pcs"
    unit_small, unit_big = ("ml", "L") if item.endswith("(ml)") else ("g", "kg")
    if amount >= 1000:
        return f"{math.ceil(amount / 100) / 10:g} {unit_big}"
    return f"{max(50, math.ceil(amount / 50) * 50)} {unit_small}"
