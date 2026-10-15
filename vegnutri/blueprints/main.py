from flask import Blueprint, current_app, redirect, render_template, send_from_directory, url_for
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
    body = f"User-agent: *\nAllow: /$\nAllow: /privacy\nAllow: /terms\nAllow: /pricing\nDisallow: /\nSitemap: {current_app.config['APP_URL']}/sitemap.xml\n"
    return body, 200, {"Content-Type": "text/plain"}


@bp.route("/sitemap.xml")
def sitemap():
    base = current_app.config["APP_URL"]
    urls = "".join(f"<url><loc>{base}{p}</loc></url>" for p in ("/", "/pricing", "/privacy", "/terms"))
    return (f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
            200, {"Content-Type": "application/xml"})


@bp.route("/healthz")
def healthz():
    from sqlalchemy import text

    from ..extensions import db
    db.session.execute(text("SELECT 1"))
    return {"status": "ok"}
