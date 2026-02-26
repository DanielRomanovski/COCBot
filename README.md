# COCBot — Clash of Clans Automation Framework

A **server-side** CoC bot built in Python. Runs entirely headless on a Linux server using a dockerised Android emulator — no physical device or monitor required.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    COCBot (Python)                           │
│                                                             │
│  src/cocbot/                                                │
│    config.py          ← Pydantic settings from .env        │
│    main.py            ← Entry point & task scheduler       │
│                                                             │
│    adb/                                                     │
│      device.py        ← ADB TCP connection, screenshot,    │
│                          tap, swipe, app control            │
│      input.py         ← Async human-like input wrapper     │
│                                                             │
│    vision/                                                  │
│      matcher.py       ← OpenCV template matching           │
│      ocr.py           ← pytesseract number/text reading    │
│                                                             │
│    api/                                                     │
│      client.py        ← coc.py official API wrapper        │
│                          (read-only: players, clans, wars)  │
│                                                             │
│    game/                                                    │
│      state.py         ← Screen state machine               │
│      navigator.py     ← High-level navigation (menus)      │
│      resources.py     ← Resource dataclasses               │
│                                                             │
│    tasks/                                                   │
│      farm.py          ← Farming loop (find → assess → atk) │
│      war.py           ← War monitoring via API             │
│                                                             │
│    utils/                                                   │
│      delays.py        ← Human-like random delay helpers    │
│      logging.py       ← Loguru setup                       │
└─────────────────────────────────────────────────────────────┘
         │ ADB TCP (port 5555)
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Docker: budtmo/docker-android:emulator_11.0               │
│  - Full Android 11 emulator                                 │
│  - noVNC web viewer on port 6080                            │
│  - ADB exposed on port 5555                                 │
│  - Requires /dev/kvm on the host                            │
└─────────────────────────────────────────────────────────────┘
         │ KVM
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Linux server with KVM support                              │
│  (bare metal or KVM-enabled cloud VM)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Requirements

### Server
- **Linux** with `/dev/kvm` available (hardware virtualisation)
  - AWS: use bare metal instances (`i3.metal`, `c5.metal`)
  - GCP: enable nested virtualisation on your VM
  - Azure: enable nested virtualisation
  - Standard VMs **without KVM will not work** (emulator too slow)
- Docker + Docker Compose
- Python 3.11+ (only needed for local dev — Docker has it)

### Local dev (macOS/Linux)
- Python 3.11+
- Poetry
- `tesseract` installed: `brew install tesseract` / `apt install tesseract-ocr`
- ADB: `brew install android-platform-tools` / `apt install adb`

---

## Quick Start

### 1. Clone & configure

```bash
git clone <your-repo>
cd COCBot
cp .env.example .env
```

Edit `.env`:
- `COC_API_TOKEN` — get from https://developer.clashofclans.com (IP-locked)
- `PLAYER_TAG` — your account's player tag
- `CLAN_TAG` — your clan tag (optional, for war monitoring)

### 2. Start the emulator

```bash
# Check KVM is available
ls /dev/kvm

# Start the Android emulator
docker compose up android -d

# Watch it boot (takes ~2–3 minutes first time)
docker compose logs -f android

# View the screen in your browser
open http://your-server-ip:6080
```

### 3. Set up Clash of Clans on the emulator

Once the emulator is running:

1. Open http://your-server-ip:6080 in a browser (noVNC)
2. Open the Play Store and install Clash of Clans
3. Log in to your account via Supercell ID
4. Leave the game on the main village screen

### 4. Capture template images

Template images tell the bot what buttons look like. You need to capture them once:

```bash
# Install dev dependencies
poetry install

# For each UI element, run:
python tools/capture_template.py --name state_village
python tools/capture_template.py --name state_attack_menu
python tools/capture_template.py --name state_loot_preview
python tools/capture_template.py --name state_in_battle
python tools/capture_template.py --name state_battle_result
python tools/capture_template.py --name state_searching
```

A window will pop up showing the current screen — click and drag to select the element, then press Enter to save it to `assets/templates/`.

### 5. Calibrate coordinates

Button positions vary by device resolution. Verify the coordinates in `src/cocbot/game/navigator.py` match your emulator:

