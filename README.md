# Angel Arms Foundation website

A simple website for the Angel Arms Foundation, built with **Python (Flask)**. It has:

1. **Home / About us**: vision, mission, values and what we do
2. **Events**: a monthly calendar plus a list of upcoming events, with an "Add to my calendar" download for each one
3. **Volunteer**: volunteer roles and a sign-up form (sign-ups are saved to a database)
4. **Donate**: two funds, the **Children's Therapy Fund** and the **Horse Care & Therapy Fund**, with bank transfer details, online payment links and gifts in kind

---

## 1. Run it on your computer (step by step)

You need Python 3.10 or newer.

```bash
# 1. Go into the project folder
cd FarmDeApp

# 2. Create a "virtual environment" (a private box for this project's packages)
python -m venv .venv

# 3. Turn it on
#    macOS / Linux:
source .venv/bin/activate
#    Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 4. Install Flask
pip install -r requirements.txt

# 5. Start the site
python app.py
```

Open **http://127.0.0.1:5000** in your browser. Press `Ctrl+C` in the terminal to stop.

Run the tests with `pytest`.

---

## 2. Edit the content (no coding needed)

All the words live in the `data/` folder as JSON files. Edit one, save it and refresh the browser.

| File | What it controls |
|------|------------------|
| `data/site.json` | Name, tagline, contact details, mission, vision, values, programs, **donation funds, bank details and payment links** |
| `data/events.json` | Calendar events |
| `data/opportunities.json` | Volunteer roles |

**JSON tips:** keep the quotes `"..."`, put a comma between items and **no** comma after the last item.
If the site shows an error after an edit, paste the file into https://jsonlint.com to find the mistake.

### Add an event

Copy an existing block in `data/events.json` and change the values:

```json
{
  "id": "summer-camp-2027",
  "title": "Summer Riding Camp",
  "date": "2027-04-12",
  "start": "09:00",
  "end": "15:00",
  "location": "Angel Arms Farm",
  "category": "therapy",
  "summary": "One short paragraph.",
  "volunteers_needed": true
}
```

- `id`: unique, lowercase, no spaces
- `date`: YEAR-MONTH-DAY
- `category`: one of `therapy`, `horses`, `community`, `volunteer`, `fundraising` (this sets the colour)
- `volunteers_needed`: `true` shows the event on the Volunteer page too

### Turn on online donations

The easiest way is a **payment link** from a provider such as Stripe (Payment Links), PayPal (Donate button link)
or your bank's online payment page. Create one link per fund, then paste each into `online_link` in `data/site.json`:

```json
"online_link": "https://donate.stripe.com/your-link-here"
```

A "Donate online" button then appears for that fund. Card details are handled by the provider, never by this website.

Also fill in `bank_transfer` (bank, account number, and `promptpay` if you use it).

---

## 3. Change the logo and colours

- **Logo:** replace `static/img/logo.svg` with the real Angel Arms logo.
  If your logo is a PNG, save it as `static/img/logo.png`, then in `templates/base.html` and `templates/index.html`
  change `img/logo.svg` to `img/logo.png`.
- **Colours:** at the top of `static/css/style.css`, change the values under `:root` (for example `--brown` and `--gold`) to match the logo.

---

## 4. See volunteer sign-ups

Sign-ups are saved in `instance/angelarms.db`. To view them in the browser, set an admin password before starting:

```bash
# macOS / Linux
export ADMIN_PASSWORD="choose-a-strong-password"
# Windows (PowerShell)
$env:ADMIN_PASSWORD="choose-a-strong-password"

python app.py
```

Then go to **/admin/volunteers**, enter any username and your password.
(If no password is set, the admin page is switched off.)

---

## 5. Put it online

Any host that runs Python works, for example PythonAnywhere, Render or Railway. For a live site:

- Set the `SECRET_KEY` environment variable to a long random value (`python -c "import secrets; print(secrets.token_hex(32))"`).
- Set `ADMIN_PASSWORD`.
- Run with a production server, e.g. `pip install gunicorn` then `gunicorn app:app`.
- Make sure the host keeps the `instance/` folder between restarts so sign-ups aren't lost.

---

## Project layout

```
app.py                  # the Flask app (routes, calendar, sign-up form, admin page)
data/                   # editable content (JSON)
templates/              # HTML pages (Jinja templates)
static/css/style.css    # all styling
static/js/main.js       # mobile menu + "Copy" buttons
static/img/logo.svg     # placeholder logo, replace with the real one
tests/test_app.py       # automated tests (run: pytest)
```
