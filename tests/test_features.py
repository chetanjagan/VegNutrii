from datetime import date

from vegnutri.extensions import db
from vegnutri.models import ChatMessage, HouseholdMember, MealLog, MealPlan, User, utcnow


def _make_paid(user, plan="pro"):
    from datetime import timedelta
    user.plan = plan
    user.plan_expires_at = utcnow() + timedelta(days=30)
    db.session.commit()


def test_free_plan_gets_three_days_pro_gets_seven(user, user_client):
    user_client.get("/plan")
    assert MealPlan.query.filter_by(user_id=user.id).count() == 3
    _make_paid(user)
    user_client.get("/plan")
    assert MealPlan.query.filter_by(user_id=user.id).count() == 7


def test_expired_plan_falls_back_to_free(user):
    from datetime import timedelta
    user.plan = "pro"
    user.plan_expires_at = utcnow() - timedelta(days=1)
    assert user.active_plan == "free"


def test_family_page_gated(user, user_client):
    r = user_client.get("/family")
    assert r.status_code == 302 and "/pricing" in r.headers["Location"]
    _make_paid(user, "family")
    assert user_client.get("/family").status_code == 200
    user_client.post("/family", data=dict(name="Ravi", age="8", height="125", weight="25", gender="male",
                                          activity_level="light", goal="fat_loss"))
    child = HouseholdMember.query.first()
    assert child.goal == "maintenance" and child.daily_calories == 1700


def test_log_planned_meal(user, user_client):
    user_client.get("/plan")
    r = user_client.post(f"/plan/{date.today().isoformat()}/log/lunch")
    assert r.status_code == 302
    assert MealLog.query.filter_by(user_id=user.id, meal_type="lunch").count() == 1


def test_coach_quota_enforced(user, user_client):
    for _ in range(5):
        db.session.add(ChatMessage(user_id=user.id, role="user", content="q"))
    db.session.commit()
    r = user_client.post("/api/coach", json={"message": "one more"})
    assert r.status_code == 429 and r.get_json()["upgrade"] is True


def test_clearing_chat_keeps_quota(user, user_client):
    for _ in range(3):
        db.session.add(ChatMessage(user_id=user.id, role="user", content="q"))
    db.session.commit()
    user_client.post("/coach/clear")
    from vegnutri.services.coach import quota
    assert quota(user)["used"] == 3


def test_profile_change_rebuilds_future_plans(user, user_client):
    from conftest import onboard
    user_client.get("/plan")
    onboard(user_client, diet_mode="jain")
    user_client.get("/plan")
    from vegnutri.data.meals import MEALS
    for row in MealPlan.query.filter_by(user_id=user.id):
        for key in row.data["meals"].values():
            assert not ({"onion_garlic", "root"} & MEALS[key]["tags"])


def test_export_and_delete_account(user, user_client):
    user_client.post("/log", data=dict(source="manual", name="Dal", calories="200", meal_type="lunch"))
    data = user_client.get("/account/export").get_json()
    assert data["account"]["email"] == "asha@example.com" and data["meal_logs"]
    assert user_client.post("/account/delete", data=dict(password="wrong")).status_code == 302
    assert User.query.count() == 1
    user_client.post("/account/delete", data=dict(password="password123"))
    assert User.query.count() == 0 and MealLog.query.count() == 0


def test_public_pages_render(client):
    for url in ("/", "/pricing", "/privacy", "/terms", "/refunds", "/disclaimer", "/login", "/register"):
        assert client.get(url).status_code == 200, url
