"""AI coach backed by Groq (OpenAI-compatible API), using the server's API key."""
from datetime import date, datetime

import requests
from flask import current_app

from ..data.meals import CUISINES
from ..extensions import db
from ..models import ChatMessage
from .nutrition import ALLERGIES, DIET_MODES, GOALS
from .plans import plan_of

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Tried in order. If the first hits its free daily/minute limit (429), the next one answers.
DEFAULT_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


class CoachError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


def is_configured():
    return bool(current_app.config.get("GROQ_API_KEY"))


def used_today(user_id):
    start = datetime.combine(date.today(), datetime.min.time())
    return ChatMessage.query.filter(ChatMessage.user_id == user_id, ChatMessage.role == "user",
                                    ChatMessage.created_at >= start).count()


def quota(user):
    limit = plan_of(user)["coach_daily"]
    used = used_today(user.id)
    return {"limit": limit, "used": used, "left": max(limit - used, 0)}


def _models():
    """Model order comes from GROQ_MODELS (comma-separated) or the defaults above."""
    custom = [m.strip() for m in (current_app.config.get("GROQ_MODELS") or "").split(",") if m.strip()]
    return custom or DEFAULT_MODELS


def system_prompt(user, profile, today_totals, plan_view, gaps):
    diet = DIET_MODES.get(profile.diet_mode, DIET_MODES["vegetarian"])[0]
    allergies = ", ".join(ALLERGIES.get(a, a) for a in profile.allergy_list) or "none"
    meals = ""
    if plan_view:
        meals = "\n".join(f"  {slot.title()}: {m['name']}" for slot, m in plan_view["meals"].items())
    gap_text = ", ".join(gaps) if gaps else "none flagged"
    return f"""You are the VegNutri coach: a warm, practical nutrition coach for Indian vegetarians.

User: {user.username}
Diet: {diet} (STRICT: never suggest anything this diet excludes, including hidden ingredients)
Allergies/intolerances: {allergies} (never suggest these)
Cuisine they prefer: {CUISINES.get(profile.cuisine, profile.cuisine)}
Age {profile.age}, {profile.gender}, {profile.height:g} cm, {profile.weight:g} kg. Goal: {GOALS.get(profile.goal, profile.goal)}
Daily targets: {profile.daily_calories} kcal, {profile.daily_protein} g protein. Usual cook time: {profile.cooking_time} min.
Budget: {"Rs " + str(profile.daily_budget) + " per day" if profile.daily_budget else "not set"}

Today so far: {today_totals['kcal']:.0f} kcal, {today_totals['protein']:.0f} g protein eaten.
Remaining: {max(profile.daily_calories - today_totals['kcal'], 0):.0f} kcal, {max(profile.daily_protein - today_totals['protein'], 0):.0f} g protein.
Today's plan:
{meals or "  (no plan generated)"}
Nutrients running low this week: {gap_text}

How to respond:
- Be concrete: name Indian dishes and portions (katori, roti count, grams).
- Keep answers to 2-4 short paragraphs unless they ask for a full recipe.
- Use simple language. Reply in the user's language if they write in Hindi, Kannada, Tamil, etc.

Safety rules (always follow):
- You are not a doctor. Do not diagnose, and do not advise on medication doses.
- For pregnancy, diabetes, kidney/liver/heart disease, thyroid conditions, PCOS treatment,
  or anyone under 18, give general guidance only and recommend seeing a doctor or registered dietitian.
- Never recommend eating below 1200 kcal/day, fasting for weight loss beyond their religious practice,
  or extreme diets.
- If the user mentions bingeing, purging, fear of eating, or severe restriction, respond with care,
  do not give calorie or weight numbers, and gently suggest speaking to a doctor or counsellor.
- For B12 or iron supplements, say they're common for vegetarians and suggest a blood test with a doctor."""


def chat(user, message, context_prompt):
    key = current_app.config.get("GROQ_API_KEY")
    if not key:
        raise CoachError("The coach isn't available right now.", 503)

    history = (ChatMessage.query.filter_by(user_id=user.id, cleared=False)
               .order_by(ChatMessage.created_at.desc()).limit(16).all())[::-1]
    messages = [{"role": "system", "content": context_prompt}]
    messages += [{"role": m.role if m.role in ("user", "assistant") else "user", "content": m.content}
                 for m in history]
    messages.append({"role": "user", "content": message})

    db.session.add(ChatMessage(user_id=user.id, role="user", content=message))
    db.session.commit()

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    rate_limited = False
    for model in _models():
        payload = {"model": model, "messages": messages, "temperature": 0.6,
                   "max_tokens": 900, "top_p": 0.9}
        try:
            r = requests.post(GROQ_URL, json=payload, headers=headers, timeout=40)
        except requests.RequestException as exc:
            current_app.logger.warning("Groq %s request error: %s", model, exc)
            continue
        if r.status_code == 429:
            rate_limited = True
            continue
        if r.status_code >= 400:
            current_app.logger.warning("Groq %s HTTP %s: %s", model, r.status_code, r.text[:300])
            continue
        try:
            reply = (r.json()["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, ValueError):
            reply = ""
        if not reply:
            reply = "I couldn't answer that one. Try asking it a different way."
        db.session.add(ChatMessage(user_id=user.id, role="assistant", content=reply))
        db.session.commit()
        return reply

    if rate_limited:
        raise CoachError("The coach is busy. Try again in a few seconds.", 429)
    raise CoachError("The coach couldn't reply. Try again in a minute.", 502)
