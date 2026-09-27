#!/usr/bin/env bash
# One-command deploy/redeploy for the Angel Arms Foundation website.
# Copied from AjanDB's webapp/deploy.sh ("local" target) and adapted to this
# Flask app. Ways to run it:
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
#   bash deploy.sh --docker        # fresh environment every deploy: rebuilds
#                                   #   the Docker image from scratch (latest
#                                   #   python base, clean install, tests run
#                                   #   inside the build), replaces the old
#                                   #   container, then opens the tunnel.
#                                   #   Combine with --no-tunnel for local only.
#                                   #   Volunteer sign-ups live in the
#                                   #   "angelarms-data" Docker volume and
#                                   #   survive every rebuild.
#   bash deploy.sh --kill          # stops everything this script started:
#                                   #   the server, the Docker container and
#                                   #   any tunnel. Nothing is deleted.
#
# Flags (any mode): --no-pull skips `git pull`. --no-tunnel skips the
# cloudflared tunnel - see above.
#
# Secrets: the first run creates instance/.env (gitignored) with a random
# SECRET_KEY and ADMIN_PASSWORD (for /admin/volunteers). Edit that file to
# change the password; it is loaded on every run (and passed to Docker).
#
# Differences from AjanDB's script, all needed for this project:
#   - port 5000 (AjanDB uses 8000, so both can run at the same time)
#   - gunicorn app:app instead of uvicorn backend.main:app
#   - no tesseract/ffmpeg (this site doesn't need them), no vercel target
#   - downloads the right cloudflared for ARM Chromebooks as well as Intel/AMD
#   - extra --docker and --kill options
set -euo pipefail

# --- Parse args (before the re-exec, so we know whether to pull; the same
# args are forwarded unchanged to the re-exec'd copy of this script below,
# where they're parsed again for the real work). ---
NO_PULL=0
NO_TUNNEL=0
MODE="local"
for arg in "$@"; do
  case "$arg" in
    --no-pull) NO_PULL=1 ;;
    --no-tunnel) NO_TUNNEL=1 ;;
    --docker) MODE="docker" ;;
    --kill) MODE="kill" ;;
    *) echo "Unknown option: $arg  (use: --no-tunnel, --docker, --kill, --no-pull)" >&2; exit 1 ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=5000
CONTAINER=angelarms-web
IMAGE=angelarms-web
VOLUME=angelarms-data

# --- Kill: stop everything, no pull, no rebuild. ---
kill_all() {
  local stopped=0
  if pkill -f "gunicorn --name angelarms-local" 2>/dev/null; then
    echo "    Stopped the local server (port $PORT)."; stopped=1
  fi
  if pkill -f "$REPO_DIR/cloudflared tunnel" 2>/dev/null; then
    echo "    Stopped the cloudflared tunnel."; stopped=1
  fi
  if command -v docker >/dev/null 2>&1; then
    local d="docker"
    docker info >/dev/null 2>&1 || d="sudo docker"
    if $d ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
      $d rm -f "$CONTAINER" >/dev/null
      echo "    Stopped and removed the Docker container ($CONTAINER)."; stopped=1
    fi
  fi
  [ "$stopped" = "1" ] || echo "    Nothing was running."
  return 0
}

if [ "$MODE" = "kill" ]; then
  echo "==> Stopping the Angel Arms site..."
  kill_all
  echo "    Your volunteer sign-ups and instance/.env are untouched."
  exit 0
fi

# --- Re-exec after a git pull so we always run the freshly-pulled version of
# this very script, never a half-updated one (bash doesn't guarantee reading
# a script file atomically while it changes underneath itself). ---
if [ "${ANGELARMS_REEXEC:-}" != "1" ]; then
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

APP_DIR="$REPO_DIR"
cd "$APP_DIR"

