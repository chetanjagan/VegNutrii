"""Subscription plans, prices and feature limits. Change prices here only."""
from functools import wraps

from flask import flash, jsonify, redirect, request, url_for
from flask_login import current_user

PLANS = {
    "free": {
        "name": "Free",
        "prices": {},
        "plan_days": 3,
        "coach_daily": 5,
        "photo_daily": 2,   # photo food recognition
        "smart_daily": 5,   # voice or typed "2 roti aur dal" recognition
        "features": set(),
    },
    "pro": {
        "name": "Pro",
        "prices": {"month": 9900, "year": 69900},  # paise (Rs 99 / Rs 699)
        "plan_days": 7,
        "coach_daily": 60,
        "photo_daily": 20,
        "smart_daily": 40,
        "features": {"budget", "fasting", "micros_full", "grocery_week"},
    },
    "family": {
        "name": "Family",
        "prices": {"year": 119900},  # Rs 1,199 per year
        "plan_days": 7,
        "coach_daily": 100,
        "photo_daily": 30,
        "smart_daily": 60,
        "max_members": 4,
        "features": {"budget", "fasting", "micros_full", "grocery_week", "family"},
    },
}

PERIOD_DAYS = {"month": 31, "year": 366}

FEATURE_NAMES = {
    "budget": "Budget-based meal plans",
    "fasting": "Vrat and fasting-day plans",
    "micros_full": "Full micronutrient tracking",
    "grocery_week": "Weekly grocery list from your plan",
    "family": "Family kitchen",
}


def plan_of(user):
    return PLANS[user.active_plan if user and user.is_authenticated else "free"]


def has_feature(user, feature):
    return feature in plan_of(user)["features"]


def price_label(paise):
    rupees = paise / 100
    return f"₹{rupees:,.0f}"


def requires_feature(feature):
    """Route decorator: redirect free users to the pricing page."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_feature(current_user, feature):
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "upgrade_required", "feature": feature}), 402
                flash(f"{FEATURE_NAMES.get(feature, 'This feature')} is part of VegNutri Pro.", "info")
                return redirect(url_for("billing.pricing"))
            return fn(*args, **kwargs)
        return wrapper
    return deco
