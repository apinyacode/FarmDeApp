"""Angel Arms Foundation website.

A small Flask app. Content (mission, events, volunteer roles, donation
details) lives in the JSON files in ``data/`` so it can be edited without
touching Python code. Volunteer sign-ups are stored in a SQLite database
in ``instance/``.

Run locally:
    python app.py
"""

import calendar
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load_events():
    """Return all events sorted by date, each with a parsed ``day`` field."""
    events = load_json("events.json")
    for event in events:
        event["day"] = date.fromisoformat(event["date"])
    return sorted(events, key=lambda e: (e["day"], e["start"]))


def build_month(year, month, events):
    """Return a list of weeks; each week is 7 cells of (date or None, events)."""
    by_day = {}
    for event in events:
        by_day.setdefault(event["day"], []).append(event)
    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        weeks.append([
            (d if d.month == month else None, by_day.get(d, []))
            for d in week
        ])
    return weeks


def ics_for_event(event, site_name):
    """Build a minimal iCalendar file so visitors can add an event to their calendar."""
    day = event["day"].strftime("%Y%m%d")
    start = event["start"].replace(":", "") + "00"
    end = event["end"].replace(":", "") + "00"

    def esc(text):
        return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{site_name}//Events//EN",
        "BEGIN:VEVENT",
        f"UID:{event['id']}@angelarms",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{day}T{start}",
        f"DTEND:{day}T{end}",
        f"SUMMARY:{esc(event['title'])}",
        f"LOCATION:{esc(event['location'])}",
        f"DESCRIPTION:{esc(event['summary'])}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------------------
# Database (volunteer sign-ups)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS volunteers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    role TEXT,
    availability TEXT,
    message TEXT
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.db_path)
        g.db.row_factory = sqlite3.Row
        g.db.executescript(SCHEMA)
    return g.db


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        DATABASE=os.path.join(app.instance_path, "angelarms.db"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", ""),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    @app.before_request
    def _set_db_path():
        g.db_path = app.config["DATABASE"]

    @app.teardown_appcontext
    def _close_db(exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def _inject_globals():
        # Makes `site`, `csrf_token` and the current year available in every template.
        return {
            "site": load_json("site.json"),
            "csrf_token": _csrf_token,
            "current_year": date.today().year,
        }

    def _csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    def _check_csrf():
        token = request.form.get("csrf_token", "")
        if not token or not secrets.compare_digest(token, session.get("csrf", "")):
            abort(400, "Form expired — please go back, refresh and try again.")

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            password = app.config["ADMIN_PASSWORD"]
            auth = request.authorization
            if not password:
                abort(404)
            if not auth or not secrets.compare_digest(auth.password or "", password):
                return Response(
                    "Login required", 401,
                    {"WWW-Authenticate": 'Basic realm="Angel Arms admin"'},
                )
            return view(*args, **kwargs)
        return wrapped

    # -- Pages ---------------------------------------------------------------

    @app.route("/")
    def index():
        today = date.today()
        upcoming = [e for e in load_events() if e["day"] >= today][:3]
        return render_template("index.html", upcoming=upcoming)

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/events")
    def events():
        all_events = load_events()
        today = date.today()
        try:
            year = int(request.args.get("year", today.year))
            month = int(request.args.get("month", today.month))
            first = date(year, month, 1)
        except ValueError:
            abort(404)
        prev_month = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        upcoming = [e for e in all_events if e["day"] >= today]
        return render_template(
            "events.html",
            weeks=build_month(year, month, all_events),
            month_label=first.strftime("%B %Y"),
            prev_month=prev_month,
            next_month=next_month,
            today=today,
            upcoming=upcoming,
        )

    @app.route("/events/<event_id>.ics")
    def event_ics(event_id):
        event = next((e for e in load_events() if e["id"] == event_id), None)
        if event is None:
            abort(404)
        body = ics_for_event(event, load_json("site.json")["name"])
        return Response(
            body,
            mimetype="text/calendar",
            headers={"Content-Disposition": f"attachment; filename={event_id}.ics"},
        )

    @app.route("/volunteer", methods=["GET", "POST"])
    def volunteer():
        opportunities = load_json("opportunities.json")
        form = {}
        errors = {}
        if request.method == "POST":
            _check_csrf()
            form = {k: request.form.get(k, "").strip() for k in
                    ("name", "email", "phone", "role", "availability", "message")}
            if not form["name"]:
                errors["name"] = "Please tell us your name."
            if "@" not in form["email"] or "." not in form["email"]:
                errors["email"] = "Please enter a valid email address."
            valid_roles = {o["id"] for o in opportunities} | {"any"}
            if form["role"] not in valid_roles:
                errors["role"] = "Please choose a role."
            if not errors:
                db = get_db()
                db.execute(
                    "INSERT INTO volunteers (created_at, name, email, phone, role,"
                    " availability, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (datetime.now().isoformat(timespec="seconds"), form["name"],
                     form["email"], form["phone"], form["role"],
                     form["availability"], form["message"]),
                )
                db.commit()
                flash(f"Thank you, {form['name']}! We'll be in touch soon.")
                return redirect(url_for("volunteer") + "#signup")
        return render_template(
            "volunteer.html",
            opportunities=opportunities,
            events=[e for e in load_events()
                    if e["volunteers_needed"] and e["day"] >= date.today()],
            form=form,
            errors=errors,
            selected_role=request.args.get("role", form.get("role", "")),
        )

    @app.route("/donate")
    def donate():
        return render_template("donate.html", selected=request.args.get("fund", ""))

    @app.route("/admin/volunteers")
    @admin_required
    def admin_volunteers():
        rows = get_db().execute(
            "SELECT * FROM volunteers ORDER BY created_at DESC").fetchall()
        return render_template("admin_volunteers.html", rows=rows)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
