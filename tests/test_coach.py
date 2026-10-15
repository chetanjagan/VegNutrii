"""The coach talks to Groq's OpenAI-compatible API. These tests fake the HTTP layer."""
import pytest

from vegnutri.models import ChatMessage


class FakeResp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(body)

    def json(self):
        return self._body


def ok(text):
    return FakeResp(200, {"choices": [{"message": {"role": "assistant", "content": text}}]})


@pytest.fixture
def keyed(app):
    app.config["GROQ_API_KEY"] = "gsk_test_key"
    return app


def test_coach_reply_and_request_shape(keyed, user, user_client, monkeypatch):
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, json=json, headers=headers)
        return ok("Have dal and 2 rotis.")

    monkeypatch.setattr("vegnutri.services.coach.requests.post", fake_post)
    r = user_client.post("/api/coach", json={"message": "dinner ideas?"})
    assert r.status_code == 200 and r.get_json()["reply"] == "Have dal and 2 rotis."
    assert seen["url"].startswith("https://api.groq.com/openai/v1/")
    assert seen["headers"]["Authorization"] == "Bearer gsk_test_key"
    assert seen["json"]["messages"][0]["role"] == "system"
    assert seen["json"]["messages"][-1] == {"role": "user", "content": "dinner ideas?"}
    assert ChatMessage.query.filter_by(user_id=user.id, role="assistant").count() == 1


def test_falls_back_to_next_model_on_429(keyed, user_client, monkeypatch):
    tried = []

    def fake_post(url, json=None, headers=None, timeout=None):
        tried.append(json["model"])
        return FakeResp(429) if len(tried) == 1 else ok("fallback answer")

    monkeypatch.setattr("vegnutri.services.coach.requests.post", fake_post)
    r = user_client.post("/api/coach", json={"message": "hi"})
    assert r.get_json()["reply"] == "fallback answer"
    assert tried == ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def test_all_models_rate_limited(keyed, user_client, monkeypatch):
    monkeypatch.setattr("vegnutri.services.coach.requests.post", lambda *a, **k: FakeResp(429))
    r = user_client.post("/api/coach", json={"message": "hi"})
    assert r.status_code == 429


def test_no_key_means_coach_off(user_client):
    r = user_client.post("/api/coach", json={"message": "hi"})
    assert r.status_code == 503
