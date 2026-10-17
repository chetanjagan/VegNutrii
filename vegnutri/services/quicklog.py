"""Recognise food from a photo, a voice note or a typed sentence, using Groq.

The AI only identifies foods and portions. It maps each food to a key in our own
component database, and nutrition is always computed from that database. Foods
the catalogue doesn't have come back as clearly marked AI estimates.

Nothing uploaded is stored: photos and audio are sent to Groq and then discarded.
"""
import base64
import json
import re

import requests
from flask import current_app

from ..data.foods import COMPONENTS
from ..extensions import db
from ..models import AIUsage
from . import coach
from .nutrition import excluded_tags
from .plans import plan_of

VISION_MODELS = ["qwen/qwen3.8-27b", "qwen/qwen3.6-27b", "meta-llama/llama-4-maverick-17b-128e-instruct",
                 "meta-llama/llama-4-scout-17b-16e-instruct"]
WHISPER_MODELS = ["whisper-large-v3", "whisper-large-v3-turbo"]

MAX_IMAGE_BYTES = 3 * 1024 * 1024    # Groq caps base64 images at 4 MB; base64 adds about a third
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 500
MAX_ITEMS = 8

IMAGE_TYPES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png"}
AUDIO_EXTENSIONS = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
                    "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "video/webm": "webm"}

TAG_WORDS = {"onion_garlic": "onion or garlic", "root": "root vegetables", "egg": "egg", "dairy": "dairy",
             "gluten": "gluten", "peanut": "peanuts", "nuts": "tree nuts", "soy": "soy", "sesame": "sesame",
             "coconut": "coconut", "honey": "honey", "mushroom": "mushroom"}

KINDS = {"photo": ("photo",), "smart": ("voice", "text")}


class QuickLogError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ── Daily limits ────────────────────────────────────────────────────────
def usage(user, group):
    """{'limit', 'used', 'left'} for 'photo' or 'smart' (voice + text) today, India time."""
    limit = plan_of(user)[f"{group}_daily"]
    used = AIUsage.query.filter(AIUsage.user_id == user.id, AIUsage.kind.in_(KINDS[group]),
                                AIUsage.created_at >= coach._start_of_today_utc()).count()
    return {"limit": limit, "used": used, "left": max(limit - used, 0)}


def _check_quota(user, group):
    if usage(user, group)["left"] <= 0:
        what = "photo" if group == "photo" else "voice and typed"
        raise QuickLogError(f"You've used today's {what} recognitions. Search and log by hand, or try again tomorrow.", 429)


def _record(user, kind):
    db.session.add(AIUsage(user_id=user.id, kind=kind))
    db.session.commit()


# ── Prompting ───────────────────────────────────────────────────────────
_catalogue_cache = None


def _catalogue():
    global _catalogue_cache
    if _catalogue_cache is None:
        _catalogue_cache = "\n".join(f"{c['key']} | {c['name']} | 1 serving = {c['serving']}"
                                     for c in sorted(COMPONENTS.values(), key=lambda c: c["key"]))
    return _catalogue_cache


INSTRUCTIONS = """You identify Indian food and map it to this food catalogue (key | name | serving size):

{catalogue}

Return ONLY a JSON object, no other text:
{{"items": [{{"key": "<catalogue key, or null>", "name": "<short dish name>", "servings": <number>,
  "kcal": <number>, "protein": <number>, "carbs": <number>, "fat": <number>}}], "note": "<one short sentence, or empty>"}}

Rules:
- Prefer catalogue keys. Pick the closest catalogue dish (any dal -> the closest dal, plain chapati -> roti).
- "servings" counts catalogue servings: 3 rotis = 3 (serving is 1 piece); 4 idlis = 2 (serving is 2 pieces);
  a full katori of dal = 1; half a katori = 0.5.
- Only when key is null, fill kcal/protein/carbs/fat as your estimate for the WHOLE amount eaten. Otherwise omit them.
- If the portion isn't clear, assume a normal Indian household portion.
- At most {max_items} items. Ignore anything that isn't food or drink. If there's no food, return "items": [].
- Never invent foods that aren't there."""


def _messages_for_text(text):
    return [{"role": "system", "content": INSTRUCTIONS.format(catalogue=_catalogue(), max_items=MAX_ITEMS)},
            {"role": "user", "content": "What I ate (may be in Hindi, Hinglish, Kannada, Tamil or another Indian "
                                        f"language): {text}"}]


