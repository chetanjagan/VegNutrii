"""Photo, voice and text food recognition. Groq is mocked; no network calls."""
import json

import pytest
from conftest import onboard, register

from vegnutri.data.foods import COMPONENTS
from vegnutri.models import AIUsage, MealLog
from vegnutri.services import coach, quicklog

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2000
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 2000


class FakeResp:
    def __init__(self, status, data=None, text=""):
        self.status_code, self._data, self.text = status, data or {}, text

    def json(self):
        return self._data


def chat_reply(obj, think=False):
    content = ("<think>let me look</think>" if think else "") + "Sure! " + json.dumps(obj)
    return FakeResp(200, {"choices": [{"message": {"content": content}}]})


ROTI_DAL = {"items": [{"key": "roti", "name": "Roti", "servings": 3},
                      {"key": "dal_tadka", "name": "Dal", "servings": 1, "kcal": 99999},
                      {"key": None, "name": "Mango lassi", "kcal": 260, "protein": 7, "carbs": 45, "fat": 6}],
            "note": "Looks like lunch"}


@pytest.fixture
def groq(app, monkeypatch):
    app.config["GROQ_API_KEY"] = "gsk_test"
    coach._model_cache.update(at=0.0, ids=None)
    calls, responses = [], []

    def fake_post(url, json=None, headers=None, timeout=None, files=None, data=None):
        calls.append({"url": url, "json": json, "headers": headers, "files": files, "data": data})
        return responses.pop(0)

    monkeypatch.setattr(coach.requests, "get", lambda *a, **k: FakeResp(500))
    monkeypatch.setattr(quicklog.requests, "post", fake_post)
    return calls, responses


def test_text_recognition_uses_our_database_not_ai_numbers(user, user_client, groq):
    calls, responses = groq
    responses.append(chat_reply(ROTI_DAL))
    r = user_client.post("/api/quick-log/text", json={"text": "teen roti aur dal, ek mango lassi"})
    body = r.get_json()
    assert r.status_code == 200 and len(body["items"]) == 3
    roti, dal, lassi = body["items"]
    assert roti["key"] == "roti" and roti["servings"] == 3 and roti["per"]["kcal"] == COMPONENTS["roti"]["kcal"]
    assert dal["per"]["kcal"] == COMPONENTS["dal_tadka"]["kcal"]  # the AI's 99999 is ignored
    assert lassi["estimate"] and lassi["per"]["kcal"] == 260 and "estimate" in lassi["warning"]
    assert "roti | Roti / chapati" in calls[0]["json"]["messages"][0]["content"]  # catalogue in prompt
    assert body["smart_left"] == 4


