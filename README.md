# CoCBot

Automated Clash of Clans clan management bot.  
Runs on a Windows machine — controls the game via ADB on an Android emulator, and is managed through Discord slash commands.

---

## What it does

| Feature | Description |
|---|---|
| **Auto-invite loop** | Scans the in-game Notice Board, filters players by Town Hall / donations, sends invites |
| **Auto-moderation** | Scores every clan member by inactivity, kicks the worst offenders when the clan is full |
| **Activity tracker** | Polls the official CoC API every N hours and records when each member was last active |
| **Discord bot** | Full control and monitoring from Discord — no SSH needed |
| **Console log** | Every tap, API call, and log line is posted to a Discord `#console` channel in real time |

### Discord commands

| Command | Who | Description |
|---|---|---|
| `/leaderboard` | anyone | Clan activity ranked best → worst, with kick targets marked |
| `/invite start [moderate]` | admin | Start the notice-board scan + invite loop |
| `/invite stop` | admin | Stop the loop |
| `/invite status` | anyone | Loop state + current filter values |
| `/config [key] [value]` | admin (write) | View or change any setting live — no restart needed |
| `/screenshot` | admin | Capture the emulator screen and post it |
| `/forcemenu` | admin | Press ESC ×7 + Cancel to recover to the main screen |
| `/help` | anyone | Full command reference |

---

## Requirements

