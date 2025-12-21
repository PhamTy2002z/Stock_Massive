FROM python:3.11-slim

WORKDIR /code

# Install build dependencies for packages requiring C compilation (e.g., wordcloud)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn (no reload for stability in Docker)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
