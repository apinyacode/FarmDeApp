#!/usr/bin/env bash
# One-command deploy/redeploy for the Angel Arms Foundation website.
# Copied from AjanDB's webapp/deploy.sh ("local" target) and adapted to this
# Flask app. Two ways to run it:
#
#   bash deploy.sh                 # installs missing system deps,
#                                   #   sets up the venv, restarts the server,
#                                   #   opens a public cloudflared tunnel.
#                                   #   Look for the https://....trycloudflare.com
#                                   #   link in the output and share it.
#   bash deploy.sh --no-tunnel     # same as above but skips cloudflared -
#                                   #   the server stays reachable only at
#                                   #   http://localhost:5000/ on this
#                                   #   machine. No tunnel flakiness to
#                                   #   debug at all, at the cost of only
#                                   #   this machine being able to reach it
#                                   #   (no other device, no public URL to
#                                   #   share). Good for local-only testing.
#
# Flags: --no-pull skips `git pull`. --no-tunnel skips the cloudflared
# tunnel - see above.
#
# Secrets: the first run creates instance/.env (gitignored) with a random
# SECRET_KEY and ADMIN_PASSWORD (for /admin/volunteers). Edit that file to
# change the password; it is loaded on every run.
#
# Differences from AjanDB's script, all needed for this project:
#   - port 5000 (AjanDB uses 8000, so both can run at the same time)
#   - gunicorn app:app instead of uvicorn backend.main:app
#   - no tesseract/ffmpeg (this site doesn't need them), no vercel target
#   - downloads the right cloudflared for ARM Chromebooks as well as Intel/AMD
set -euo pipefail

# --- Parse args (before the re-exec, so we know whether to pull; the same
# args are forwarded unchanged to the re-exec'd copy of this script below,
# where they're parsed again for the real work). ---
NO_PULL=0
NO_TUNNEL=0
for arg in "$@"; do
  case "$arg" in
    --no-pull) NO_PULL=1 ;;
    --no-tunnel) NO_TUNNEL=1 ;;
  esac
done

# --- Re-exec after a git pull so we always run the freshly-pulled version of
# this very script, never a half-updated one (bash doesn't guarantee reading
# a script file atomically while it changes underneath itself). ---
if [ "${ANGELARMS_REEXEC:-}" != "1" ]; then
  REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$REPO_DIR"

  if [ "$NO_PULL" = "1" ]; then
    echo "==> Skipping git pull (--no-pull)"
  elif [ -n "$(git status --porcelain)" ]; then
    echo "==> Local changes detected in $REPO_DIR - not auto-pulling."
    echo "    Review with 'git status'; commit or stash, then re-run."
  else
    echo "==> Pulling latest code..."
    git pull
  fi

  export ANGELARMS_REEXEC=1
  exec bash "$REPO_DIR/deploy.sh" "$@"
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
PORT=5000

deploy_local() {
  echo "==> Checking system dependencies..."
  NEED_APT=()
  command -v git >/dev/null 2>&1 || NEED_APT+=(git)
  python3 -c "import venv" >/dev/null 2>&1 || NEED_APT+=(python3-venv)
  command -v pip3 >/dev/null 2>&1 || NEED_APT+=(python3-pip)
  command -v curl >/dev/null 2>&1 || NEED_APT+=(curl)

  if [ ${#NEED_APT[@]} -gt 0 ]; then
    echo "    Installing: ${NEED_APT[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${NEED_APT[@]}"
  else
    echo "    All present."
  fi

  echo "==> Python environment..."
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -r requirements.txt

  mkdir -p instance
  if [ ! -f "instance/.env" ]; then
    echo "==> Creating instance/.env (secret key + admin password)"
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

  echo "==> Stopping any previous server on port $PORT..."
  pkill -9 -f "gunicorn --bind 0.0.0.0:$PORT" 2>/dev/null || true
  sleep 1

  echo "==> Starting server..."
  rm -f /tmp/angelarms_gunicorn.log
  nohup gunicorn --bind "0.0.0.0:$PORT" --workers 2 --access-logfile - app:app > /tmp/angelarms_gunicorn.log 2>&1 &
  SERVER_PID=$!
  sleep 2
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "!! Server failed to start. Last log lines:"
    tail -n 30 /tmp/angelarms_gunicorn.log
    exit 1
  fi
  echo "    Running (pid $SERVER_PID). Logs: /tmp/angelarms_gunicorn.log"
  echo "    Admin page: /admin/volunteers  (any username, password: $ADMIN_PASSWORD)"

  if [ "$NO_TUNNEL" = "1" ]; then
    echo "==> Skipping tunnel (--no-tunnel)."
    echo "    Open http://localhost:$PORT/ on this machine - no public URL,"
    echo "    no tunnel to drop or debug."
    echo "    Stop the server with: kill $SERVER_PID   (or: pkill -f 'gunicorn --bind 0.0.0.0:$PORT')"
    return 0
  fi

  echo "==> Setting up cloudflared..."
  CLOUDFLARED_BIN="$APP_DIR/cloudflared"
  if [ ! -x "$CLOUDFLARED_BIN" ]; then
    case "$(uname -m)" in
      aarch64|arm64) CF_ARCH=arm64 ;;
      armv7l|armhf) CF_ARCH=arm ;;
      *) CF_ARCH=amd64 ;;
    esac
    curl -Lo "$CLOUDFLARED_BIN" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$CF_ARCH"
    chmod +x "$CLOUDFLARED_BIN"
  fi

  echo "==> Opening tunnel - Ctrl+C stops both the tunnel and the server."
  echo "    Your public link is the https://....trycloudflare.com line below."
  trap 'echo; echo "==> Stopping server (pid $SERVER_PID)..."; kill "$SERVER_PID" 2>/dev/null || true' INT TERM EXIT
  "$CLOUDFLARED_BIN" tunnel --url "http://localhost:$PORT"
}

deploy_local
