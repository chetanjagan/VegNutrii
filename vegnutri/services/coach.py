"""AI coach backed by Groq (OpenAI-compatible chat completions), using the server's API key."""
import time
from datetime import datetime, timedelta

import requests
from flask import current_app

from ..data.meals import CUISINES
from ..extensions import db
from ..models import ChatMessage, utcnow
from .nutrition import ALLERGIES, DIET_MODES, GOALS
from .plans import plan_of

API = "https://api.groq.com/openai/v1"
# Tried in order, skipping any the account can't see. GROQ_MODEL (env) goes first if set.
PREFERRED_MODELS = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-8b-instant", "openai/gpt-oss-20b"]
HISTORY_MESSAGES = 16
_model_cache = {"at": 0.0, "ids": None}

# The daily question quota resets at midnight India time, not UTC.
QUOTA_UTC_OFFSET = timedelta(hours=5, minutes=30)


class CoachError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


def _key():
    return (current_app.config.get("GROQ_API_KEY") or "").strip()


def is_configured():
    return bool(_key())


def _headers():
    return {
        "Authorization": f"Bearer {_key()}",
        "Content-Type": "application/json",
        # Groq sits behind Cloudflare, which can reject requests with a bare library user agent
        "User-Agent": f"{current_app.config.get('APP_NAME', 'VegNutri')}/4.0 (+{current_app.config.get('APP_URL', '')})",
    }


def _start_of_today_utc():
    local_now = utcnow() + QUOTA_UTC_OFFSET
    local_midnight = datetime.combine(local_now.date(), datetime.min.time())
    return local_midnight - QUOTA_UTC_OFFSET


def used_today(user_id):
    return ChatMessage.query.filter(ChatMessage.user_id == user_id, ChatMessage.role == "user",
                                    ChatMessage.created_at >= _start_of_today_utc()).count()


def quota(user):
    limit = plan_of(user)["coach_daily"]
    used = used_today(user.id)
    return {"limit": limit, "used": used, "left": max(limit - used, 0)}


def available_models(force=False):
    """Model ids to try, in preference order. Uses Groq's /models list (cached for an hour)."""
    preferred = list(PREFERRED_MODELS)
    override = (current_app.config.get("GROQ_MODEL") or "").strip()
    if override:
        preferred = [override] + [m for m in preferred if m != override]
    if force or not _model_cache["ids"] or time.time() - _model_cache["at"] > 3600:
        try:
            r = requests.get(f"{API}/models", headers=_headers(), timeout=10)
            if r.status_code == 200:
                _model_cache.update(at=time.time(), ids={m["id"] for m in r.json().get("data", []) if m.get("active", True)})
            else:
                current_app.logger.warning("Groq /models returned HTTP %s: %s", r.status_code, r.text[:300])
        except requests.RequestException as exc:
            current_app.logger.warning("Groq /models unreachable: %s", exc)
    ids = _model_cache["ids"]
    if not ids:
        return preferred  # couldn't list; just try them
    usable = [m for m in preferred if m in ids]
    return usable or preferred


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
- Keep answers to 2-4 short paragraphs unless they ask for a full recipe. Plain text, no markdown tables.
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


def _messages(user, message, context_prompt):
    history = (ChatMessage.query.filter_by(user_id=user.id, cleared=False)
               .order_by(ChatMessage.created_at.desc()).limit(HISTORY_MESSAGES).all())[::-1]
    msgs = [{"role": "system", "content": context_prompt}]
    msgs += [{"role": "assistant" if m.role == "assistant" else "user", "content": m.content} for m in history]
    msgs.append({"role": "user", "content": message})
    return msgs


def _payload(model, messages):
    body = {"model": model, "messages": messages, "temperature": 0.6, "top_p": 0.9,
            "max_completion_tokens": 900}
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"  # reasoning models: keep latency and token use down
        body["max_completion_tokens"] = 1600
    return body


def _extract(data):
    try:
        return (data["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""


def chat(user, message, context_prompt):
    if not is_configured():
        raise CoachError("The coach isn't available right now.", 503)

    messages = _messages(user, message, context_prompt)
    rate_limited = False
    for model in available_models():
        try:
            r = requests.post(f"{API}/chat/completions", json=_payload(model, messages), headers=_headers(), timeout=40)
        except requests.RequestException as exc:
            current_app.logger.warning("Groq %s request error: %s", model, exc)
            continue
        if r.status_code in (401, 403):
            # Same key for every model, so trying others won't help
            current_app.logger.error("Groq rejected the request (HTTP %s). Check GROQ_API_KEY. Body: %s",
                                     r.status_code, r.text[:300])
            raise CoachError("The coach isn't available right now.", 503)
        if r.status_code == 429:
            rate_limited = True
            current_app.logger.warning("Groq %s rate limited: %s", model, r.text[:200])
            continue
        if r.status_code >= 400:
            current_app.logger.warning("Groq %s HTTP %s: %s", model, r.status_code, r.text[:300])
            continue
        reply = _extract(r.json())
        if not reply:
            current_app.logger.warning("Groq %s returned an empty reply", model)
            continue
        # Save only on success, so failed attempts don't use up the daily quota
        now = utcnow()
        db.session.add(ChatMessage(user_id=user.id, role="user", content=message, created_at=now))
        db.session.add(ChatMessage(user_id=user.id, role="assistant", content=reply, created_at=now + timedelta(milliseconds=1)))
        db.session.commit()
        return reply

    if rate_limited:
        raise CoachError("The coach is busy. Try again in a few seconds.", 429)
    raise CoachError("The coach couldn't reply. Try again in a minute.", 502)


def diagnose():
    """Plain-language health check used by `flask coach-check`."""
    lines = []
    key = _key()
    if not key:
        return ["GROQ_API_KEY is not set. Add it to .env (it starts with gsk_) and restart the app."]
    lines.append(f"GROQ_API_KEY is set (starts with {key[:4]}..., {len(key)} characters).")
    if not key.startswith("gsk_"):
        lines.append("Warning: Groq keys normally start with gsk_. Check you copied the right key.")
    try:
        r = requests.get(f"{API}/models", headers=_headers(), timeout=10)
    except requests.RequestException as exc:
        return lines + [f"Can't reach api.groq.com: {exc}. Check your internet connection or firewall."]
    if r.status_code in (401, 403):
        return lines + [f"Groq rejected the key (HTTP {r.status_code}): {r.text[:200]}",
                        "Create a new key at console.groq.com/keys and update .env."]
    if r.status_code != 200:
        return lines + [f"Groq /models returned HTTP {r.status_code}: {r.text[:200]}"]
    ids = sorted(m["id"] for m in r.json().get("data", []))
    lines.append(f"Key works. {len(ids)} models available.")
    models = available_models(force=True)
    lines.append(f"Will try, in order: {', '.join(models)}")
    try:
        t = time.time()
        r = requests.post(f"{API}/chat/completions", headers=_headers(), timeout=40,
                          json=_payload(models[0], [{"role": "user", "content": "Reply with one word: ready"}]))
        if r.status_code == 200:
            lines.append(f"Test reply from {models[0]} in {time.time() - t:.1f}s: {_extract(r.json())!r}")
        else:
            lines.append(f"Test chat with {models[0]} failed, HTTP {r.status_code}: {r.text[:300]}")
    except requests.RequestException as exc:
        lines.append(f"Test chat failed: {exc}")
    return lines