def _messages_for_image(data_url):
    return [{"role": "user", "content": [
        {"type": "text", "text": INSTRUCTIONS.format(catalogue=_catalogue(), max_items=MAX_ITEMS)
         + "\n\nIdentify the food in this photo of a meal."},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]}]


def _parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def _complete(models, messages, label):
    """Try models in order; return the parsed JSON object from the first that answers properly."""
    if not coach.is_configured():
        raise QuickLogError("Smart logging isn't available right now.", 503)
    rate_limited = False
    for model in models:
        body = {"model": model, "messages": messages, "temperature": 0.2, "max_completion_tokens": 1200}
        try:
            r = requests.post(f"{coach.API}/chat/completions", json=body, headers=coach._headers(), timeout=45)
        except requests.RequestException as exc:
            current_app.logger.warning("Groq %s %s request error: %s", label, model, exc)
            continue
        if r.status_code in (401, 403):
            current_app.logger.error("Groq rejected the %s request (HTTP %s): %s", label, r.status_code, r.text[:300])
            raise QuickLogError("Smart logging isn't available right now.", 503)
        if r.status_code == 429:
            rate_limited = True
            continue
        if r.status_code >= 400:
            current_app.logger.warning("Groq %s %s HTTP %s: %s", label, model, r.status_code, r.text[:300])
            continue
        parsed = _parse_json(coach._extract(r.json()))
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            return parsed
        current_app.logger.warning("Groq %s %s returned something that wasn't the expected JSON", label, model)
    if rate_limited:
        raise QuickLogError("Busy right now. Try again in a few seconds.", 429)
    raise QuickLogError("Couldn't recognise that. Try again, or search and log by hand.", 502)


# ── Turning AI output into loggable items ───────────────────────────────
def _num(value, lo, hi, default=0.0):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(v, lo), hi)


