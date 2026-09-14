# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=20

WORKDIR /app

# curl is required by the docker-compose healthcheck. Chromium and its
# distribution-matched driver keep Selenium independent from runtime downloads.
#
# chromium/chromium-driver are version-pinned: an unpinned rebuild once pulled
# a newer chromedriver that rejected the (then-present) excludeSwitches
# capability outright, taking every crawl down with "Selenium browser failed
# to start" (see INCIDENT_P0_GOOGLE_MAPS_ONLY_5_REVIEWS.md §12-13).
#
# Debian's security archive keeps only the CURRENT build of a package - the
# exact version below WILL eventually 404 on `apt-get update` once Debian
# ships the next security point-release (confirmed: the version this pin
# replaced vanished from the mirror within the same day it was installed).
# That is the intended failure mode - a loud build break forces a deliberate
# bump instead of a silent Chrome upgrade breaking crawls again. To bump:
# `apt-cache madison chromium` for the current version, update both lines,
# rebuild, and re-verify _create_driver() actually starts before deploying.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        chromium=152.0.7977.82-1~deb13u1 \
        chromium-driver=152.0.7977.82-1~deb13u1 \
        curl \
        xauth \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY apps/api/requirements.txt /app/apps/api/requirements.txt

# This host's link to PyPI drops mid-download (BrokenPipeError), so:
#  - the BuildKit cache mount keeps every wheel that DID finish, so each retry
#    (and each re-run of `docker compose build`) only fetches what is still
#    missing and the install converges instead of restarting from zero;
#  - --prefer-binary avoids sdist builds, cutting the number of transfers;
#  - the loop retries the whole install, sleeping between attempts.
# pip is not self-upgraded here — that download was itself failing, and the
# base image's pip installs every pinned wheel fine.
RUN --mount=type=cache,target=/root/.cache/pip \
    for attempt in 1 2 3 4 5 6; do \
        echo "pip install attempt ${attempt}/6"; \
        pip install --prefer-binary -r /app/apps/api/requirements.txt && break; \
        if [ "${attempt}" = 6 ]; then echo "pip install failed after 6 attempts" >&2; exit 1; fi; \
        echo "retrying in 15s..."; sleep 15; \
    done

COPY app /app/app
COPY apps /app/apps
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY scripts /app/scripts
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh /app/scripts/run_crawl_worker.sh \
    && mkdir -p /app/exports

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
