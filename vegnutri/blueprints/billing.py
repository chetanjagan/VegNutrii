import json

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import limiter
from ..models import Payment
from ..services import billing as svc
from ..services.plans import FEATURE_NAMES, PLANS

bp = Blueprint("billing", __name__)


@bp.route("/pricing")
def pricing():
    return render_template("pricing.html", plans=PLANS, features=FEATURE_NAMES,
                           configured=svc.is_configured(), demo=svc.demo_mode())


@bp.route("/api/billing/order", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def create_order():
    data = request.get_json(silent=True) or {}
    plan, period = data.get("plan"), data.get("period")
    try:
        payment = svc.create_order(current_user, plan, period)
    except svc.BillingError as exc:
        return jsonify({"error": "billing", "message": str(exc)}), 400
    return jsonify({
        "order_id": payment.order_id, "amount": payment.amount_paise, "currency": "INR",
        "key": current_app.config["RAZORPAY_KEY_ID"], "demo": svc.demo_mode(),
        "name": current_app.config["APP_NAME"],
        "description": f"{PLANS[plan]['name']} plan, {'1 month' if period == 'month' else '1 year'}",
        "prefill": {"email": current_user.email, "name": current_user.username},
    })


@bp.route("/api/billing/verify", methods=["POST"])
@login_required
def verify():
    data = request.get_json(silent=True) or {}
    order_id = data.get("razorpay_order_id", "")
    payment = Payment.query.filter_by(order_id=order_id, user_id=current_user.id).first()
    if not payment:
        return jsonify({"error": "unknown_order", "message": "We couldn't find that order."}), 404
    if svc.demo_mode() and order_id.startswith("order_demo_"):
        svc.activate(payment, "pay_demo_" + order_id[-8:])
        return jsonify({"ok": True})
    if not svc.verify_checkout_signature(order_id, data.get("razorpay_payment_id", ""), data.get("razorpay_signature", "")):
        current_app.logger.warning("Bad checkout signature for order %s", order_id)
        return jsonify({"error": "signature", "message": "Payment couldn't be verified. If money was deducted, "
                        "it will be confirmed automatically or refunded. Contact support if not."}), 400
    svc.activate(payment, data.get("razorpay_payment_id"))
    return jsonify({"ok": True})


@bp.route("/api/billing/webhook", methods=["POST"])
def webhook():
    raw = request.get_data()
    if not svc.verify_webhook_signature(raw, request.headers.get("X-Razorpay-Signature", "")):
        return jsonify({"error": "bad_signature"}), 400
    try:
        event = json.loads(raw)
    except ValueError:
        return jsonify({"error": "bad_json"}), 400
    status = svc.handle_webhook(event)
    current_app.logger.info("Razorpay webhook %s: %s", event.get("event"), status)
    return jsonify({"status": status})


@bp.route("/billing/success")
@login_required
def success():
    flash(f"You're on {PLANS[current_user.active_plan]['name']}. Thank you for supporting {current_app.config['APP_NAME']}!", "success")
    return redirect(url_for("tracker.dashboard"))