def _and_list(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def enrich(raw_items, profile):
    """Validate AI items and attach nutrition from our database. Never trusts AI numbers for known foods."""
    excluded = excluded_tags(profile.diet_mode, profile.allergy_list) if profile else set()
    out = []
    for raw in raw_items[:MAX_ITEMS]:
        if not isinstance(raw, dict):
            continue
        key = raw.get("key")
        comp = COMPONENTS.get(key) if isinstance(key, str) else None
        if comp:
            servings = round(_num(raw.get("servings"), 0.25, 6, 1.0) * 4) / 4
            conflicts = sorted(TAG_WORDS[t] for t in comp["tags"] & excluded if t in TAG_WORDS)
            out.append({
                "key": comp["key"], "name": comp["name"], "serving": comp["serving"], "servings": servings,
                "per": {n: comp[n] for n in ("kcal", "protein", "carbs", "fat")}, "estimate": False,
                "warning": f"Contains {_and_list(conflicts)}, which your diet settings exclude." if conflicts else None,
            })
        else:
            name = str(raw.get("name") or "").strip()[:120]
            if not name:
                continue
            out.append({
                "key": None, "name": name, "serving": "as eaten", "servings": 1.0,
                "per": {"kcal": round(_num(raw.get("kcal"), 0, 2500)), "protein": round(_num(raw.get("protein"), 0, 150), 1),
                        "carbs": round(_num(raw.get("carbs"), 0, 400), 1), "fat": round(_num(raw.get("fat"), 0, 200), 1)},
                "estimate": True,
                "warning": "Not in our food database, so these numbers are an AI estimate. Check them before logging.",
            })
    return out


# ── The three ways in ───────────────────────────────────────────────────
def _sniff_image(data):
    for magic, mime in IMAGE_TYPES.items():
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def from_photo(user, data):
    _check_quota(user, "photo")
    if not data:
        raise QuickLogError("Choose a photo first.")
    if len(data) > MAX_IMAGE_BYTES:
        raise QuickLogError("That photo is too large. Try a smaller one, or take a new photo in the app.", 413)
    mime = _sniff_image(data)
    if not mime:
        raise QuickLogError("That doesn't look like a JPEG, PNG or WebP photo.")
    data_url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    models = coach.pick_models(list(VISION_MODELS), current_app.config.get("GROQ_VISION_MODEL"))
    parsed = _complete(models, _messages_for_image(data_url), "vision")
    _record(user, "photo")
    return {"items": enrich(parsed["items"], user.profile), "note": str(parsed.get("note") or "")[:200]}


def transcribe(data, mimetype):
    if not data:
        raise QuickLogError("No recording received. Try again.")
    if len(data) > MAX_AUDIO_BYTES:
        raise QuickLogError("That recording is too long. Keep it under a minute.", 413)
    base_type = (mimetype or "").split(";")[0].strip().lower()
    ext = AUDIO_EXTENSIONS.get(base_type)
    if not ext:
        raise QuickLogError("That audio format isn't supported. Try recording again in Chrome or Safari.")
    if not coach.is_configured():
        raise QuickLogError("Smart logging isn't available right now.", 503)
    headers = {k: v for k, v in coach._headers().items() if k != "Content-Type"}
    models = coach.pick_models(list(WHISPER_MODELS), current_app.config.get("GROQ_WHISPER_MODEL"))
    rate_limited = False
    for model in models:
        try:
            r = requests.post(f"{coach.API}/audio/transcriptions", headers=headers, timeout=60,
                              files={"file": (f"meal.{ext}", data, base_type)},
                              data={"model": model, "response_format": "json", "temperature": "0"})
        except requests.RequestException as exc:
            current_app.logger.warning("Groq whisper %s request error: %s", model, exc)
            continue
        if r.status_code in (401, 403):
            current_app.logger.error("Groq rejected the transcription (HTTP %s): %s", r.status_code, r.text[:300])
            raise QuickLogError("Smart logging isn't available right now.", 503)
        if r.status_code == 429:
            rate_limited = True
            continue
        if r.status_code >= 400:
            current_app.logger.warning("Groq whisper %s HTTP %s: %s", model, r.status_code, r.text[:300])
            continue
        text = (r.json().get("text") or "").strip()
        if text:
            return text[:MAX_TEXT_CHARS]
        raise QuickLogError("I couldn't hear anything. Try again a little closer to the mic.")
    if rate_limited:
        raise QuickLogError("Busy right now. Try again in a few seconds.", 429)
    raise QuickLogError("Couldn't understand the recording. Try again, or type it instead.", 502)


def from_text(user, text, kind="text"):
    _check_quota(user, "smart")
    text = (text or "").strip()
    if not text:
        raise QuickLogError("Type what you ate first.")
    if len(text) > MAX_TEXT_CHARS:
        raise QuickLogError(f"Keep it under {MAX_TEXT_CHARS} characters.")
    parsed = _complete(coach.available_models(), _messages_for_text(text), kind)
    _record(user, kind)
    return {"items": enrich(parsed["items"], user.profile), "note": str(parsed.get("note") or "")[:200]}


def from_voice(user, data, mimetype):
    _check_quota(user, "smart")
    text = transcribe(data, mimetype)
    result = from_text(user, text, kind="voice")
    result["transcript"] = text
    return result


def build_logs(items):
    """Turn reviewed items from the browser into MealLog field dicts. Known foods use our database."""
    logs = []
    for item in (items or [])[:MAX_ITEMS * 2]:
        if not isinstance(item, dict):
            continue
        servings = round(_num(item.get("servings"), 0.25, 10, 1.0) * 4) / 4
        comp = COMPONENTS.get(item.get("key")) if isinstance(item.get("key"), str) else None
        if comp:
            values = {n: comp[n] * servings for n in ("protein", "carbs", "fat", "fiber", "iron", "calcium", "b12", "zinc")}
            logs.append(dict(name=comp["name"], servings=servings, calories=comp["kcal"] * servings, **values))
            continue
        name = str(item.get("name") or "").strip()[:120]
        per = item.get("per") or {}
        if not name:
            continue
        logs.append(dict(name=name, servings=servings,
                         calories=_num(per.get("kcal"), 0, 2500) * servings,
                         protein=_num(per.get("protein"), 0, 150) * servings,
                         carbs=_num(per.get("carbs"), 0, 400) * servings,
                         fat=_num(per.get("fat"), 0, 200) * servings))
    return logs


def diagnose_lines():
    """Extra lines for `flask coach-check`: which photo and speech models will be used."""
    ids = coach.listed_model_ids() or set()
    vision = coach.pick_models(list(VISION_MODELS), current_app.config.get("GROQ_VISION_MODEL"))
    whisper = coach.pick_models(list(WHISPER_MODELS), current_app.config.get("GROQ_WHISPER_MODEL"))
    lines = [f"Photo logging will try: {', '.join(vision)}",
             f"Voice logging will try: {', '.join(whisper)}"]
    if ids and not any(m in ids for m in vision):
        lines.append("Warning: none of the known vision models are on your account. Set GROQ_VISION_MODEL to a "
                     "vision model from console.groq.com/docs/vision.")
    if ids and not any(m in ids for m in whisper):
        lines.append("Warning: no Whisper model found on your account. Set GROQ_WHISPER_MODEL.")
    return lines

