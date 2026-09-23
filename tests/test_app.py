import re

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "ADMIN_PASSWORD": "secret",
    })
    return app.test_client()


def get_csrf(client):
    html = client.get("/volunteer").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.mark.parametrize("path", ["/", "/about", "/events", "/volunteer", "/donate"])
def test_pages_load(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert "Angel Arms Foundation" in resp.get_data(as_text=True)


def test_home_shows_mission_and_both_funds(client):
    html = client.get("/").get_data(as_text=True)
    assert "Our mission" in html
    assert "Children&#39;s Therapy Fund" in html or "Children's Therapy Fund" in html
    assert "Horse Care &amp; Therapy Fund" in html


def test_calendar_month_navigation(client):
    html = client.get("/events?year=2026&month=10").get_data(as_text=True)
    assert "October 2026" in html
    assert "Open Farm Day" in html


def test_calendar_bad_month_is_404(client):
    assert client.get("/events?year=2026&month=13").status_code == 404


def test_event_ics_download(client):
    resp = client.get("/events/open-farm-day-oct.ics")
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"
    body = resp.get_data(as_text=True)
    assert "DTSTART:20261010T090000" in body
    assert client.get("/events/nope.ics").status_code == 404


def test_volunteer_signup_saved_and_visible_to_admin(client):
    token = get_csrf(client)
    resp = client.post("/volunteer", data={
        "csrf_token": token, "name": "Somchai", "email": "s@example.com",
        "role": "stable-care", "availability": "Weekends",
    }, follow_redirects=True)
    assert "Thank you, Somchai" in resp.get_data(as_text=True)

    assert client.get("/admin/volunteers").status_code == 401
    admin = client.get("/admin/volunteers", auth=("admin", "secret"))
    assert admin.status_code == 200
    assert "s@example.com" in admin.get_data(as_text=True)


def test_volunteer_validation_errors(client):
    token = get_csrf(client)
    html = client.post("/volunteer", data={
        "csrf_token": token, "name": "", "email": "bad", "role": "",
    }).get_data(as_text=True)
    assert "Please tell us your name." in html
    assert "valid email" in html
    assert "Please choose a role." in html


def test_volunteer_rejects_missing_csrf(client):
    resp = client.post("/volunteer", data={"name": "x", "email": "a@b.co", "role": "any"})
    assert resp.status_code == 400
