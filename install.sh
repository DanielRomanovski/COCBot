#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CoCBot — Ubuntu / Debian installer
#
# Usage:
#   chmod +x install.sh && ./install.sh
#
# What it does:
#   1. Installs system dependencies (Python 3.11, tesseract-ocr, adb)
#   2. Creates a .venv virtual environment
#   3. Installs all Python dependencies
#   4. Copies .env.example → .env if .env doesn't exist yet
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── 1. System dependencies ───────────────────────────────────────────────────
info "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    tesseract-ocr \
    adb

# ── 2. Python version check ──────────────────────────────────────────────────
PYTHON=""
for cmd in python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(sys.version_info >= (3,11))" 2>/dev/null || echo "False")
        if [ "$ver" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

[ -n "$PYTHON" ] || error "Python 3.11+ not found even after install. Check your OS."
info "Using Python: $($PYTHON --version)"

# ── 3. Virtual environment ───────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    info "Creating virtual environment (.venv)..."
    "$PYTHON" -m venv .venv
else
    info ".venv already exists — skipping creation."
fi

VENV_PYTHON=".venv/bin/python"

# ── 4. Install Python dependencies ──────────────────────────────────────────
info "Installing Python dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip -q
"$VENV_PYTHON" -m pip install -r requirements.txt -q
info "Dependencies installed."

# ── 5. Environment file ───────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    info ".env created from .env.example — fill in your tokens before running."
else
    warn ".env already exists — not overwriting."
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Install complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Edit .env and fill in:"
echo "       COC_API_TOKEN, PLAYER_TAG"
echo "       DISCORD_BOT_TOKEN, DISCORD_GUILD_ID"
echo "       ADB_HOST / ADB_PORT for your emulator"
echo ""
echo "  2. Start your Android emulator and launch CoC"
echo "     (or use Docker Compose — see README.md)"
echo ""
echo "  3. Run the bot:"
echo "       .venv/bin/python tools/discord_bot.py"
echo ""
echo "  For 24/7 operation use systemd (see README.md)"
echo ""
