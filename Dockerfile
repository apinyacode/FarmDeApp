# Angel Arms Foundation website: a clean, self-contained image.
# deploy.sh --docker rebuilds this from scratch on every deploy:
#   docker pull python:3.11-slim && docker build --no-cache -t angelarms-web .
#   docker run -p 5000:5000 --env-file instance/.env -v angelarms-data:/app/instance angelarms-web
# The angelarms-data volume keeps volunteer sign-ups (angelarms.db) across rebuilds.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so this layer is reused when only the site changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY data/ data/
COPY templates/ templates/
COPY static/ static/
COPY tests/ tests/

# Run as a normal user; instance/ holds the SQLite database (mounted as a volume).
RUN useradd --create-home app && mkdir -p instance && chown app:app instance
USER app

# A broken build (e.g. a typo in data/*.json) fails here instead of going live.
RUN python -m pytest -q -p no:cacheprovider

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=4)"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app:app"]
