#!/usr/bin/env bash
# Simple shell commands for the Thai handwriting OCR.
#
#   ./ocr.sh transcribe myfile.pdf     split the PDF and let Claude read every page
#   ./ocr.sh review                    open the review app in your browser
#   ./ocr.sh export myfile.pdf         make the CSV and Word files
#
# The first time, it installs what it needs and asks for your API key.

set -euo pipefail
cd "$(dirname "$0")"

# ---- first-time setup: Python packages in a private .venv folder
if [ ! -x .venv/bin/python ]; then
  echo "First run: installing Python packages (takes a minute or two)..."
  python3 -m venv .venv || { echo "Please install Python first:  sudo apt install python3 python3-venv"; exit 1; }
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
  echo "Installed."
fi
PY=.venv/bin/python

# ---- API key: from the environment, or saved in api_key.txt (asked once)
load_key() {
  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    if [ ! -s api_key.txt ]; then
      read -rsp "Paste your Anthropic API key (starts with sk-ant-): " key; echo
      ( umask 077; printf '%s\n' "$key" > api_key.txt )   # only you can read this file
      echo "Saved in api_key.txt"
    fi
    export ANTHROPIC_API_KEY="$(cat api_key.txt)"
  fi
}

# "input/questions_2560.pdf" -> "questions_2560"
doc_name() { basename "${1%.pdf}"; }

case "${1:-}" in
  transcribe)
    [ -f "${2:-}" ] || { echo "Usage: ./ocr.sh transcribe path/to/file.pdf [--pages 1-3]"; exit 1; }
    load_key
    "$PY" step1_extract_pages.py "$2"
    "$PY" step2_transcribe.py "$(doc_name "$2")" "${@:3}"
    echo; echo "Next:  ./ocr.sh review"
    ;;
  review)
    echo "Opening http://localhost:8501  (press Ctrl+C here to stop)"
    "$PY" -m streamlit run step3_review_app.py
    ;;
  export)
    [ -n "${2:-}" ] || { echo "Usage: ./ocr.sh export path/to/file.pdf [--approved-only]"; exit 1; }
    "$PY" step4_export.py "$(doc_name "$2")" "${@:3}"
    ;;
  *)
    sed -n '3,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
