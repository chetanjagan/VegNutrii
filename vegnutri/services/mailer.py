"""Email sending.

Two ways to send, checked in this order:
 1. Brevo HTTP API (BREVO_API_KEY): works over HTTPS, so it also works on hosts whose free
    tiers block outgoing SMTP ports. Free tier: 300 emails a day.
 2. SMTP (MAIL_SERVER and friends).
With neither configured, emails are written to the log instead.
"""
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

import requests
from flask import current_app


def mail_configured():
    cfg = current_app.config
    return bool(cfg.get("BREVO_API_KEY") or cfg.get("MAIL_SERVER"))


def _send_brevo(to, subject, body):
    cfg = current_app.config
    name, addr = parseaddr(cfg["MAIL_FROM"])
    try:
        r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=15,
                          headers={"api-key": cfg["BREVO_API_KEY"], "accept": "application/json"},
                          json={"sender": {"name": name or cfg["APP_NAME"], "email": addr},
                                "to": [{"email": to}], "subject": subject, "textContent": body})
    except requests.RequestException as exc:
        current_app.logger.error("Brevo unreachable sending to %s: %s", to, exc)
        return False
    if r.status_code >= 300:
        current_app.logger.error("Brevo rejected email to %s: HTTP %s %s", to, r.status_code, r.text[:300])
        return False
    return True


def _send_smtp(to, subject, body):
    cfg = current_app.config
    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15) as smtp:
            if cfg.get("MAIL_USE_TLS"):
                smtp.starttls()
            if cfg.get("MAIL_USERNAME"):
                smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        current_app.logger.error("Email to %s failed: %s", to, exc)
        return False


def send_email(to, subject, body):
    cfg = current_app.config
    if cfg.get("BREVO_API_KEY"):
        return _send_brevo(to, subject, body)
    if cfg.get("MAIL_SERVER"):
        return _send_smtp(to, subject, body)
    current_app.logger.warning("No email provider set; email to %s not sent.\nSubject: %s\n%s", to, subject, body)
    return False
