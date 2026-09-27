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

`deploy.sh` is copied from AjanDB's `webapp/deploy.sh`, so it works the same way. Open the **Terminal** app on your Chromebook, then:

```bash
# first time only: download the project
git clone https://github.com/apinyacode/FarmDeApp.git
cd FarmDeApp

# every time: start (or restart after an edit)
bash deploy.sh --no-tunnel      # just on this Chromebook
bash deploy.sh                  # on this Chromebook AND online with a public link
```

| Command | What it does |
|---|---|
| `bash deploy.sh --no-tunnel` | **Local only.** Pulls the latest code, installs anything missing, (re)starts the site. Open **http://localhost:5000** in Chrome. The site keeps running in the background after the script finishes |
| `bash deploy.sh` | **Local + tunnel.** Same, then opens a public cloudflared tunnel. Look for the `https://….trycloudflare.com` line in the output and share it. Keep the terminal open; **Ctrl+C** stops both the tunnel and the site |
| `bash deploy.sh --docker` | **Fresh environment every time.** Rebuilds the site from scratch in a clean Docker container, runs the tests inside it, swaps out the old container, then opens the tunnel. Add `--no-tunnel` for local only |
| `bash deploy.sh --kill` | **Stops everything:** the site (normal or Docker) and any tunnel. Your sign-ups and password are kept |
| `bash deploy.sh --no-pull` | Skips downloading the latest code from GitHub (combine with any of the above) |

About the tunnel link:
- It is **new every time** you run it, and works only while the Chromebook is awake and the terminal is open.
  That makes it good for showing the site to the board, volunteers or a sponsor, not as the permanent website.
- Anyone with the link can see the site. The admin page is still protected by your password.

#### Docker mode (`--docker`)

Every `bash deploy.sh --docker` starts from a clean slate. It gets the latest Python base image, installs everything fresh (no leftovers from
earlier runs), runs the tests, and only then replaces the running site. **If the build or tests fail, the old site keeps running.**

- The first run installs Docker (`docker.io`) if it's missing. It uses `sudo` until you log out and back in.
- Volunteer sign-ups live in a Docker volume called `angelarms-data`, so they **survive every rebuild**.
  Back it up with: `docker run --rm -v angelarms-data:/data -v "$PWD":/backup alpine tar czf /backup/angelarms-data.tgz -C /data .`
- The container restarts on its own if the Chromebook's Linux restarts (until you run `--kill`).
- Watch the logs: `docker logs -f angelarms-web`.
- If Docker Hub can't be reached, it rebuilds from the base image already saved on your Chromebook.
- Old images are cleaned up after each deploy so the disk doesn't fill up.

It uses port **5000**, so it can run at the same time as AjanDB (port 8000).
If something goes wrong, the server log is in `/tmp/angelarms_gunicorn.log`.

> Don't see a Terminal app? Turn on Linux first: **Settings → About ChromeOS → Developers → Linux development environment → Turn on**.

---

## 2. Edit the content (no coding needed)

All the words live in the `data/` folder as JSON files. Edit one, save it and refresh the browser.

| File | What it controls |
|------|------------------|
| `data/site.json` | Name, tagline, contact details, mission, vision, values, programs, **donation funds, bank details and payment links** |
| `data/events.json` | Calendar events |
| `data/opportunities.json` | Volunteer roles |
| `data/programs.json` | The 5-day volunteer programs (Helping Hands, Caretakers): goals, skills, activities, photos |

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

- **Logo:** `static/img/logo.png` is the full logo (heart, Thai and English name). `static/img/logo-mark.png` is the heart only
  (`favicon.png` is a small copy for the browser tab),
  used in the header and browser tab. To update the logo, replace these files and keep the same names.
- **Horse photos:** the "Meet our Guardian Angels" photos are in `static/img/horses/`. To add or change them, put the photo in that folder
  and list it under `guardian_angels` → `photos` in `data/site.json`.
- **Share picture:** `static/img/share.jpg` is the image shown when the site's link is shared on Facebook or LINE.
  It includes the headline, so after changing `headline` / `headline_sub` in `data/site.json`, rebuild it with
  `pip install pillow` (once) and then `python scripts/make_share_image.py`.
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

## 5. The live website: https://angelarmsfoundation.org

The live site runs on **Render** (Singapore) and the domain is at **Cloudflare**.
Everything Render needs is described in `render.yaml`.

### How changes go live

