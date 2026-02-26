# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN pip install poetry==1.8.3

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --no-root --only main

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ADB
    adb \
    # OpenCV
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1-mesa-glx \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    # Misc
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY src/ ./src/
COPY assets/ ./assets/

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

# Create log directory
RUN mkdir -p /app/logs

ENTRYPOINT ["python", "-m", "cocbot.main"]
