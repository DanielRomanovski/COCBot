#!/usr/bin/env pwsh
<#
.SYNOPSIS
    One-command setup for CoCBot on Windows.
.DESCRIPTION
    - Checks Python 3.11+
    - Creates a virtual environment
    - Installs all Python dependencies
    - Copies .env.example → .env (if .env does not exist)
    - Prints next-steps reminder
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

function Write-OK([string]$msg) {
    Write-Host "    OK  $msg" -ForegroundColor Green
}

function Write-Fail([string]$msg) {
    Write-Host "    ERR $msg" -ForegroundColor Red
    exit 1
}

# ── 1. Python version check ───────────────────────────────────────────────────
Write-Step "Checking Python version..."
$pyCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 11) {
                $pyCmd = $cmd
                Write-OK "Found $ver via '$cmd'"
                break
            }
        }
    } catch {}
}
if (-not $pyCmd) {
    Write-Host @"

    Python 3.11 or newer is required but was not found.
    Download it from:  https://www.python.org/downloads/
    Make sure to tick "Add python.exe to PATH" during install.
"@ -ForegroundColor Yellow
    Write-Fail "Python 3.11+ not found."
}

# ── 2. Virtual environment ────────────────────────────────────────────────────
Write-Step "Creating virtual environment (.venv)..."
if (Test-Path ".venv") {
    Write-OK ".venv already exists — skipping creation."
} else {
    & $pyCmd -m venv .venv
    Write-OK ".venv created."
}

$pip  = ".venv\Scripts\pip.exe"
$python = ".venv\Scripts\python.exe"

# ── 3. Install dependencies ───────────────────────────────────────────────────
Write-Step "Installing Python dependencies from requirements.txt..."
& $pip install --upgrade pip --quiet
& $pip install -r requirements.txt
Write-OK "All packages installed."

# ── 4. .env file ─────────────────────────────────────────────────────────────
Write-Step "Setting up .env..."
if (Test-Path ".env") {
    Write-OK ".env already exists — not overwriting."
} else {
    Copy-Item ".env.example" ".env"
    Write-OK "Copied .env.example → .env"
    Write-Host @"

    IMPORTANT: Edit .env before running the bot.
    Open it in a text editor and fill in:
      COC_API_TOKEN      — https://developer.clashofclans.com
      PLAYER_TAG         — your CoC player tag
      DISCORD_BOT_TOKEN  — https://discord.com/developers/applications
      DISCORD_GUILD_ID   — right-click your Discord server → Copy Server ID
"@ -ForegroundColor Yellow
}

# ── 5. Done ───────────────────────────────────────────────────────────────────
Write-Host @"

============================================================
  Setup complete!

  Next steps:
  1. Edit .env with your API tokens (see above).
  2. Install and configure your Android emulator (see README).
  3. Start CoC on the emulator and leave it on the main screen.
  4. Run the Discord bot:
       .venv\Scripts\python.exe tools\discord_bot.py

  Then in your Discord server:
    /invite start     — start scanning and inviting players
    /leaderboard      — show member activity rankings
    /config           — view / change runtime settings
    /help             — full command list
============================================================
"@ -ForegroundColor Green
