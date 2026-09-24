#!/usr/bin/env bash
# One-command deploy/redeploy for the Angel Arms Foundation website, for
# Ubuntu / Debian, including the Linux environment on a Chromebook.
# Modelled on AjanDB's webapp/deploy.sh, with the same flags.
#
#   bash deploy.sh                 # installs missing system deps, sets up
#                                   #   the venv, runs the tests, (re)starts
#                                   #   the server in the background. Local
#                                   #   only: open http://localhost:5000/ in
#                                   #   Chrome.
#   bash deploy.sh --tunnel        # same, then also opens a public
#                                   #   cloudflared tunnel so you can share a
#                                   #   https://....trycloudflare.com link
#                                   #   (anyone with the link can see the site).
#   bash deploy.sh stop            # stops the background server.
#
# Flags: --no-pull skips `git pull`. --tunnel opens the public tunnel.
# (--no-tunnel is accepted for AjanDB muscle memory; it is the default here.)
# PORT=8080 bash deploy.sh changes the port (default 5000, so it can run at
# the same time as AjanDB on 8000).
#
# Secrets: the first run writes instance/.env (gitignored) with a random
# SECRET_KEY and ADMIN_PASSWORD. Edit it to change the admin password.
set -euo pipefail

# --- Parse args (before the re-exec; the same args are forwarded to the
# re-exec'd copy of this script below). ---
TARGET="local"
NO_PULL=0
TUNNEL=0
for arg in "$@"; do
  case "$arg" in
    local|stop) TARGET="$arg" ;;
    --no-pull) NO_PULL=1 ;;
    --tunnel) TUNNEL=1 ;;
    --no-tunnel) TUNNEL=0 ;;
    *) echo "Unknown option: $arg  (use: stop, --no-pull, --tunnel)" >&2; exit 1 ;;
  esac
done

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
PORT="${PORT:-5000}"
PID_FILE="$APP_DIR/instance/server.pid"
LOG_FILE="/tmp/angelarms_server.log"

stop_server() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "==> Stopping previous server (pid $(cat "$PID_FILE"))..."
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"
}

if [ "$TARGET" = "stop" ]; then
  stop_server
  echo "    Stopped."
  exit 0
fi

# --- Re-exec after a git pull so we always run the freshly-pulled version of
# this very script, never a half-updated one. ---
if [ "${ANGELARMS_REEXEC:-}" != "1" ]; then
  if [ "$NO_PULL" = "1" ]; then
    echo "==> Skipping git pull (--no-pull)"
  elif [ ! -d .git ]; then
    echo "==> Not a git checkout - skipping git pull."
  elif [ -n "$(git status --porcelain)" ]; then
    echo "==> Local changes detected in $APP_DIR - not auto-pulling."
    echo "    Review with 'git status'; commit or stash, then re-run."
  else
    echo "==> Pulling latest code..."
    git pull || echo "    git pull failed - continuing with the code you have."
  fi

  export ANGELARMS_REEXEC=1
  exec bash "$APP_DIR/deploy.sh" "$@"
fi

echo "==> Checking system dependencies..."
NEED_APT=()
command -v git >/dev/null 2>&1 || NEED_APT+=(git)
command -v python3 >/dev/null 2>&1 || NEED_APT+=(python3)
python3 -m venv --help >/dev/null 2>&1 || NEED_APT+=(python3-venv)
command -v curl >/dev/null 2>&1 || NEED_APT+=(curl)
if [ ${#NEED_APT[@]} -gt 0 ]; then
  echo "    Installing: ${NEED_APT[*]}"
  sudo apt-get update -qq
  sudo apt-get install -y "${NEED_APT[@]}"
else
  echo "    All present."
fi

echo "==> Python environment..."
# ensurepip is missing on some Ubuntu images even when venv imports fine;
# a half-made .venv without pip is removed and rebuilt.
if [ -d .venv ] && [ ! -x .venv/bin/pip ]; then
  rm -rf .venv
fi
if [ ! -d .venv ]; then
  if ! python3 -m venv .venv; then
    rm -rf .venv
    echo "    Installing python3-venv..."
    sudo apt-get update -qq
    sudo apt-get install -y python3-venv
    python3 -m venv .venv
  fi
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

mkdir -p instance
if [ ! -f instance/.env ]; then
  echo "==> Creating instance/.env with a secret key and admin password"
  {
    echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')"
    echo "ADMIN_PASSWORD=$(python -c 'import secrets; print(secrets.token_urlsafe(12))')"
  } > instance/.env
  chmod 600 instance/.env
fi
echo "==> Loading instance/.env"
set -a
# shellcheck disable=SC1091
source instance/.env
set +a

echo "==> Running tests..."
if ! python -m pytest -q; then
  echo "!! Tests failed - not starting the server. Fix the error above"
  echo "   (often a typo in a data/*.json file) and re-run."
  exit 1
fi

stop_server

echo "==> Starting server..."
rm -f "$LOG_FILE"
nohup gunicorn --bind "0.0.0.0:$PORT" --workers 2 --access-logfile - app:app > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"
sleep 2
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "!! Server failed to start. Last log lines:"
  tail -n 30 "$LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi
echo "    Running (pid $SERVER_PID). Logs: $LOG_FILE"
echo
echo "    Website:     http://localhost:$PORT/"
echo "    Admin page:  http://localhost:$PORT/admin/volunteers"
echo "                 (any username, password: $ADMIN_PASSWORD)"
echo

if [ "$TUNNEL" != "1" ]; then
  echo "==> Local only (add --tunnel for a public link)."
  echo "    Open http://localhost:$PORT/ in Chrome on this Chromebook."
  echo "    The server keeps running in the background after this script exits."
  echo "    Stop it with: bash deploy.sh stop"
  exit 0
fi

echo "==> Setting up cloudflared..."
case "$(uname -m)" in
  x86_64|amd64) CF_ARCH=amd64 ;;
  aarch64|arm64) CF_ARCH=arm64 ;;
  armv7l|armhf) CF_ARCH=arm ;;
  *) echo "!! No cloudflared build for $(uname -m). Re-run without --tunnel."; exit 1 ;;
esac
CLOUDFLARED_BIN="$APP_DIR/cloudflared"
if [ ! -x "$CLOUDFLARED_BIN" ]; then
  curl -fLo "$CLOUDFLARED_BIN" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$CF_ARCH"
  chmod +x "$CLOUDFLARED_BIN"
fi

echo "==> Opening tunnel - look for the https://....trycloudflare.com link below."
echo "    Ctrl+C stops both the tunnel and the server."
trap 'echo; echo "==> Stopping server (pid $SERVER_PID)..."; kill "$SERVER_PID" 2>/dev/null || true; rm -f "$PID_FILE"' INT TERM EXIT
"$CLOUDFLARED_BIN" tunnel --url "http://localhost:$PORT"
