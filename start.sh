#!/usr/bin/env bash
# One-command setup + start for the Angel Arms Foundation website.
#
#   ./start.sh          # development: auto-reloads when you edit files (http://127.0.0.1:5000)
#   ./start.sh prod     # production: runs with gunicorn, reachable from other machines
#   PORT=8080 ./start.sh prod
#
# First run: creates .venv, installs packages, and writes instance/.env with a
# random SECRET_KEY and ADMIN_PASSWORD. Later runs reuse all of that.

set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-dev}"
PORT="${PORT:-5000}"

# 1. Find Python -------------------------------------------------------------
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/" >&2
  exit 1
fi
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 9))' || {
  echo "Python 3.9 or newer is required (found $("$PY" --version))." >&2
  exit 1
}

# 2. Virtual environment + packages ------------------------------------------
if [ ! -x .venv/bin/python ]; then
  echo "==> Creating virtual environment (.venv)"
  "$PY" -m venv .venv
fi
VPY=.venv/bin/python

# Only reinstall when requirements.txt has changed since the last install.
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  echo "==> Installing packages"
  "$VPY" -m pip install --quiet --upgrade pip
  "$VPY" -m pip install --quiet -r requirements.txt
  touch .venv/.installed
fi

# 3. Secrets (created once, kept in instance/.env, never committed) ----------
mkdir -p instance
if [ ! -f instance/.env ]; then
  echo "==> Creating instance/.env with a secret key and admin password"
  {
    echo "SECRET_KEY=$("$VPY" -c 'import secrets; print(secrets.token_hex(32))')"
    echo "ADMIN_PASSWORD=$("$VPY" -c 'import secrets; print(secrets.token_urlsafe(12))')"
  } > instance/.env
  chmod 600 instance/.env
fi
set -a; . instance/.env; set +a

# 4. Quick self-check --------------------------------------------------------
echo "==> Running tests"
"$VPY" -m pytest -q

# 5. Start -------------------------------------------------------------------
echo
echo "  Admin page: /admin/volunteers  (any username, password: $ADMIN_PASSWORD)"
echo "  Change the password any time in instance/.env"
echo

case "$MODE" in
  dev)
    echo "==> Starting in DEVELOPMENT mode on http://127.0.0.1:$PORT  (Ctrl+C to stop)"
    exec "$VPY" -m flask --app app run --debug --port "$PORT"
    ;;
  prod)
    echo "==> Starting in PRODUCTION mode on port $PORT  (Ctrl+C to stop)"
    exec .venv/bin/gunicorn --bind "0.0.0.0:$PORT" --workers 2 --access-logfile - app:app
    ;;
  *)
    echo "Unknown mode '$MODE'. Use: ./start.sh  or  ./start.sh prod" >&2
    exit 1
    ;;
esac
