"""Public meal library and sample meal plans."""
import re

import pytest

from vegnutri.blueprints.explore import PLAN_PAGES, suits
from vegnutri.data.meals import MEALS
from vegnutri.services.nutrition import DIET_MODES


def test_meal_library_and_filters(client):
    assert client.get("/meals").status_code == 200
    html = client.get("/meals?diet=jain").get_data(as_text=True)
    names = set(re.findall(r'class="panel meal-card" href="/meals/([a-z0-9_]+)"', html))
    assert names and all(not (MEALS[k]["tags"] & DIET_MODES["jain"][1]) for k in names)
    vrat = set(re.findall(r'href="/meals/([a-z0-9_]+)"', client.get("/meals?diet=vrat").get_data(as_text=True)))
    assert vrat and all("fasting" in MEALS[k]["tags"] for k in vrat)


def test_every_meal_page_renders(client):
    for key in MEALS:
        r = client.get(f"/meals/{key}")
        assert r.status_code == 200, key
    assert client.get("/meals/not-a-meal").status_code == 404


@pytest.mark.parametrize("slug", list(PLAN_PAGES))
def test_sample_plans_follow_their_diet(client, slug):
    r = client.get(f"/meal-plans/{slug}")
    assert r.status_code == 200
    _, _, diet, _, fasting = PLAN_PAGES[slug]
    planned = re.findall(r'<span class="name"><a href="/meals/([a-z0-9_]+)"', r.get_data(as_text=True))
    assert planned
    for key in planned:
        assert suits(MEALS[key], "vrat" if fasting else diet), (slug, key)


def test_sample_plans_are_stable(client):
    a = client.get("/meal-plans/jain").get_data(as_text=True)
    b = client.get("/meal-plans/jain").get_data(as_text=True)
    pick = lambda h: re.findall(r'<span class="name"><a href="/meals/([a-z0-9_]+)"', h)
    assert pick(a) == pick(b)  # same content every visit, which search engines need


def test_seo_basics(client):
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/meals/idli_sambar" in sitemap and "/meal-plans/jain" in sitemap
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Allow: /meals" in robots and "Allow: /meal-plans" in robots
    page = client.get("/meals/idli_sambar").get_data(as_text=True)
    assert 'rel="canonical"' in page and '<meta name="description" content="Idli' in page
