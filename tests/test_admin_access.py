"""Admins get every feature, can preview the app as any plan, and nobody else can."""
from conftest import onboard, register

from vegnutri.extensions import db
from vegnutri.models import MealPlan, User


def _admin_client(client, app):
    app.config["ADMIN_EMAILS"] = ["boss@example.com"]
    register(client, username="boss", email="boss@example.com")
    onboard(client)
    return User.query.filter_by(email="boss@example.com").first()


def test_admin_email_gets_admin_and_full_access(app, client):
    admin = _admin_client(client, app)
    assert admin.is_admin and admin.active_plan == "family" and admin.plan_expires_at is None
    assert client.get("/family").status_code == 200  # Family-only page
    client.get("/plan")
    assert MealPlan.query.filter_by(user_id=admin.id).count() == 7  # Pro/Family plan length
    assert b"Unlock with Pro" not in client.get("/nutrients").data


def test_pages_with_plan_dates_do_not_crash_for_admin(app, client):
    _admin_client(client, app)
    for url in ("/dashboard", "/account/", "/pricing", "/admin/"):
        r = client.get(url)
        assert r.status_code == 200, url
    assert b"Admin: full access" in client.get("/dashboard").data


def test_preview_as_free_shows_paywalls_then_stops(app, client):
    admin = _admin_client(client, app)
    client.post("/admin/preview", data={"plan": "free"})
    assert client.get("/family").status_code == 302  # now blocked, like a free user
    page = client.get("/nutrients").get_data(as_text=True)
    assert "Unlock with Pro" in page and "Admin preview" in page
    client.post("/admin/preview", data={"plan": "pro"})
    assert client.get("/family").status_code == 302 and b"Unlock with Pro" not in client.get("/nutrients").data
    client.post("/admin/preview", data={"plan": ""})
    assert client.get("/family").status_code == 200
    assert admin.plan == "free"  # previews never change the stored plan or billing


def test_preview_does_not_count_admin_as_paying(app, client):
    _admin_client(client, app)
    html = client.get("/admin/").get_data(as_text=True)
    assert "Plans and what they include" in html and "See as Free" in html


def test_feature_table_matches_plan_settings(app, client):
    from vegnutri.services.plans import PLANS
    _admin_client(client, app)
    html = client.get("/admin/").get_data(as_text=True)
    assert f"{PLANS['free']['plan_days']} days" in html and str(PLANS["pro"]["coach_daily"]) in html
    assert "Budget-based meal plans" in html and "Family kitchen" in html


def test_regular_users_cannot_preview_or_get_admin_access(user, user_client):
    assert user_client.post("/admin/preview", data={"plan": "family"}).status_code == 403
    assert user.active_plan == "free" and user_client.get("/family").status_code == 302
    with user_client.session_transaction() as s:
        s["admin_preview"] = "family"  # even a forged session value does nothing for non-admins
    assert user_client.get("/family").status_code == 302


def test_removing_admin_removes_access(app, client):
    admin = _admin_client(client, app)
    admin.is_admin = False
    db.session.commit()
    assert admin.active_plan == "free" and client.get("/family").status_code == 302
