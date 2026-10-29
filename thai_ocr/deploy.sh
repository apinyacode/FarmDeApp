#!/usr/bin/env bash
# Fresh (re)install of the Thai handwriting OCR scripts.
#
#   bash deploy.sh                 stop everything, delete the old copy, download + install fresh
#   bash deploy.sh --wipe-data     same, but also start with no data (old data goes to a backup folder)
#
# Install folder: ~/thai_ocr   (change with:  INSTALL_DIR=/somewhere bash deploy.sh)
#
# By default your data is carried over to the fresh copy:
#   work/         page images, Claude's transcriptions (already paid for), your reviews
#   input/        your PDFs
#   api_key.txt   your saved API key

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/thai_ocr}"
INSTALL_DIR="${INSTALL_DIR%/}"
BRANCH="${BRANCH:-claude/quirky-sagan-27izb0}"
TARBALL="https://github.com/apinyacode/FarmDeApp/archive/refs/heads/$BRANCH.tar.gz"
DATA=(work input api_key.txt)

WIPE=no
[ "${1:-}" = "--wipe-data" ] && WIPE=yes

# This script deletes the folder it may live in, so run from a temporary copy.
if [ -z "${DEPLOY_COPY:-}" ] && [ -f "$0" ]; then
  copy="$(mktemp)"; cp "$0" "$copy"
  DEPLOY_COPY=1 exec bash "$copy" "$@"
fi
cleanup_copy() { [ -n "${DEPLOY_COPY:-}" ] && rm -f "$0"; true; }
trap 'cleanup_copy; rm -rf "$INSTALL_DIR.new"' EXIT

# The install folder gets deleted, so don't stand inside it.
cd "$HOME"

for tool in curl tar python3; do
  command -v "$tool" >/dev/null || { echo "Please install $tool first:  sudo apt install curl tar python3 python3-venv"; exit 1; }
done

# ---- 1. download first, so a failed download leaves the old copy working
echo "==> Downloading fresh scripts ($BRANCH)"
rm -rf "$INSTALL_DIR.new"; mkdir -p "$INSTALL_DIR.new"
curl -fsSL "$TARBALL" | tar xz -C "$INSTALL_DIR.new" --strip-components=2 --wildcards '*/thai_ocr' \
  || { echo "Download failed - nothing was changed."; exit 1; }

# ---- 2. stop everything running from the install folder (review app, transcribing, ...)
echo "==> Stopping running OCR programs"
# Never stop this script or the terminal that started it.
protected=" $$ "
pid=$$
while [ "$pid" -gt 1 ] 2>/dev/null; do
  pid="$(awk '{print $4}' "/proc/$pid/stat" 2>/dev/null)" || break
  protected="$protected$pid "
done

find_ours() {
  # Only programs started from the install folder: its own Python (.venv/bin/python,
  # used by the review app and the transcribing steps) and ocr.sh itself.
  for proc in /proc/[0-9]*; do
    pid="${proc#/proc/}"
    case "$protected" in *" $pid "*) continue ;; esac
    cwd="$(readlink "$proc/cwd" 2>/dev/null)" || continue
    case "$cwd" in "$INSTALL_DIR"|"$INSTALL_DIR"/*) ;; *) continue ;; esac
    mapfile -d '' -t argv < "$proc/cmdline" 2>/dev/null || continue
    case "${argv[0]:-}" in .venv/bin/python*|*/.venv/bin/python*) echo "$pid"; continue ;; esac
    case "${argv[1]:-}" in ocr.sh|*/ocr.sh) echo "$pid" ;; esac
  done
}
pids="$(find_ours)"
if [ -n "$pids" ]; then
  kill $pids 2>/dev/null || true
  for _ in 1 2 3 4 5; do sleep 1; pids="$(find_ours)"; [ -z "$pids" ] && break; done
  [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  echo "    stopped."
else
  echo "    nothing was running."
fi

# ---- 3. put data aside, delete the old copy, move the fresh one in
# From here on, never auto-delete the new folder: it may hold your data.
trap cleanup_copy EXIT
if [ -d "$INSTALL_DIR" ]; then
  if [ "$WIPE" = yes ]; then
    backup="${INSTALL_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup"
    for item in "${DATA[@]}"; do
      if [ -e "$INSTALL_DIR/$item" ]; then mv "$INSTALL_DIR/$item" "$backup/"; fi
    done
    echo "==> Old data moved to $backup  (delete it yourself when you're sure)"
  else
    for item in "${DATA[@]}"; do
      if [ -e "$INSTALL_DIR/$item" ]; then mv "$INSTALL_DIR/$item" "$INSTALL_DIR.new/"; fi
    done
    echo "==> Keeping your data: work/, input/, api_key.txt"
  fi
  echo "==> Deleting old copy (scripts + installed packages)"
  rm -rf "$INSTALL_DIR"
fi
mv "$INSTALL_DIR.new" "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/input"

# ---- 4. install packages fresh
echo "==> Installing Python packages (a minute or two)"
python3 -m venv "$INSTALL_DIR/.venv" || { echo "Please run:  sudo apt install python3-venv"; exit 1; }
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
chmod +x "$INSTALL_DIR/ocr.sh"

cat <<EOF

Done - fresh install in $INSTALL_DIR

  cd $INSTALL_DIR          (run this even if you were already there - the old folder is gone)
  ./ocr.sh transcribe input/yourfile.pdf
  ./ocr.sh review
  ./ocr.sh export input/yourfile.pdf

To start fresh again later:  bash $INSTALL_DIR/deploy.sh
EOF
