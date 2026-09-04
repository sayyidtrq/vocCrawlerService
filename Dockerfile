FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

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

# Networks that build this image drop mid-download (BrokenPipeError), so retry
# the whole install on top of pip's own per-file --retries. --prefer-binary
# avoids sdist builds, cutting the number of fragile transfers. The base
# image's pip installs every pinned wheel here, so it is not upgraded (that
# was itself a failing download).
RUN pip install --prefer-binary -r /app/apps/api/requirements.txt \
    || pip install --prefer-binary -r /app/apps/api/requirements.txt \
    || pip install --prefer-binary -r /app/apps/api/requirements.txt

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
