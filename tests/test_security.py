from conftest import onboard, register

from vegnutri import create_app
from vegnutri.config import TestConfig
from vegnutri.extensions import db
from vegnutri.models import MealLog


def test_security_headers(client):
    r = client.get("/")
    csp = r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp and "nonce-" in csp and "unsafe-inline" not in csp.split("style-src")[0]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_csrf_enforced_when_enabled():
    class CsrfConfig(TestConfig):
        WTF_CSRF_ENABLED = True
    app = create_app(CsrfConfig)
    with app.app_context():
        db.create_all()
        r = app.test_client().post("/login", data=dict(email="x@example.com", password="y"))
        assert r.status_code == 400


def test_users_cannot_touch_each_others_data(app, client):
    register(client)
    onboard(client)
    client.post("/log", data=dict(source="manual", name="Secret dal", calories="200", meal_type="lunch"))
    log_id = MealLog.query.first().id
    client.post("/logout")
    register(client, username="mallory", email="m@example.com")
    onboard(client)
    assert client.post(f"/log/{log_id}/delete").status_code == 404
    assert db.session.get(MealLog, log_id) is not None
    assert b"Secret dal" not in client.get("/log").data


def test_log_values_come_from_server_not_client(user_client):
    user_client.post("/log", data=dict(source="food", food_key="moong_dal", servings="2", meal_type="lunch",
                                       calories="99999"))
    log = MealLog.query.first()
    assert log.calories == 360 and log.protein == 24
