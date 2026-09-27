#!/bin/sh
# Start the website inside the container.
# Hosting disks (Render, a Docker volume) can be mounted owned by root, so make sure the
# app user can write the sign-up database, then drop to that user to run the site.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/instance
  chown -R app:app /app/instance
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