def test_photo_sends_image_to_vision_model(user, user_client, groq):
    calls, responses = groq
    responses.append(chat_reply({"items": [{"key": "idli", "servings": 1.5}]}, think=True))
    r = user_client.post("/api/quick-log/photo", data={"image": (__import__("io").BytesIO(JPEG), "meal.jpg")},
                         content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["items"][0]["key"] == "idli"
    content = calls[0]["json"]["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert calls[0]["json"]["model"] == quicklog.VISION_MODELS[0]
    assert AIUsage.query.filter_by(kind="photo").count() == 1


def test_photo_rejects_non_images_and_huge_files(user, user_client, groq):
    io = __import__("io")
    r = user_client.post("/api/quick-log/photo", data={"image": (io.BytesIO(b"<html>not a photo"), "x.jpg")},
                         content_type="multipart/form-data")
    assert r.status_code == 400 and "JPEG" in r.get_json()["message"]
    big = b"\xff\xd8\xff" + b"0" * (quicklog.MAX_IMAGE_BYTES + 1)
    r = user_client.post("/api/quick-log/photo", data={"image": (io.BytesIO(big), "x.jpg")},
                         content_type="multipart/form-data")
    assert r.status_code == 413
    assert AIUsage.query.count() == 0  # rejected uploads don't use quota


def test_voice_transcribes_then_recognises(user, user_client, groq):
    calls, responses = groq
    responses += [FakeResp(200, {"text": "do roti aur dal"}), chat_reply(ROTI_DAL)]
    io = __import__("io")
    r = user_client.post("/api/quick-log/voice",
                         data={"audio": (io.BytesIO(b"\x1aE\xdf\xa3" + b"0" * 5000), "meal.webm", "audio/webm")},
                         content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 200 and body["transcript"] == "do roti aur dal"
    assert calls[0]["url"].endswith("/audio/transcriptions") and calls[0]["data"]["model"] == "whisper-large-v3"
    assert "Content-Type" not in calls[0]["headers"]  # multipart boundary must be set by requests
    assert AIUsage.query.filter_by(kind="voice").count() == 1


def test_unsupported_audio_format(user, user_client, groq):
    io = __import__("io")
    r = user_client.post("/api/quick-log/voice", data={"audio": (io.BytesIO(b"0" * 5000), "x.exe", "application/x-msdownload")},
                         content_type="multipart/form-data")
    assert r.status_code == 400 and "format" in r.get_json()["message"]


def test_diet_conflict_is_flagged(app, client, groq):
    calls, responses = groq
    register(client)
    onboard(client, diet_mode="jain")
    responses.append(chat_reply({"items": [{"key": "aloo_gobi", "servings": 1}, {"key": "lauki_sabzi", "servings": 1}]}))
    items = client.post("/api/quick-log/text", json={"text": "aloo gobi and lauki"}).get_json()["items"]
    assert items[0]["warning"] == "Contains onion or garlic and root vegetables, which your diet settings exclude."
    assert items[1]["warning"] is None


def test_bad_json_and_model_fallback(user, user_client, groq):
    calls, responses = groq
    responses += [FakeResp(200, {"choices": [{"message": {"content": "I think it's dal"}}]}), chat_reply(ROTI_DAL)]
    r = user_client.post("/api/quick-log/text", json={"text": "dal"})
    assert r.status_code == 200 and len(calls) == 2


def test_failures_do_not_use_quota(user, user_client, groq):
    calls, responses = groq
    responses += [FakeResp(500)] * 4
    r = user_client.post("/api/quick-log/text", json={"text": "dal"})
    assert r.status_code == 502 and AIUsage.query.count() == 0


def test_daily_limits_and_upgrade_hint(user, user_client, groq):
    from vegnutri.extensions import db
    for _ in range(2):
        db.session.add(AIUsage(user_id=user.id, kind="photo"))
    db.session.commit()
    io = __import__("io")
    r = user_client.post("/api/quick-log/photo", data={"image": (io.BytesIO(PNG), "m.png")},
                         content_type="multipart/form-data")
    assert r.status_code == 429 and "upgrade" in r.get_json()


def test_save_recomputes_known_foods_and_keeps_estimates(user, user_client):
    items = [{"key": "roti", "name": "anything", "servings": 3, "per": {"kcal": 1}},
             {"key": None, "name": "Mango lassi", "servings": 1, "per": {"kcal": 260, "protein": 7, "carbs": 45, "fat": 6}},
             {"key": None, "name": "", "servings": 1, "per": {"kcal": 50}}]
    r = user_client.post("/api/quick-log/save", json={"items": items, "meal_type": "lunch"})
    assert r.status_code == 200 and r.get_json()["count"] == 2
    roti = MealLog.query.filter_by(name="Roti / chapati").first()
    assert roti.calories == COMPONENTS["roti"]["kcal"] * 3 and roti.iron > 0 and roti.meal_type == "lunch"
    assert MealLog.query.filter_by(name="Mango lassi").first().calories == 260


def test_save_requires_items(user_client):
    assert user_client.post("/api/quick-log/save", json={"items": []}).status_code == 400


def test_page_renders_and_mic_allowed(user_client):
    r = user_client.get("/quick-log")
    assert r.status_code == 200 and "microphone=(self)" in r.headers["Permissions-Policy"]


def test_quick_log_requires_login(client):
    assert client.post("/api/quick-log/text", json={"text": "dal"}).status_code in (302, 401)
