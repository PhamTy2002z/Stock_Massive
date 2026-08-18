# 3.12 is a floor, not a preference: FiinQuantX 0.1.67 ships an f-string that
# nests the same quote character, which only parses from 3.12 on (PEP 701).
# Under 3.11 `import FiinQuantX` dies with a SyntaxError, the Collector reports
# "FiinQuant login failed" for every symbol, and market and valuation silently
# come back empty while vnstock keeps working.
FROM python:3.12-slim

WORKDIR /code

# Install build dependencies for packages requiring C compilation (e.g., wordcloud)
# netcat-openbsd provides `nc`, used by entrypoint.sh to wait for the database
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Entrypoint waits for the database and applies migrations before starting
ENTRYPOINT ["./entrypoint.sh"]

# Run with uvicorn (no reload for stability in Docker)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
