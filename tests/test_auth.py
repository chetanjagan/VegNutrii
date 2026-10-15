import hashlib

from conftest import register

from vegnutri.extensions import db
from vegnutri.models import User


def test_register_requires_terms_and_valid_input(client):
    r = client.post("/register", data=dict(username="a", email="bad", password="short"))
    assert r.status_code == 400
    assert User.query.count() == 0


def test_register_login_logout(client):
    assert register(client).status_code == 302
    client.post("/logout")
    r = client.post("/login", data=dict(email="asha@example.com", password="wrong-pass"))
    assert r.status_code == 401
    r = client.post("/login", data=dict(email="ASHA@example.com ", password="password123"))
    assert r.status_code == 302


def test_duplicate_email_rejected(client):
    register(client)
    client.post("/logout")
    r = register(client, username="other")
    assert r.status_code == 400


def test_legacy_sha256_password_is_upgraded(app, client):
    u = User(username="old", email="old@example.com", password_hash=hashlib.sha256(b"oldpass123").hexdigest())
    db.session.add(u)
    db.session.commit()
    r = client.post("/login", data=dict(email="old@example.com", password="oldpass123"))
    assert r.status_code == 302
    db.session.refresh(u)
    assert not u.has_legacy_hash and u.check_password("oldpass123")


def test_login_redirect_rejects_external_next(client):
    register(client)
    client.post("/logout")
    r = client.post("/login?next=//evil.example.com", data=dict(email="asha@example.com", password="password123"))
    assert "evil" not in r.headers["Location"]


def test_password_reset_token_single_use(app, client):
    from vegnutri.blueprints.auth import make_reset_token
    register(client)
    client.post("/logout")
    user = User.query.first()
    token = make_reset_token(user)
    assert client.post(f"/reset/{token}", data=dict(password="newpassword1")).status_code == 302
    # Second use fails because the password hash changed
    r = client.post(f"/reset/{token}", data=dict(password="another-pass"))
    assert r.status_code == 302 and "/forgot" in r.headers["Location"]
    assert client.post("/login", data=dict(email="asha@example.com", password="newpassword1")).status_code == 302


def test_pages_require_login(client):
    for url in ("/dashboard", "/plan", "/log", "/coach", "/account/"):
        r = client.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"]
