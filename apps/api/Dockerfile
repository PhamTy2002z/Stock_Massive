FROM python:3.12-slim

WORKDIR /code

# Install build dependencies for packages requiring C compilation (e.g., wordcloud)
# netcat-openbsd provides `nc`, used by entrypoint.sh to wait for the database
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /bin/bash app

# Install dependencies first (cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=app:app . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Not root, like the production image. The bind-mounted `src` and `alembic` only
# need to be readable; vnstock's device files and the matplotlib cache land in
# this user's home. uid 1000 is the usual first user on a Linux host, so
# `__pycache__` in the mount stays writable there too (Docker Desktop maps any
# uid). A one-off `pip install` inside the container falls back to a user
# install; use `docker compose exec -u root api ...` for anything else.
USER app

# Health check.
#
# The interval is what `docker compose up --wait` waits on, so it is also how
# long `pnpm dev` serves a frontend against an API that is already up. At 30s a
# container that finished booting was still reported "starting" for most of a
# minute after it began answering.
#
# The start period has to cover a whole cold boot instead: waiting for the
# database, applying migrations, and the Capability Probe's five live route
# checks, which alone take about thirty seconds. Checks that fail inside it do
# not count toward `retries`, so a slow-but-healthy boot is never mistaken for
# an unhealthy container.
HEALTHCHECK --interval=5s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Entrypoint waits for the database and applies migrations before starting
ENTRYPOINT ["./entrypoint.sh"]

# Run with uvicorn (no reload for stability in Docker)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
