"""Razorpay payments (Orders API + Checkout), verified server-side.

Flow:
 1. create_order() makes a Razorpay order and a Payment row (status=created).
 2. The browser opens Razorpay Checkout; on success it posts the ids + signature.
 3. verify_checkout_signature() checks the signature, then activate() upgrades the user.
 4. The webhook (payment.captured / order.paid) calls activate() too, so the
    upgrade still happens if the user closes the tab. activate() is idempotent.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

import requests
from flask import current_app

from ..extensions import db
from ..models import Coupon, Payment, User, utcnow
from .plans import PERIOD_DAYS, PLANS

API = "https://api.razorpay.com/v1"


class BillingError(Exception):
    pass


def is_configured():
    cfg = current_app.config
    return bool(cfg["RAZORPAY_KEY_ID"] and cfg["RAZORPAY_KEY_SECRET"])


def demo_mode():
    cfg = current_app.config
    return cfg["DEMO_BILLING"] and cfg["DEBUG"] and not is_configured()


MIN_AMOUNT_PAISE = 100  # Razorpay's minimum order is Rs 1


def price_for(plan, period):
    try:
        return PLANS[plan]["prices"][period]
    except KeyError:
        raise BillingError("Unknown plan or billing period.")


def find_coupon(code, plan):
    """Return (coupon, None) if the code can be used for this plan, else (None, reason)."""
    code = (code or "").strip().upper()
    if not code:
        return None, None
    c = Coupon.query.filter_by(code=code).first()
    if not c or not c.active:
        return None, "That code isn't valid."
    if c.expires_at and c.expires_at < utcnow():
        return None, "That code has expired."
    if c.max_uses is not None and c.uses >= c.max_uses:
        return None, "That code has been fully used."
    if plan not in c.plans.split(","):
        return None, f"That code doesn't apply to the {PLANS[plan]['name']} plan."
    return c, None


def quote(plan, period, code=None):
    """Price after any coupon: {'price', 'discount', 'amount', 'coupon', 'error'} in paise."""
    price = price_for(plan, period)
    coupon, error = find_coupon(code, plan)
    discount = 0
    if coupon:
        # Charge a whole number of rupees so the shown price is exactly what's charged
        amount = round(price * (100 - coupon.percent_off) / 100 / 100) * 100
        discount = price - max(amount, MIN_AMOUNT_PAISE)
    return {"price": price, "discount": discount, "amount": price - discount,
            "coupon": coupon.code if coupon else None, "percent_off": coupon.percent_off if coupon else 0,
            "error": error}


def create_order(user, plan, period, coupon_code=None):
    q = quote(plan, period, coupon_code)
    if q["error"]:
        raise BillingError(q["error"])
    amount = q["amount"]
    receipt = f"vn_{user.id}_{secrets.token_hex(6)}"
    if demo_mode():
        order_id = "order_demo_" + secrets.token_hex(8)
    else:
        if not is_configured():
            raise BillingError("Payments are not set up yet. Add Razorpay keys to the environment.")
        cfg = current_app.config
        try:
            resp = requests.post(
                f"{API}/orders",
                auth=(cfg["RAZORPAY_KEY_ID"], cfg["RAZORPAY_KEY_SECRET"]),
                json={"amount": amount, "currency": "INR", "receipt": receipt,
                      "notes": {"user_id": str(user.id), "plan": plan, "period": period}},
                timeout=15,
            )
        except requests.RequestException as exc:
            current_app.logger.error("Razorpay unreachable: %s", exc)
            raise BillingError("Couldn't reach the payment provider. Try again in a minute.")
        if resp.status_code >= 300:
            current_app.logger.error("Razorpay order failed: %s %s", resp.status_code, resp.text[:300])
            raise BillingError("Couldn't start the payment. Try again in a minute.")
        order_id = resp.json()["id"]
    payment = Payment(user_id=user.id, plan=plan, period=period, amount_paise=amount, order_id=order_id,
                      coupon_code=q["coupon"], discount_paise=q["discount"])
    db.session.add(payment)
    db.session.commit()
    return payment


def _hmac(secret, message):
    return hmac.new(secret.encode(), message.encode() if isinstance(message, str) else message, hashlib.sha256).hexdigest()


def verify_checkout_signature(order_id, payment_id, signature):
    secret = current_app.config["RAZORPAY_KEY_SECRET"]
    if not secret or not signature:
        return False
    return hmac.compare_digest(_hmac(secret, f"{order_id}|{payment_id}"), signature)


def verify_webhook_signature(raw_body, signature):
    secret = current_app.config["RAZORPAY_WEBHOOK_SECRET"]
    if not secret or not signature:
        return False
    return hmac.compare_digest(_hmac(secret, raw_body), signature)


def activate(payment, payment_id):
    """Mark a payment as paid and extend the user's plan. Safe to call twice."""
    if payment.status == "paid":
        return False
    payment.status = "paid"
    payment.payment_id = payment_id
    payment.paid_at = utcnow()
    if payment.coupon_code:
        coupon = Coupon.query.filter_by(code=payment.coupon_code).first()
        if coupon:
            coupon.uses += 1
    user = db.session.get(User, payment.user_id) if payment.user_id else None
    if user:
        first_payment = not Payment.query.filter(Payment.user_id == user.id, Payment.status == "paid",
                                                 Payment.id != payment.id).first()
        now = utcnow()
        start = now
        still_running = user.plan_expires_at and user.plan_expires_at > now
        if still_running and (user.plan == payment.plan or user.on_trial):
            start = user.plan_expires_at  # renewing, or buying during a trial: paid time starts after it
        user.plan = payment.plan
        user.plan_expires_at = start + timedelta(days=PERIOD_DAYS[payment.period])
        user.on_trial = False
        if first_payment and user.referred_by_id:
            _reward_referrer(user.referred_by_id)
    db.session.commit()
    return True


def _reward_referrer(referrer_id):
    """The inviter gets free Pro time when someone they invited pays for the first time."""
    referrer = db.session.get(User, referrer_id)
    if not referrer:
        return
    days = timedelta(days=current_app.config.get("REFERRAL_REWARD_DAYS", 30))
    now = utcnow()
    if referrer.is_paid and not referrer.on_trial:
        referrer.plan_expires_at += days  # keep their Pro or Family, just longer
    else:
        base = referrer.plan_expires_at if referrer.on_trial and referrer.plan_expires_at and referrer.plan_expires_at > now else now
        referrer.plan = "pro"
        referrer.plan_expires_at = base + days
        referrer.on_trial = False
    referrer.referral_rewards += 1


def handle_webhook(event):
    """Process a verified webhook event dict. Returns a short status string."""
    name = event.get("event", "")
    payload = event.get("payload", {})
    if name in ("payment.captured", "order.paid"):
        entity = payload.get("payment", {}).get("entity", {})
        order_id, payment_id = entity.get("order_id"), entity.get("id")
        payment = Payment.query.filter_by(order_id=order_id).first()
        if not payment:
            return "unknown_order"
        if entity.get("amount") and int(entity["amount"]) != payment.amount_paise:
            current_app.logger.error("Amount mismatch for order %s", order_id)
            return "amount_mismatch"
        return "activated" if activate(payment, payment_id) else "already_active"
    if name == "payment.failed":
        entity = payload.get("payment", {}).get("entity", {})
        payment = Payment.query.filter_by(order_id=entity.get("order_id")).first()
        if payment and payment.status == "created":
            payment.status = "failed"
            db.session.commit()
        return "failed_recorded"
    return "ignored"
