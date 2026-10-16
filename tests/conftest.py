import os

import pytest

from vegnutri import create_app
from vegnutri.config import TestConfig
from vegnutri.extensions import db as _db


class _Config(TestConfig):
    # Set TEST_DATABASE_URL=postgresql://... to run the suite against Postgres
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", TestConfig.SQLALCHEMY_DATABASE_URI).replace(
        "postgresql://", "postgresql+psycopg://")


@pytest.fixture
def app():
    app = create_app(_Config)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="asha", email="asha@example.com", password="password123"):
    return client.post("/register", data=dict(username=username, email=email, password=password, accept_terms="on"))


def onboard(client, **overrides):
    data = dict(age=30, height=160, weight=62, gender="female", goal="fat_loss", activity_level="light",
                diet_mode="vegetarian", cuisine="north_indian", cooking_time=30, daily_budget=0)
    data.update(overrides)
    return client.post("/onboarding", data=data)


@pytest.fixture
def user_client(client):
    register(client)
    onboard(client)
    return client


@pytest.fixture
def user(app, user_client):
    from vegnutri.models import User
    return User.query.filter_by(email="asha@example.com").first()
