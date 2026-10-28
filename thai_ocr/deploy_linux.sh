#!/usr/bin/env bash
# Install or update the Thai handwriting OCR scripts on a Linux machine.
#
# What it does:
#   1. downloads only the thai_ocr/ folder from GitHub (not the whole website)
#   2. copies the scripts into INSTALL_DIR (default: ~/thai_ocr)
#   3. creates a Python virtual environment there and installs the packages
#
# Safe to run again to update: your work/ and input/ folders are never touched.
#
# Usage:
#   bash deploy_linux.sh                         # install to ~/thai_ocr
#   bash deploy_linux.sh /opt/thai_ocr           # install somewhere else
#   BRANCH=main bash deploy_linux.sh             # use another branch
#   REPO_URL=git@github.com:apinyacode/FarmDeApp.git bash deploy_linux.sh   # clone over SSH

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/apinyacode/FarmDeApp.git}"
BRANCH="${BRANCH:-claude/quirky-sagan-27izb0}"
INSTALL_DIR="${1:-$HOME/thai_ocr}"
SUBFOLDER="thai_ocr"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- checks
say "Checking requirements"
command -v git >/dev/null || fail "git is not installed. Install it with:  sudo apt install git"
command -v python3 >/dev/null || fail "python3 is not installed. Install it with:  sudo apt install python3 python3-venv"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
  || fail "Python 3.10 or newer is needed (you have $(python3 --version 2>&1))."
python3 -c 'import venv, ensurepip' 2>/dev/null \
  || fail "The Python venv module is missing. Install it with:  sudo apt install python3-venv"
echo "git $(git --version | cut -d' ' -f3), $(python3 --version)"

# ---------------------------------------------------------------- download
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT   # always delete the temporary clone, even on errors

say "Downloading $SUBFOLDER/ from $REPO_URL (branch $BRANCH)"
# --depth 1 + --filter + --sparse = fetch only the latest version of only this folder.
git clone --quiet --depth 1 --branch "$BRANCH" --filter=blob:none --sparse "$REPO_URL" "$TMP_DIR/repo" \
  || fail "Could not clone. If the repository is private, log in first (e.g. 'gh auth login'),
       or use SSH:  REPO_URL=git@github.com:apinyacode/FarmDeApp.git bash $0"
git -C "$TMP_DIR/repo" sparse-checkout set "$SUBFOLDER"
[ -f "$TMP_DIR/repo/$SUBFOLDER/step1_extract_pages.py" ] \
  || fail "Branch '$BRANCH' has no $SUBFOLDER/ folder."
COMMIT="$(git -C "$TMP_DIR/repo" rev-parse --short HEAD)"

# ---------------------------------------------------------------- copy scripts
say "Copying scripts to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
# Copy every file from the repo folder. work/, input/ and .venv/ are not in git,
# so existing ones in INSTALL_DIR are left exactly as they are.
cp -a "$TMP_DIR/repo/$SUBFOLDER/." "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/input"
echo "$COMMIT" > "$INSTALL_DIR/.deployed_commit"
echo "Installed version: $COMMIT"

# ---------------------------------------------------------------- python packages
say "Setting up the Python environment (this can take a minute)"
if [ ! -x "$INSTALL_DIR/.venv/bin/python" ]; then
  python3 -m venv "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/python" -m pip install --quiet -r "$INSTALL_DIR/requirements.txt"

# Quick self-test: can every script be imported?
( cd "$INSTALL_DIR" && .venv/bin/python -c \
  "import common, step1_extract_pages, step2_transcribe, step4_export, streamlit" ) \
  || fail "The packages installed but the scripts don't load. Send this output to your helper."

# ---------------------------------------------------------------- done
say "Done! Next steps:"
cat <<EOF

  cd $INSTALL_DIR
  source .venv/bin/activate
  export ANTHROPIC_API_KEY=sk-ant-...        # your key from console.anthropic.com

  # put your PDF in $INSTALL_DIR/input/ then:
  python step1_extract_pages.py input/questions_2560.pdf
  python step2_transcribe.py questions_2560 --pages 1-3
  streamlit run step3_review_app.py
  python step4_export.py questions_2560

  Full guide: $INSTALL_DIR/README.md
  To update later, just run this script again (your work/ folder is kept).

EOF

if [ -n "${SSH_CONNECTION:-}" ]; then
  cat <<EOF
  You're connected over SSH, so the review app's browser page is on this server.
  To open it on your own computer, connect with a tunnel:
      ssh -L 8501:localhost:8501 $(whoami)@<this-server>
  then run streamlit here and open http://localhost:8501 on your computer.
  (Don't expose port 8501 to the internet: the app has no password and shows private letters.)

EOF
fi
