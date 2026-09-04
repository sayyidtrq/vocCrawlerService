# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=20

WORKDIR /app

# curl is required by the docker-compose healthcheck. Chromium and its
# distribution-matched driver keep Selenium independent from runtime downloads.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        chromium \
        chromium-driver \
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