```bash
python tools/find_coords.py
# Click on buttons to print their (x, y) coordinates
```

Update the `Coords` class in `navigator.py` to match.

### 6. Run the bot

```bash
# Full Docker stack (recommended for server use)
docker compose up -d

# Or run locally (emulator in Docker, bot on host)
poetry run cocbot

# Watch logs
docker compose logs -f cocbot
# or
tail -f logs/cocbot.log
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `COC_API_TOKEN` | **required** | Supercell developer API token |
| `PLAYER_TAG` | **required** | Player tag to monitor (e.g. `#ABC123`) |
| `CLAN_TAG` | optional | Clan tag for war monitoring |
| `ADB_HOST` | `localhost` | ADB host (use `android` in Docker) |
| `ADB_PORT` | `5555` | ADB TCP port |
| `EMULATOR_WIDTH` | `1080` | Screen width in pixels |
| `EMULATOR_HEIGHT` | `1920` | Screen height in pixels |
| `BOT_TASKS` | `farm` | Comma-separated tasks: `farm`, `war` |
| `MIN_GOLD` | `200000` | Minimum gold to attack a base |
| `MIN_ELIXIR` | `200000` | Minimum elixir to attack a base |
| `MIN_DARK_ELIXIR` | `1000` | Minimum dark elixir to attack |
| `MAX_SKIP_COUNT` | `50` | Max bases to skip before giving up |
| `ATTACK_CYCLE_INTERVAL` | `600` | Seconds between attack cycles |
| `BREAK_EVERY_N_CYCLES` | `10` | Take a break every N cycles (0=off) |
| `MIN_ACTION_DELAY` | `0.3` | Min delay between actions (seconds) |
| `MAX_ACTION_DELAY` | `1.2` | Max delay between actions (seconds) |

---

## What the Official API Can Do

The official Supercell API (`coc.py`) is **read-only** and used for monitoring:

| Feature | Available |
|---|---|
| Read player stats, troops, heroes | ✅ |
| Read clan info, members, donations | ✅ |
| Read current war state + attacks | ✅ |
| Read CWL groups & rounds | ✅ |
| Read capital raid log | ✅ |
| Event polling (member joined, war state changed) | ✅ |
| **Perform in-game actions** | ❌ Not possible |

All actual in-game actions (attacking, donating, navigating menus) go through the ADB screen automation stack.

---

## Extending the Bot

### Custom troop deployment

Override `FarmingTask.deploy_troops()` in a subclass:

```python
class GiantHealerFarm(FarmingTask):
    async def deploy_troops(self) -> None:
        # Drop giants first, then healers behind them
        await self.input.deploy_troops_line(80, 800, 400, count=10)   # giants
        await asyncio.sleep(2)
        await self.input.deploy_troops_line(80, 900, 400, count=5)    # healers
```

### Adding new tasks

Create a new file in `src/cocbot/tasks/` with an async class, then add it to the task runner in `main.py`.

### AI base analysis (optional)

Uncomment `google-generativeai` in `pyproject.toml` and add `GEMINI_API_KEY` to `.env`. Then send screenshots to Gemini Vision API to decide whether to attack a base.

---

## ⚠️ Legal Notice

Automating Clash of Clans **violates Supercell's Terms of Service** and risks permanent account bans. Use at your own risk and only on accounts you are prepared to lose. The official API is safe to use for read-only stat tracking per Supercell's Fan Content Policy.

---

## Project Structure

```
COCBot/
├── src/cocbot/            # Main package
│   ├── adb/               # ADB device & input
│   ├── api/               # Official CoC API client
│   ├── game/              # State machine & navigation
│   ├── tasks/             # High-level bot tasks
│   ├── utils/             # Logging, delays
│   ├── vision/            # OpenCV + OCR
│   ├── config.py          # Pydantic settings
│   └── main.py            # Entry point
├── assets/
│   └── templates/         # UI template images (add your own)
├── tools/
│   ├── capture_template.py # Interactive template capture
│   └── find_coords.py      # Click to print coordinates
├── tests/                 # Unit tests (no device needed)
├── logs/                  # Runtime logs
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```
