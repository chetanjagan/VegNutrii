"""Groq coach tests. The Groq API is mocked; no network calls."""
import pytest

from vegnutri.models import ChatMessage
from vegnutri.services import coach


class FakeResp:
    def __init__(self, status, data=None, text=""):
        self.status_code, self._data, self.text = status, data or {}, text

    def json(self):
        return self._data


MODELS = FakeResp(200, {"data": [{"id": "llama-3.3-70b-versatile", "active": True},
                                 {"id": "llama-3.1-8b-instant", "active": True}]})


def reply(text):
    return FakeResp(200, {"choices": [{"message": {"role": "assistant", "content": text}}]})


@pytest.fixture
def groq(app, monkeypatch):
    app.config["GROQ_API_KEY"] = "gsk_test"
    coach._model_cache.update(at=0.0, ids=None)
    calls = []
    responses = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return responses.pop(0)

    monkeypatch.setattr(coach.requests, "get", lambda *a, **k: MODELS)
    monkeypatch.setattr(coach.requests, "post", fake_post)
    return calls, responses


def test_successful_reply_uses_openai_format(user, user_client, groq):
    calls, responses = groq
    responses.append(reply("Have paneer bhurji with 2 rotis."))
    r = user_client.post("/api/coach", json={"message": "Dinner idea?"})
    assert r.status_code == 200 and "paneer" in r.get_json()["reply"]
    sent = calls[0]
    assert sent["url"].endswith("/openai/v1/chat/completions")
    assert sent["headers"]["Authorization"] == "Bearer gsk_test"
    assert "python-requests" not in sent["headers"]["User-Agent"]
    assert sent["json"]["model"] == "llama-3.3-70b-versatile"
    assert sent["json"]["messages"][0]["role"] == "system"
    assert "Vegetarian" in sent["json"]["messages"][0]["content"]
    assert sent["json"]["messages"][-1] == {"role": "user", "content": "Dinner idea?"}
    assert ChatMessage.query.count() == 2


def test_falls_back_to_next_model(user, user_client, groq):
    calls, responses = groq
    responses += [FakeResp(400, text='{"error":{"code":"model_decommissioned"}}'), reply("ok")]
    r = user_client.post("/api/coach", json={"message": "hi"})
    assert r.status_code == 200
    assert [c["json"]["model"] for c in calls] == ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def test_failures_do_not_use_quota(user, user_client, groq):
    calls, responses = groq
    responses += [FakeResp(500), FakeResp(500)]
    r = user_client.post("/api/coach", json={"message": "hi"})
    assert r.status_code == 502
    assert ChatMessage.query.count() == 0
    assert coach.quota(user)["used"] == 0


def test_bad_key_stops_immediately(user, user_client, groq):
    calls, responses = groq
    responses.append(FakeResp(401, text="invalid api key"))
    r = user_client.post("/api/coach", json={"message": "hi"})
    assert r.status_code == 503 and len(calls) == 1


def test_rate_limit_message(user, user_client, groq):
    calls, responses = groq
    responses += [FakeResp(429), FakeResp(429)]
    r = user_client.post("/api/coach", json={"message": "hi"})
    assert r.status_code == 429 and "busy" in r.get_json()["message"]


def test_history_is_sent_back(user, user_client, groq):
    calls, responses = groq
    responses += [reply("first answer"), reply("second answer")]
    user_client.post("/api/coach", json={"message": "first"})
    user_client.post("/api/coach", json={"message": "second"})
    msgs = calls[1]["json"]["messages"]
    assert [m["content"] for m in msgs[1:]] == ["first", "first answer", "second"]


def test_model_override(app, user, user_client, groq):
    calls, responses = groq
    app.config["GROQ_MODEL"] = "llama-3.1-8b-instant"
    responses.append(reply("ok"))
    user_client.post("/api/coach", json={"message": "hi"})
    assert calls[0]["json"]["model"] == "llama-3.1-8b-instant"


def test_coach_check_reports_missing_key(app):
    app.config["GROQ_API_KEY"] = ""
    with app.app_context():
        assert "not set" in coach.diagnose()[0]
