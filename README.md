# Angel Arms Foundation website

A simple website for the Angel Arms Foundation, built with **Python (Flask)**. It has:

1. **Home / About us**: vision, mission, values and what we do
2. **Events**: a monthly calendar plus a list of upcoming events, with an "Add to my calendar" download for each one
3. **Volunteer**: volunteer roles and a sign-up form (sign-ups are saved to a database)
4. **Donate**: two funds, the **Children's Therapy Fund** and the **Horse Care & Therapy Fund**, with bank transfer details, online payment links and gifts in kind

---

## 1. Start it: one command

You only need **Python 3.9 or newer** installed. Everything else is automatic.

| | macOS / Linux | Windows |
|---|---|---|
| **On your computer** (auto-reloads when you edit) | `./start.sh` | `start.bat` |
| **On a server** (production) | `./start.sh prod` | `start.bat prod` |

Then open **http://127.0.0.1:5000**. Press `Ctrl+C` to stop.

What the script does for you:
1. Creates a private Python environment (`.venv`) and installs the packages (first time only)
2. Creates `instance/.env` with a random **secret key** and **admin password** (first time only)
3. Runs the tests, so you know everything works
4. Starts the website and prints the admin password

Want a different port? `PORT=8080 ./start.sh prod` (Windows: `set PORT=8080` then `start.bat prod`).

---

### On a Chromebook (Ubuntu / Linux) — recommended

Works the same way as AjanDB's `deploy.sh`. Open the **Terminal** app on your Chromebook, then:

```bash
# first time only: download the project
git clone https://github.com/apinyacode/FarmDeApp.git
cd FarmDeApp

# every time: start (or restart after an edit)
bash deploy.sh
```

Then open **http://localhost:5000** in Chrome. The site keeps running in the background, even after you close the terminal.

| Command | What it does |
|---|---|
| `bash deploy.sh` | Pulls the latest code, installs anything missing, runs the tests and (re)starts the site |
| `bash deploy.sh stop` | Stops the site |
| `bash deploy.sh tunnel` | Also puts the site online with a public `https://….trycloudflare.com` link, shown in a box. Keep the terminal open; Ctrl+C takes it offline |
| `bash deploy.sh --no-pull` | Skips downloading the latest code from GitHub |

#### Sharing the site online with `bash deploy.sh tunnel`

- The link is **new every time** you run it, and works only while the Chromebook is awake and the terminal is open.
  That makes it good for showing the site to the board, volunteers or a sponsor, not as the permanent website.
- Anyone with the link can see the site. The admin page is still protected by your password.
- **Want a permanent address?** Create a free Cloudflare account, go to *Zero Trust → Networks → Tunnels → Create a tunnel*,
  point it at `http://localhost:5000`, and copy the token. Then add these two lines to `instance/.env`:
  ```
  CLOUDFLARE_TUNNEL_TOKEN=eyJ...your-token...
  PUBLIC_URL=https://www.your-domain.org
  ```
  From then on, `bash deploy.sh tunnel` uses that fixed address. It still only works while the computer running it is on.

It uses port **5000**, so it can run at the same time as AjanDB (port 8000).
If something goes wrong, the server log is in `/tmp/angelarms_server.log`.

> Don't see a Terminal app? Turn on Linux first: **Settings → About ChromeOS → Developers → Linux development environment → Turn on**.

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

### Thai QR donation code

The "Scan to donate" section shows `static/img/donate-qr.png`, a sharp copy of the foundation's K SHOP Thai QR code.
It contains exactly the same payment data as the original (the checksum was verified), so it pays into the same account.
If the bank ever issues a new QR code, replace that file with the new one and keep the same name.
The name, bank and reference shown next to it are under `donation` → `qr` in `data/site.json`.

You can also fill in `bank_transfer` → `account_number` or `promptpay`. They only appear on the page once they're filled in.

---

## 3. Logo, photos and colours

- **Logo:** `static/img/logo.png` is the full logo (heart, Thai and English name). `static/img/logo-mark.png` is the heart only,
  used in the header and browser tab. To update the logo, replace these files and keep the same names.
- **Horse photos:** the "Meet our Guardian Angels" photos are in `static/img/horses/`. To add or change them, put the photo in that folder
  and list it under `guardian_angels` → `photos` in `data/site.json`.
- **Colours:** at the top of `static/css/style.css`, under `:root`. They come from the logo (`--pink`, `--rose`, `--ink`)
  and from the Dream / Hope / Friends / Love booth colours.

---

## 4. See volunteer sign-ups

Go to **/admin/volunteers**, enter any username, and use the admin password.
The start script prints the password, and it is stored in `instance/.env`. Edit that file to change it,
then restart the site.

Sign-ups are saved in `instance/angelarms.db`. **Back up the `instance/` folder**, because it holds your sign-ups and secrets.
It is never uploaded to GitHub.

---

## 5. Put it online

On any Linux server or VPS (for example DigitalOcean, Linode, AWS Lightsail):

```bash
git clone <this repo> angelarms && cd angelarms
./start.sh prod                 # listens on port 5000
```

To keep it running after you log out, run it inside `tmux` or `screen`, or as a system service.
Put a web server such as Caddy or Nginx in front of it to get a real domain and HTTPS.

On a hosting platform (PythonAnywhere, Render, Railway), point it at `app:app`, and set `SECRET_KEY` and
`ADMIN_PASSWORD` as environment variables in the platform's settings.
Make sure `instance/` is on a persistent disk so sign-ups survive restarts.

---

## Project layout

```
deploy.sh               # Ubuntu / Chromebook: one-command deploy (background server)
start.sh / start.bat    # one-command setup + start (foreground)
app.py                  # the Flask app (routes, calendar, sign-up form, admin page)
data/                   # editable content (JSON)
templates/              # HTML pages (Jinja templates)
static/css/style.css    # all styling
static/js/main.js       # mobile menu + "Copy" buttons
static/img/logo.png     # Angel Arms logo (logo-mark.png = heart only, for header/favicon)
tests/test_app.py       # automated tests (run: pytest)
```
