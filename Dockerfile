FROM python:3.11-slim

# System dependencies:
#   tesseract-ocr   — OCR for reading in-game numbers
#   adb             — ADB client to talk to the Android emulator
#   netcat-openbsd  — used in healthcheck / wait scripts
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        adb \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ src/
COPY tools/ tools/

# Persistent data files are mounted as volumes (see docker-compose.yml)
# so that bot_config.json and member_activity.json survive container restarts.

CMD ["python", "tools/discord_bot.py"]