install_apt() {
  if [ $# -gt 0 ]; then
    echo "    Installing: $*"
    sudo apt-get update -qq
    sudo apt-get install -y "$@"
  else
    echo "    All present."
  fi
}

# Creates instance/.env once (random secret key + admin password), then loads it.
load_secrets() {
  mkdir -p instance
  if [ ! -f "instance/.env" ]; then
    echo "==> Creating instance/.env (secret key + admin password)"
    {
      echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
      echo "ADMIN_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
    } > instance/.env
    chmod 600 instance/.env
  fi
  echo "==> Loading instance/.env"
  set -a
  # shellcheck disable=SC1091
  source instance/.env
  set +a
}

# Opens the public tunnel in the foreground; $1 is the command that stops the
# site when the tunnel is closed with Ctrl+C.
open_tunnel() {
  STOP_CMD="$1"
  if [ "$NO_TUNNEL" = "1" ]; then
    echo "==> Skipping tunnel (--no-tunnel)."
    echo "    Open http://localhost:$PORT/ on this machine - no public URL,"
    echo "    no tunnel to drop or debug."
    echo "    Stop the site with: bash deploy.sh --kill"
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

  echo "==> Opening tunnel - Ctrl+C stops both the tunnel and the site."
  echo "    Your public link is the https://....trycloudflare.com line below."
  trap 'echo; echo "==> Stopping the site..."; eval "$STOP_CMD" >/dev/null 2>&1 || true' INT TERM EXIT
  "$CLOUDFLARED_BIN" tunnel --url "http://localhost:$PORT"
}

deploy_local() {
  echo "==> Checking system dependencies..."
  NEED_APT=()
  command -v git >/dev/null 2>&1 || NEED_APT+=(git)
  python3 -c "import venv" >/dev/null 2>&1 || NEED_APT+=(python3-venv)
  command -v pip3 >/dev/null 2>&1 || NEED_APT+=(python3-pip)
  command -v curl >/dev/null 2>&1 || NEED_APT+=(curl)
  install_apt "${NEED_APT[@]}"

  echo "==> Python environment..."
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -r requirements.txt

  load_secrets

  echo "==> Stopping any previous server on port $PORT..."
  pkill -9 -f "gunicorn --name angelarms-local" 2>/dev/null || true
  if command -v docker >/dev/null 2>&1; then
    { docker rm -f "$CONTAINER" || sudo -n docker rm -f "$CONTAINER"; } >/dev/null 2>&1 || true
  fi
  sleep 1

  echo "==> Starting server..."
  rm -f /tmp/angelarms_gunicorn.log
  nohup gunicorn --name angelarms-local --bind "0.0.0.0:$PORT" --workers 2 --access-logfile - app:app > /tmp/angelarms_gunicorn.log 2>&1 &
  SERVER_PID=$!
  sleep 2
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "!! Server failed to start. Last log lines:"
    tail -n 30 /tmp/angelarms_gunicorn.log
    exit 1
  fi
  echo "    Running (pid $SERVER_PID). Logs: /tmp/angelarms_gunicorn.log"
  echo "    Admin page: /admin/volunteers  (any username, password: $ADMIN_PASSWORD)"

  open_tunnel "kill $SERVER_PID"
}

deploy_docker() {
  echo "==> Checking system dependencies..."
  NEED_APT=()
  command -v git >/dev/null 2>&1 || NEED_APT+=(git)
  command -v python3 >/dev/null 2>&1 || NEED_APT+=(python3)
  command -v curl >/dev/null 2>&1 || NEED_APT+=(curl)
  command -v docker >/dev/null 2>&1 || NEED_APT+=(docker.io)
  install_apt "${NEED_APT[@]}"

  # Use plain `docker` if this user may, otherwise sudo (a fresh docker.io
  # install needs a logout/login before the docker group takes effect).
  DOCKER="docker"
  if ! docker info >/dev/null 2>&1; then
    if ! sudo docker info >/dev/null 2>&1; then
      echo "    Starting the Docker service..."
      sudo systemctl start docker 2>/dev/null || sudo service docker start
      sleep 2
    fi
    DOCKER="sudo docker"
  fi

  load_secrets

  echo "==> Getting the latest Python base image..."
  BASE_IMAGE="$(awk '/^FROM /{print $2; exit}' Dockerfile)"
  if ! $DOCKER pull -q "$BASE_IMAGE" >/dev/null; then
    if $DOCKER image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
      echo "    Couldn't reach Docker Hub - using the copy already on this machine."
    else
      echo "!! Couldn't download $BASE_IMAGE. Check your internet connection and try again."
      exit 1
    fi
  fi

  # The running site is only replaced after this build (and its tests) succeed.
  echo "==> Building a fresh image (no cache, tests included)..."
  $DOCKER build --no-cache -t "$IMAGE" .

  echo "==> Replacing the previous container..."
  pkill -9 -f "gunicorn --name angelarms-local" 2>/dev/null || true
  $DOCKER rm -f "$CONTAINER" >/dev/null 2>&1 || true

  echo "==> Starting container..."
  $DOCKER run -d --name "$CONTAINER" --restart unless-stopped \
    -p "$PORT:5000" \
    --env-file instance/.env \
    -v "$VOLUME:/app/instance" \
    "$IMAGE" >/dev/null

  for _ in $(seq 1 20); do
    curl -fsS -o /dev/null "http://localhost:$PORT/" 2>/dev/null && break
    sleep 1
  done
  if ! curl -fsS -o /dev/null "http://localhost:$PORT/" 2>/dev/null; then
    echo "!! The site did not come up. Last log lines:"
    $DOCKER logs --tail 30 "$CONTAINER"
    exit 1
  fi
  echo "    Running in container '$CONTAINER'. Logs: $DOCKER logs -f $CONTAINER"
  echo "    Volunteer sign-ups are kept in the '$VOLUME' volume."
  echo "    Admin page: /admin/volunteers  (any username, password: $ADMIN_PASSWORD)"

  # Remove the previous, now-unused images so the disk doesn't fill up.
  $DOCKER image prune -f >/dev/null 2>&1 || true

  open_tunnel "$DOCKER rm -f $CONTAINER"
}

case "$MODE" in
  local) deploy_local ;;
  docker) deploy_docker ;;
esac
