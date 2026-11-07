# syntax=docker/dockerfile:1
# Slim run-only image for dedup_cleaner (stdlib + cryptography).
#
# Safety: the image ships with dry-run ON and the deletion master switch OFF.
# Real paths, the Fernet key, and the flags come from docker-compose env /
# a mounted `.env` -- never baked into the image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Create a non-root user; the tree is passed in as a volume.
RUN useradd --create-home --shell /usr/sbin/nologin dedup

WORKDIR /app

# Install the single runtime dependency before copying code (layer cache).
RUN pip install --no-cache-dir "cryptography>=42.0"

COPY dedup_cleaner ./dedup_cleaner
COPY tools/dedup_cleaner.py ./tools/dedup_cleaner.py

# State CSV (encrypted) lives here by default; compose mounts a volume onto it.
RUN mkdir -p /volume/dedup/state \
    && chown -R dedup:dedup /volume /app
VOLUME ["/volume/dedup/state"]

# Safety defaults (can/should be overridden by compose env).
ENV DEDUP_DRY_RUN=true \
    DEDUP_ALLOW_DELETE=false

USER dedup
ENTRYPOINT ["python", "-m", "dedup_cleaner"]
# Compose supplies the actual flags, e.g.:
#   docker run --rm --env-file .env -v ${DEDUP_ROOT}:/data:ro -v dedup_state:/volume/dedup/state \
#     dedup_cleaner --root /data   # (real paths/flags come from .env, never the image)
