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
    assert "The Angel Arms Foundation" in resp.get_data(as_text=True)


def test_home_shows_mission_and_both_funds(client):
    html = client.get("/").get_data(as_text=True)
    assert "Our mission" in html and "Guardian Angels" in html
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


def test_about_shows_story_objectives_and_board(client):
    html = client.get("/about").get_data(as_text=True)
    assert "Farm de Lek" in html
    assert "Horseboy Method" in html
    assert "Mrs Premruedee Tantivejkul" in html
    assert "มูลนิธิในอ้อมกอด" in html


def test_facebook_link_on_pages(client):
    fb = "https://www.facebook.com/profile.php?id=61583808935783"
    assert fb in client.get("/").get_data(as_text=True)
    assert fb in client.get("/events").get_data(as_text=True)


def test_donate_shows_thai_qr(client):
    html = client.get("/donate").get_data(as_text=True)
    assert "img/donate-qr.png" in html
    assert "Save QR code" in html
    assert "000-0-00000-0" not in html  # no placeholder account number
    resp = client.get("/static/img/donate-qr.png")
    assert resp.status_code == 200 and resp.mimetype == "image/png"


def test_volunteer_page_shows_five_day_programs(client):
    html = client.get("/volunteer").get_data(as_text=True)
    assert "5-day volunteer programs" in html
    assert "Helping Hands" in html and "Caretakers" in html
    assert "Special Education Centre" in html


def test_can_apply_for_a_five_day_program(client):
    token = get_csrf(client)
    resp = client.post("/volunteer", data={
        "csrf_token": token, "name": "Mali", "email": "mali@example.com",
        "role": "caretakers", "availability": "1-5 March",
    }, follow_redirects=True)
    assert "Thank you, Mali" in resp.get_data(as_text=True)
    admin = client.get("/admin/volunteers", auth=("admin", "secret"))
    assert "caretakers" in admin.get_data(as_text=True)


def test_apply_link_preselects_program(client):
    html = client.get("/volunteer?role=helping-hands").get_data(as_text=True)
    assert '<option value="helping-hands" selected>' in html