1. A change is made on a branch and a **pull request** is opened on GitHub.
2. GitHub runs the tests automatically (green tick = safe; red X = don't merge).
3. Press **Merge** on GitHub. Render rebuilds and publishes the site within a few minutes.
   The build runs the tests again; if they fail, the old version simply keeps running.

### One-time setup (already done once; keep for reference)

**Render**
1. Render dashboard → **New +** → **Blueprint** → choose the `FarmDeApp` repository → **Apply**.
   Render creates the `angelarms-web` service, its 1 GB disk and the settings from `render.yaml`.
2. It asks for the secrets marked `sync: false`. Fill in:
   - `ADMIN_PASSWORD`: a strong password for `/admin/volunteers`
   - `ANTHROPIC_API_KEY`: for the chat helper (leave empty to keep chat off)
   - `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`: for the LINE bot (leave empty until ready)

   `SECRET_KEY` is generated by Render automatically. Change any of these later under
   **angelarms-web → Environment** (the site restarts by itself).
3. Wait for the first deploy to finish (**Logs** tab shows `46 passed` during the build). The site now
   answers at the `https://angelarms-web….onrender.com` address shown at the top of the page.

**Cloudflare (domain)**
1. In Render: **angelarms-web → Settings → Custom Domains**. Both `angelarmsfoundation.org` and
   `www.angelarmsfoundation.org` are listed (from `render.yaml`), each with the DNS record Render wants.
2. In Cloudflare: **angelarmsfoundation.org → DNS → Records → Add record**, for each one Render shows:
   - `@` (the bare domain): type **CNAME**, target `angelarms-web….onrender.com`
   - `www`: type **CNAME**, target `angelarms-web….onrender.com`
   - Set **Proxy status** to **DNS only** (grey cloud) so Render can issue the HTTPS certificate.
3. Back in Render press **Verify**. Within a few minutes both addresses show a padlock.

**LINE webhook (when you turn the LINE bot on)**: `https://angelarmsfoundation.org/line/webhook`

### Everyday checks

- **Volunteer sign-ups**: https://angelarmsfoundation.org/admin/volunteers
- **Is it up?** https://angelarmsfoundation.org/healthz answers `{"status": "ok"}`
- **Problems**: Render → angelarms-web → **Logs**. **Roll back**: Render → **Events** → pick an earlier
  deploy → **Rollback**.
- **Backups**: Render → angelarms-web → **Disks** can take snapshots; sign-ups are also visible on the admin page.
- Keep **1 instance** only: the sign-ups are stored in one database file.

Your Chromebook setup (`bash deploy.sh`) still works for trying changes privately before merging.

---

## 6. Chat helper (website + LINE)

An "Ask us" bubble on every page answers visitors' questions in Thai or English, and the same helper can
answer in LINE. It only uses what's on the site (the `data/*.json` files), so when you update the site the
answers update too. It never stores chats, never asks for personal details, and won't give medical advice.

### Turn it on (website)

1. Create an account at **https://console.anthropic.com**, add a payment method, and create an **API key**.
2. Add it to `instance/.env` on the computer that runs the site:
   ```
   ANTHROPIC_API_KEY=sk-ant-...your key...
   ```
3. Restart: `bash deploy.sh --kill && bash deploy.sh --no-tunnel`. The bubble appears bottom-right.
   Without a key the bubble simply doesn't show.

Cost: about 0.5 to 1 Thai baht per question (it uses Claude Opus 5 at a low "effort" setting, and the site
information is cached so it isn't paid for in full every time). Set a monthly spending limit in the
Anthropic console so there are no surprises. To try a cheaper model, add
`CHATBOT_MODEL=claude-sonnet-5` to `instance/.env`. Each visitor can ask up to 20 questions per 10 minutes.

### Turn it on in LINE

1. Go to **https://developers.line.biz/console/**, log in with LINE, create a **Provider** (e.g. "Angel Arms
   Foundation") and a **Messaging API channel** (this also creates a LINE Official Account).
2. In the channel's **Basic settings** copy the **Channel secret**; in **Messaging API** issue a
   **Channel access token (long-lived)**. Add both to `instance/.env`:
   ```
   LINE_CHANNEL_SECRET=...
   LINE_CHANNEL_ACCESS_TOKEN=...
   ```
3. Start the site **with the tunnel**: `bash deploy.sh` and copy the `https://….trycloudflare.com` link.
4. In **Messaging API → Webhook settings** set the webhook URL to `https://….trycloudflare.com/line/webhook`,
   turn **Use webhook** on, and press **Verify** (it should say Success).
5. In the LINE Official Account settings: turn **Auto-reply messages off**, and turn **"Allow bot to join group
   chats" on**.
6. Add the account as a friend (QR code in the console), then invite it to your group.

How it behaves:
- **Private chat** with the account: it answers every message.
- **Group chat**: it answers only when you **@mention** it, or start the message with **"บอท"** or **"bot"**
  (e.g. `บอท วันเปิดฟาร์มคือวันไหน`). Otherwise it stays quiet.

> On the live site the webhook URL is `https://angelarmsfoundation.org/line/webhook` and never changes.
> (The quick tunnel link from `deploy.sh` changes every run, so use it only for testing.)

## Project layout

```
deploy.sh               # Ubuntu / Chromebook: one-command deploy: local, tunnel, --docker, --kill
Dockerfile              # clean image used by deploy.sh --docker and by Render
render.yaml             # the live site's Render setup (region, disk, secrets, domain)
.github/workflows/      # tests run on GitHub for every pull request
start.sh / start.bat    # one-command setup + start (foreground)
app.py                  # the Flask app (routes, calendar, sign-up form, admin page)
chatbot.py              # the chat helper: builds its knowledge from data/*.json, asks Claude
line_bot.py             # LINE webhook: signature check, group-chat rules, replies
data/                   # editable content (JSON)
templates/              # HTML pages (Jinja templates)
static/css/style.css    # all styling
static/js/main.js       # mobile menu + "Copy" buttons
static/img/logo.png     # Angel Arms logo (logo-mark.png = heart only, for header/favicon)
tests/test_app.py       # automated tests (run: pytest)
```
