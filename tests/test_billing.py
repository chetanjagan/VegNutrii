import hashlib
import hmac
import json

from vegnutri.models import Payment, utcnow
from vegnutri.services import billing


def _sig(secret, msg):
    return hmac.new(secret.encode(), msg if isinstance(msg, bytes) else msg.encode(), hashlib.sha256).hexdigest()


def _payment(user, plan="pro", period="year", order="order_TEST1"):
    from vegnutri.extensions import db
    p = Payment(user_id=user.id, plan=plan, period=period, amount_paise=billing.price_for(plan, period), order_id=order)
    db.session.add(p)
    db.session.commit()
    return p


def test_checkout_signature_verification(app):
    assert billing.verify_checkout_signature("order_1", "pay_1", _sig("test_secret", "order_1|pay_1"))
    assert not billing.verify_checkout_signature("order_1", "pay_1", "forged")
    assert not billing.verify_checkout_signature("order_1", "pay_2", _sig("test_secret", "order_1|pay_1"))


def test_verify_endpoint_activates_plan(user, user_client):
    p = _payment(user)
    bad = user_client.post("/api/billing/verify", json={"razorpay_order_id": p.order_id, "razorpay_payment_id": "pay_1",
                                                         "razorpay_signature": "nope"})
    assert bad.status_code == 400 and user.active_plan == "free"
    ok = user_client.post("/api/billing/verify", json={"razorpay_order_id": p.order_id, "razorpay_payment_id": "pay_1",
                                                        "razorpay_signature": _sig("test_secret", f"{p.order_id}|pay_1")})
    assert ok.status_code == 200 and user.active_plan == "pro"
    assert user.plan_expires_at > utcnow()


def _event(order_id, amount, name="payment.captured"):
    return json.dumps({"event": name, "payload": {"payment": {"entity": {"id": "pay_W", "order_id": order_id,
                                                                         "amount": amount}}}}).encode()


def test_webhook_requires_valid_signature(user, client):
    p = _payment(user)
    body = _event(p.order_id, p.amount_paise)
    r = client.post("/api/billing/webhook", data=body, headers={"X-Razorpay-Signature": "bad"},
                    content_type="application/json")
    assert r.status_code == 400 and user.active_plan == "free"


def test_webhook_activates_once(user, client):
    p = _payment(user)
    body = _event(p.order_id, p.amount_paise)
    headers = {"X-Razorpay-Signature": _sig("whsec_test", body)}
    r1 = client.post("/api/billing/webhook", data=body, headers=headers, content_type="application/json")
    first_expiry = user.plan_expires_at
    r2 = client.post("/api/billing/webhook", data=body, headers=headers, content_type="application/json")
    assert r1.get_json()["status"] == "activated" and r2.get_json()["status"] == "already_active"
    assert user.plan_expires_at == first_expiry


def test_webhook_rejects_wrong_amount(user, client):
    p = _payment(user)
    body = _event(p.order_id, 100)
    r = client.post("/api/billing/webhook", data=body, headers={"X-Razorpay-Signature": _sig("whsec_test", body)},
                    content_type="application/json")
    assert r.get_json()["status"] == "amount_mismatch" and user.active_plan == "free"


def test_renewal_stacks_time(user, client):
    p1 = _payment(user, order="order_A")
    billing.activate(p1, "pay_A")
    first = user.plan_expires_at
    p2 = _payment(user, order="order_B")
    billing.activate(p2, "pay_B")
    assert (user.plan_expires_at - first).days >= 365


def test_demo_billing_disabled_outside_debug(app):
    app.config.update(DEMO_BILLING=True, DEBUG=False)
    assert not billing.demo_mode()
