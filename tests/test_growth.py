"""Trials, coupons, referrals and the weekly email."""
import hashlib
import hmac
import json
from datetime import date, timedelta

import pytest
from conftest import onboard, register

from vegnutri.extensions import db
from vegnutri.models import Coupon, MealLog, Payment, User, utcnow
from vegnutri.services import billing, digest


def _sig(secret, msg):
    return hmac.new(secret.encode(), msg if isinstance(msg, bytes) else msg.encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def trials(app):
    app.config.update(TRIAL_DAYS=7, REFERRAL_TRIAL_DAYS=14, REFERRAL_REWARD_DAYS=30)


def _pay(user, plan="pro", period="year", order="order_X", coupon=None):
    q = billing.quote(plan, period, coupon)
    p = Payment(user_id=user.id, plan=plan, period=period, amount_paise=q["amount"], order_id=order,
                coupon_code=q["coupon"], discount_paise=q["discount"])
    db.session.add(p)
    db.session.commit()
    billing.activate(p, "pay_" + order)
    return p


# ── Trials ──────────────────────────────────────────────────────────────
def test_new_user_gets_7_day_trial(app, client, trials):
    register(client)
    u = User.query.first()
    assert u.on_trial and u.active_plan == "pro" and u.trial_days_left in (7, 8)


def test_trial_off_when_zero(app, client):
    register(client)
    assert User.query.first().active_plan == "free"


def test_trial_expires_to_free(app, client, trials):
    register(client)
    u = User.query.first()
    u.plan_expires_at = utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert u.active_plan == "free" and u.trial_days_left is None


def test_paying_during_trial_keeps_trial_days(app, client, trials):
    register(client)
    u = User.query.first()
    trial_end = u.plan_expires_at
    _pay(u, "family", "year")  # even a different plan stacks after the trial
    assert not u.on_trial and u.active_plan == "family"
    assert u.plan_expires_at >= trial_end + timedelta(days=365)


def test_trial_users_not_counted_as_paying(app, client, trials):
    register(client)
    client.post("/logout")
    admin = User(username="boss", email="boss@example.com", is_admin=True)
    admin.set_password("password123")
    db.session.add(admin)
    db.session.commit()
    client.post("/login", data=dict(email="boss@example.com", password="password123"))
    html = client.get("/admin/").get_data(as_text=True)
    assert "On a trial" in html


# ── Coupons ─────────────────────────────────────────────────────────────
def _coupon(**kw):
    c = Coupon(**{"code": "DIWALI25", "percent_off": 25, "plans": "pro,family", **kw})
    db.session.add(c)
    db.session.commit()
    return c


def test_coupon_discount_math(app):
    _coupon()
    q = billing.quote("pro", "year", "diwali25 ")
    assert q["coupon"] == "DIWALI25" and q["amount"] == 52400 and q["discount"] == 69900 - 52400  # Rs 699 -> Rs 524
    for plan, period in (("pro", "month"), ("pro", "year"), ("family", "year")):
        assert billing.quote(plan, period, "DIWALI25")["amount"] % 100 == 0  # whole rupees only


@pytest.mark.parametrize("kw,msg", [
    ({"active": False}, "isn't valid"),
    ({"expires_at": utcnow() - timedelta(days=1)}, "expired"),
    ({"max_uses": 1, "uses": 1}, "fully used"),
    ({"plans": "family"}, "doesn't apply"),
])
def test_coupon_rejections(app, kw, msg):
    _coupon(**kw)
    q = billing.quote("pro", "year", "DIWALI25")
    assert q["discount"] == 0 and msg in q["error"]


def test_coupon_never_below_razorpay_minimum(app):
    _coupon(code="BIG", percent_off=90)
    q = billing.quote("pro", "month", "BIG")
    assert q["amount"] >= billing.MIN_AMOUNT_PAISE


def test_coupon_use_counted_once_and_webhook_accepts_discounted_amount(user, client):
    c = _coupon()
    q = billing.quote("pro", "year", "DIWALI25")
    p = Payment(user_id=user.id, plan="pro", period="year", amount_paise=q["amount"], order_id="order_C",
                coupon_code="DIWALI25", discount_paise=q["discount"])
    db.session.add(p)
    db.session.commit()
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": "pay_C", "order_id": "order_C", "amount": q["amount"]}}}}).encode()
    headers = {"X-Razorpay-Signature": _sig("whsec_test", body)}
    for _ in range(2):
        client.post("/api/billing/webhook", data=body, headers=headers, content_type="application/json")
    assert user.active_plan == "pro" and c.uses == 1


def test_quote_endpoint(user_client, app):
    _coupon()
    r = user_client.post("/api/billing/quote", json={"coupon": "DIWALI25"}).get_json()
    assert r["applied"]["percent_off"] == 25 and r["prices"]["pro-year"]["amount"] < 69900
    bad = user_client.post("/api/billing/quote", json={"coupon": "NOPE"}).get_json()
    assert bad["applied"] is None and bad["error"]


def test_invalid_coupon_blocks_order(user_client, app):
    r = user_client.post("/api/billing/order", json={"plan": "pro", "period": "year", "coupon": "NOPE"})
    assert r.status_code == 400 and "isn't valid" in r.get_json()["message"]


def test_admin_creates_and_toggles_coupon(app, client):
    admin = User(username="boss", email="boss@example.com", is_admin=True)
    admin.set_password("password123")
    db.session.add(admin)
    db.session.commit()
    client.post("/login", data=dict(email="boss@example.com", password="password123"))
    client.post("/admin/coupons", data=dict(code="navratri 30!", percent_off="30", plan_pro="on", max_uses="100",
                                            expires_at="2030-10-12"))
    c = Coupon.query.first()
    assert c.code == "NAVRATRI30" and c.plans == "pro" and c.max_uses == 100 and c.expires_at.year == 2030
    client.post(f"/admin/coupons/{c.id}/toggle")
    assert not c.active


def test_non_admin_cannot_create_coupons(user_client):
    assert user_client.post("/admin/coupons", data=dict(code="FREE", percent_off="90")).status_code == 403
    assert Coupon.query.count() == 0


# ── Referrals ───────────────────────────────────────────────────────────
def _referrer(client):
    register(client, username="ravi", email="ravi@example.com")
    onboard(client)
    client.get("/account/")
    code = User.query.filter_by(username="ravi").first().referral_code
    client.post("/logout")
    return code


def test_referral_link_gives_longer_trial(app, client, trials):
    code = _referrer(client)
    r = client.get(f"/r/{code.lower()}")
    assert r.status_code == 302
    assert b"ravi invited you" in client.get("/register").data
    register(client, username="friend", email="friend@example.com")
    friend = User.query.filter_by(username="friend").first()
    ravi = User.query.filter_by(username="ravi").first()
    assert friend.referred_by_id == ravi.id and friend.trial_days_left in (14, 15)


def test_unknown_referral_code_ignored(app, client):
    client.get("/r/NOTREAL")
    register(client)
    assert User.query.first().referred_by_id is None


def test_referrer_rewarded_on_first_payment_only(app, client):
    code = _referrer(client)
    client.get(f"/r/{code}")
    register(client, username="friend", email="friend@example.com")
    ravi = User.query.filter_by(username="ravi").first()
    friend = User.query.filter_by(username="friend").first()
    assert ravi.active_plan == "free"
    _pay(friend, order="order_1")
    assert ravi.active_plan == "pro" and ravi.referral_rewards == 1
    first_expiry = ravi.plan_expires_at
    _pay(friend, order="order_2")  # renewal: no second reward
    assert ravi.referral_rewards == 1 and ravi.plan_expires_at == first_expiry


def test_paid_referrer_gets_time_added_to_their_plan(app, client):
    code = _referrer(client)
    ravi = User.query.filter_by(username="ravi").first()
    _pay(ravi, "family", "year", order="order_R")
    before = ravi.plan_expires_at
    client.get(f"/r/{code}")
    register(client, username="friend", email="friend@example.com")
    _pay(User.query.filter_by(username="friend").first(), order="order_F")
    assert ravi.active_plan == "family" and ravi.plan_expires_at == before + timedelta(days=30)


def test_account_page_shows_invite_link(user_client, user):
    html = user_client.get("/account/").get_data(as_text=True)
    assert f"/r/{user.referral_code}" in html and "wa.me" in html


# ── Weekly email ────────────────────────────────────────────────────────
@pytest.fixture
def outbox(app, monkeypatch):
    sent = []
    app.config["BREVO_API_KEY"] = "test"
    monkeypatch.setattr(digest, "send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def _log_week(user, protein):
    for i in range(1, 8):
        db.session.add(MealLog(user_id=user.id, name="Dal", meal_type="lunch", calories=1500, protein=protein,
                               iron=8, log_date=date.today() - timedelta(days=i)))
    db.session.commit()


def test_task_endpoint_requires_token(client, app):
    assert client.post("/tasks/weekly-digest").status_code == 404
    assert client.post("/tasks/weekly-digest", headers={"X-Task-Token": "wrong"}).status_code == 404
    app.config["TASK_TOKEN"] = ""
    assert client.post("/tasks/weekly-digest", headers={"X-Task-Token": ""}).status_code == 404


def test_task_endpoint_refuses_without_email_provider(client):
    r = client.post("/tasks/weekly-digest", headers={"X-Task-Token": "task-secret"})
    assert r.status_code == 503


def test_weekly_email_content_and_once_per_week(user, user_client, outbox):
    _log_week(user, protein=90)
    r = user_client.post("/tasks/weekly-digest", headers={"X-Task-Token": "task-secret"}).get_json()
    assert r["sent"] == 1 and r["remaining"] == 0
    to, subject, body = outbox[0]
    assert to == user.email and "protein on target 7 of 7 days" in subject
    assert "Iron averaged" in body and "/email/unsubscribe/" in body
    user_client.post("/tasks/weekly-digest", headers={"X-Task-Token": "task-secret"})
    assert len(outbox) == 1  # not again the same week


def test_inactive_users_are_skipped(user, user_client, outbox):
    r = user_client.post("/tasks/weekly-digest", headers={"X-Task-Token": "task-secret"}).get_json()
    assert r["sent"] == 0 and r["skipped"] == 1 and not outbox


def test_unsubscribe_link(user, client, outbox):
    token = digest.unsubscribe_token(user)
    assert client.get(f"/email/unsubscribe/{token}").status_code == 200
    assert user.weekly_digest  # GET only shows the confirm page (mail scanners follow links)
    client.post(f"/email/unsubscribe/{token}")
    assert not user.weekly_digest
    assert client.get("/email/unsubscribe/forged").status_code == 404


def test_account_toggle_for_weekly_email(user, user_client):
    user_client.post("/account/preferences", data={})
    assert not user.weekly_digest
    user_client.post("/account/preferences", data={"weekly_digest": "on"})
    assert user.weekly_digest
