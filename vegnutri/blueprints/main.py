import hmac

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user

from ..data.meals import MEALS
from ..services.plans import PLANS

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("tracker.dashboard"))
    return render_template("landing.html", plans=PLANS, meal_count=len(MEALS))


@bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")


@bp.route("/terms")
def terms():
    return render_template("legal/terms.html")


@bp.route("/disclaimer")
def disclaimer():
    return render_template("legal/disclaimer.html")


@bp.route("/refunds")
def refunds():
    return render_template("legal/refunds.html")


@bp.route("/manifest.webmanifest")
def manifest():
    resp = send_from_directory(current_app.static_folder, "manifest.webmanifest")
    resp.mimetype = "application/manifest+json"
    return resp


@bp.route("/sw.js")
def service_worker():
    # Served from the root so it can control the whole site
    resp = send_from_directory(current_app.static_folder, "js/sw.js")
    resp.headers["Cache-Control"] = "no-cache"
    resp.mimetype = "application/javascript"
    return resp


@bp.route("/robots.txt")
def robots():
    allow = "".join(f"Allow: {p}\n" for p in ("/$", "/privacy", "/terms", "/refunds", "/disclaimer", "/pricing",
                                                "/meals", "/meal-plans", "/static/"))
    body = f"User-agent: *\n{allow}Disallow: /\nSitemap: {current_app.config['APP_URL']}/sitemap.xml\n"
    return body, 200, {"Content-Type": "text/plain"}


@bp.route("/sitemap.xml")
def sitemap():
    base = current_app.config["APP_URL"]
    from .explore import sitemap_paths
    paths = ["/", "/pricing", "/privacy", "/terms"] + sitemap_paths()
    urls = "".join(f"<url><loc>{base}{p}</loc></url>" for p in paths)
    return (f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
            200, {"Content-Type": "application/xml"})


@bp.route("/healthz")
def healthz():
    from sqlalchemy import text

    from ..extensions import db
    db.session.execute(text("SELECT 1"))
    return {"status": "ok"}


@bp.route("/email/unsubscribe/<token>", methods=["GET", "POST"])
def unsubscribe(token):
    """One-click unsubscribe from the weekly email (no login needed)."""
    from ..extensions import db
    from ..services.digest import user_from_token
    user = user_from_token(token)
    if not user:
        abort(404)
    if request.method == "POST":
        user.weekly_digest = False
        db.session.commit()
        flash("You won't get weekly progress emails any more. You can turn them back on in Account.", "info")
        return redirect(url_for("main.index"))
    return render_template("unsubscribe.html", token=token)


@bp.route("/tasks/weekly-digest", methods=["POST"])
def weekly_digest_task():
    """Called by the scheduled GitHub Action. Protected by the TASK_TOKEN shared secret."""
    from ..services.digest import send_batch
    token = current_app.config.get("TASK_TOKEN", "")
    if not token or not hmac.compare_digest(request.headers.get("X-Task-Token", ""), token):
        abort(404)  # look like nothing is here
    from ..services.mailer import mail_configured
    if not mail_configured():
        return jsonify({"error": "No email provider is set (BREVO_API_KEY or MAIL_SERVER), so no emails can be sent."}), 503
    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify(send_batch(limit))