- Windows 10 or 11 (64-bit)
- Python **3.11** or newer — [python.org/downloads](https://www.python.org/downloads/)  
  *(tick "Add python.exe to PATH" during install)*
- An Android emulator (see below)
- A Supercell developer API token — [developer.clashofclans.com](https://developer.clashofclans.com)
- A Discord bot token — [discord.com/developers/applications](https://discord.com/developers/applications)

---

## Install — one command

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

This will:
1. Check Python 3.11+
2. Create a `.venv` virtual environment
3. Install all dependencies
4. Copy `.env.example` → `.env`

Then open `.env` in a text editor and fill in your tokens (see [Configuration](#configuration)).

---

## Android Emulator

You need an Android emulator to run Clash of Clans.  
**BlueStacks is not recommended** — it is heavy, full of ads, and slow on older hardware.

### Recommended: MuMu Player 12 *(free, no ads, lightweight)*

1. Download from [mumuplayer.com](https://www.mumuplayer.com/) and install.
2. Open MuMu Player, go to **Settings → Other settings** and enable **ADB debugging**.
3. Set the resolution to **1920 × 1080**, 240 dpi.
4. Install Clash of Clans from the built-in app store and log in with your Supercell ID.
5. Leave the game on the main village screen.
6. In `.env`, set:
   ```
   ADB_HOST=127.0.0.1
   ADB_PORT=16384
   EMULATOR_WIDTH=1920
   EMULATOR_HEIGHT=1080
   ```

> ADB port for MuMu Player 12 is `16384` for the first instance.  
> If you have multiple instances, use `16386`, `16388`, etc.

### Alternative: LDPlayer 9 *(free, minimal ads)*

1. Download from [ldplayer.net](https://www.ldplayer.net/) and install.
2. Open LDPlayer, go to **Settings → Other → ADB debugging** → enable.
3. Set resolution to **1920 × 1080**, 240 dpi.
4. Install CoC, log in, leave on main screen.
5. In `.env`:
   ```
   ADB_HOST=127.0.0.1
   ADB_PORT=5555
   ```

### Alternative: Android SDK Emulator *(fully free, headless, no GUI needed)*

> Best for running 24/7 on a headless Windows machine.  
> Requires ~5 GB disk for the SDK.

1. Download **Android command-line tools** from  
   [developer.android.com/studio#command-line-tools-only](https://developer.android.com/studio#command-line-tools-only)
2. Extract to `C:\android-sdk\cmdline-tools\latest\`
3. Open PowerShell and run:
   ```powershell
   $env:ANDROID_HOME = "C:\android-sdk"
   # Install an Android 30 image with Play Store
   C:\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat `
     "platform-tools" `
     "emulator" `
     "system-images;android-30;google_apis_playstore;x86_64"

   # Create an AVD called "cocbot"
   C:\android-sdk\cmdline-tools\latest\bin\avdmanager.bat create avd `
     -n cocbot -k "system-images;android-30;google_apis_playstore;x86_64" `
     --device "pixel_4"

   # Start it headless (no window)
   C:\android-sdk\emulator\emulator.exe -avd cocbot -no-window -no-audio
   ```
4. Install CoC via the Play Store (connect to it with `adb shell` or use a VNC viewer).
5. In `.env`:
   ```
   ADB_HOST=127.0.0.1
   ADB_PORT=5554
   ```

---

## Configuration

Edit `.env` (created by the installer):

| Variable | Required | Description |
|---|---|---|
| `COC_API_TOKEN` | ✅ | Token from [developer.clashofclans.com](https://developer.clashofclans.com) — **IP-locked** |
| `PLAYER_TAG` | ✅ | Your CoC player tag (e.g. `#ABC123XYZ`) |
| `ADB_HOST` | ✅ | ADB host — almost always `127.0.0.1` |
| `ADB_PORT` | ✅ | ADB port — depends on emulator (see above) |
| `EMULATOR_WIDTH` | ✅ | Emulator screen width in pixels |
| `EMULATOR_HEIGHT` | ✅ | Emulator screen height in pixels |
| `DISCORD_BOT_TOKEN` | ✅ | Token from [discord.com/developers/applications](https://discord.com/developers/applications) |
| `DISCORD_GUILD_ID` | ✅ | Your Discord server ID |
| `DISCORD_KICK_WEBHOOK` | optional | Webhook URL for kick-report messages |

### Runtime settings (via `/config` in Discord)

These can be changed live without restarting the bot:

| Key | Default | Description |
|---|---|---|
| `min_th` | `14` | Minimum Town Hall to invite |
| `max_th` | `18` | Maximum Town Hall to invite |
| `min_donations` | `1000` | Minimum season donations to invite |
| `invite_every` | `100` | Invite when this many players are queued |
| `moderate_on_invite` | `false` | Also run moderation after each invite batch |
| `players_to_kick` | `2` | Members to kick per moderation run |
| `offline_threshold_days` | `7` | Never kick anyone active within this many days |
| `dry_run` | `true` | `true` = press Cancel (safe test), `false` = real kicks |
| `activity_check_interval_hours` | `3` | How often the activity tracker polls the API |

---

## Running the bot

Make sure:
- `.env` is filled in
- The emulator is running with CoC on the **main village screen**

```powershell
.venv\Scripts\python.exe tools\discord_bot.py
```

The bot will print its startup lines to the terminal and post them to `#console` in Discord. From that point, all control is via Discord slash commands.

To keep it running permanently:

**Option A — Task Scheduler** (simplest)
1. Open Task Scheduler → Create Basic Task
2. Trigger: "When the computer starts"
3. Action: Start a Program → `.venv\Scripts\python.exe`  
   Add arguments: `tools\discord_bot.py`  
   Start in: full path to this folder

**Option B — NSSM (Non-Sucking Service Manager)**
```powershell
# Download nssm from nssm.cc, then:
nssm install CoCBot ".venv\Scripts\python.exe"
nssm set CoCBot AppParameters "tools\discord_bot.py"
nssm set CoCBot AppDirectory "C:\path\to\cocbot"
nssm start CoCBot
```

---

## Discord bot setup

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → New Application.
2. Bot → **Reset Token** → copy into `DISCORD_BOT_TOKEN`.
3. Bot → scroll down → enable **Server Members Intent** and **Message Content Intent**.
4. OAuth2 → URL Generator → Scopes: `bot`, `applications.commands`  
   Bot Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Use Slash Commands`
5. Copy the generated URL, paste it in a browser, and add the bot to your server.
6. Right-click the server name → **Copy Server ID** → paste into `DISCORD_GUILD_ID`.
7. Create a `#console` channel and add a webhook (Server Settings → Integrations → Webhooks).  
   Paste the URL into the console_sink webhook constant in [tools/console_sink.py](tools/console_sink.py).

---

## Project structure

```
cocbot/
├── install.ps1              ← one-command Windows installer
├── requirements.txt         ← pip dependencies
├── pyproject.toml           ← poetry project config
├── .env.example             ← copy to .env and fill in tokens
│
├── src/cocbot/
│   ├── adb/device.py        ← ADB connection, tap, swipe, screenshot
│   ├── api/client.py        ← CoC official API wrapper (read-only)
│   ├── config.py            ← Pydantic settings from .env
│   └── __init__.py
│
└── tools/
    ├── discord_bot.py       ← Discord bot (main entry point)
    ├── notice_board.py      ← ADB: scan notice board, collect clan lists
    ├── find_players.py      ← ADB: filter and queue player tags from clans
    ├── invite_players.py    ← ADB: search each tag and send invite
    ├── moderation.py        ← API: rank members + ADB: kick worst members
    ├── config_manager.py    ← Runtime config (bot_config.json)
    ├── console_sink.py      ← Loguru → Discord #console webhook
    └── capture_template.py  ← Dev tool: capture UI template images
```

---

## ⚠️ Legal notice

Automating Clash of Clans **violates Supercell's Terms of Service** and may result in a permanent ban. Use only on accounts you are prepared to lose. The official CoC API is safe to use for read-only stat monitoring per the Supercell Fan Content Policy.
