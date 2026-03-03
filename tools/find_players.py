# Called from notice_board.py while a clan view is open.
# Copies the clan tag via ADB clipboard, fetches members from the CoC API,
# filters by TH level + donations, and appends matching tags to found_players.txt.

from __future__ import annotations

import asyncio
import re
import sys
import time
import urllib.request
from pathlib import Path

# ── Watchdog heartbeat ────────────────────────────────────────────────────────
# Updated every time _get_clan_tag successfully returns a tag.
# notice_board.py monitors this to detect when the clipboard has gone silent.
last_tag_time: float = 0.0

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
load_dotenv()

from cocbot.adb.device import ADBDevice
from cocbot.api.client import CoCAPIClient
from cocbot.config import settings
import config_manager

# Defaults — live values are read from bot_config.json at runtime
MIN_TH         = 14       # minimum town hall level (inclusive)
MAX_TH         = 18       # maximum town hall level (inclusive)
MIN_DONATIONS  = 1000     # minimum monthly troops donated

# Output file — written to tools/found_players.txt
OUTPUT_FILE = Path(__file__).parent / "found_players.txt"

# CoC tags start with #; Android XML-encodes # as &#35; so handle both forms
_TAG_RE   = re.compile(r"#([A-Z0-9]{4,12})")
_TAG_RE_E = re.compile(r"(?:#|&#35;|&#x23;|%23)([A-Z0-9]{4,12})")


# Coordinates on the clan view screen (1440x720)
TAP_SHARE_BTN  = (738, 202)   # share button → reveals Copy + Share options
TAP_COPY_BTN   = (854, 206)   # Copy option → puts tag in Windows clipboard on BlueStacks host

# clipboard_server.py must be running on the BlueStacks Windows machine
_CLIPBOARD_SERVER = f"http://{settings.adb_host}:8765/clipboard"


def _read_http_clipboard() -> str | None:
    """Fetch clipboard text from clipboard_server.py running on the BlueStacks host."""
    try:
        with urllib.request.urlopen(_CLIPBOARD_SERVER, timeout=3) as resp:
            text = resp.read().decode("utf-8").strip().upper()
        logger.debug("HTTP clipboard: {}", text)
        match = _TAG_RE.search(text)
        if match:
            return f"#{match.group(1)}"
        logger.warning("Clipboard had no CoC tag: {}", text)
    except Exception as exc:
        logger.debug("HTTP clipboard server unreachable, falling back to ADB ({})", exc)
    return None


def _read_adb_clipboard(device: ADBDevice) -> str | None:
    """Read Android clipboard via dumpsys — works on Android 10+ (bypasses security restriction)."""
    out = device._shell("dumpsys clipboard 2>/dev/null")
    logger.debug("dumpsys clipboard ({} chars): {}", len(out), repr(out[:300]))
    # Look for the URL or raw tag in the dump
    match = _TAG_RE_E.search(out.upper())
    if match:
        return f"#{match.group(1)}"
    # Also try %23 URL-encoded form
    url_match = re.search(r"tag=%23([A-Z0-9]{4,12})", out.upper())
    if url_match:
        return f"#{url_match.group(1)}"
    logger.warning("No CoC tag in dumpsys clipboard output")
    return None


def _read_clipboard(device: ADBDevice) -> str | None:
    """Try HTTP clipboard bridge (BlueStacks), then fall back to ADB (real phone)."""
    tag = _read_http_clipboard()
    if tag:
        return tag
    return _read_adb_clipboard(device)


def _read_clipboard_via_termux_foreground(device: ADBDevice) -> str | None:
    """Android 10 blocks background clipboard reads, even for Termux.

    Workaround: briefly bring Termux to the foreground so its clipboard
    read is permitted, then switch straight back to CoC.
    """
    logger.debug("Bringing Termux to foreground so it can read clipboard")
    device._shell("am start -n com.termux/.HomeActivity")
    time.sleep(1.5)  # wait for Termux to become focused

    tag = _read_http_clipboard()
    if tag:
        logger.info("Got clan tag via Termux foreground read: {}", tag)
    else:
        logger.warning("Termux foreground clipboard read also returned nothing")

    # Switch back to CoC using monkey launcher — most reliable on all Android versions
    logger.debug("Switching back to CoC")
    device.launch_coc()
    time.sleep(2.5)  # give CoC time to restore its foreground state
    return tag


def _get_clan_tag(device: ADBDevice) -> str | None:
    """Tap Share → Copy (sets Android clipboard), then read it.

    On Android 10+ real phones the clipboard server (Termux) can only read
    while it is in the foreground.  We tap Copy first, then briefly bring
    Termux to front so it can read, then return to CoC.
    """
    time.sleep(1.5)
    logger.info("Tapping Share at {}", TAP_SHARE_BTN)
    device.tap(*TAP_SHARE_BTN)
    time.sleep(2.0)  # wait for share sheet to fully appear

    logger.info("Tapping Copy at {}", TAP_COPY_BTN)
    device.tap(*TAP_COPY_BTN)
    time.sleep(0.5)  # brief pause so CoC finishes writing to clipboard

    # Try direct HTTP read first (works on BlueStacks / rooted / older Android)
    tag = _read_http_clipboard()
    if tag:
        _record_tag_success()
        return tag

    # Android 10 restriction: background apps can't read clipboard.
    # Fix: bring Termux to foreground so it has permission, then return to CoC.
    tag = _read_clipboard_via_termux_foreground(device)
    if tag:
        _record_tag_success()
        return tag

    # Last resort: ADB dumpsys (sometimes works on non-rooted Android 10)
    tag = _read_adb_clipboard(device)
    if tag:
        _record_tag_success()
    return tag


def _record_tag_success() -> None:
    global last_tag_time
    last_tag_time = time.time()


# ── API fetch & filter ────────────────────────────────────────────────────────

async def _fetch_and_filter(clan_tag: str) -> list[str]:
    """Fetch clan members and return tags of those passing the filters."""
    retries = 3
    for attempt in range(retries):
        try:
            async with CoCAPIClient(
                token=settings.coc_api_token,
                player_tag=settings.player_tag,
                clan_tag=clan_tag,
            ) as client:
                members = await client.get_clan_members(clan_tag)
            break
        except Exception as exc:
            msg = str(exc)
            if "429" in msg and attempt < retries - 1:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning("Rate limited — waiting {}s before retry", wait)
                await asyncio.sleep(wait)
            else:
                raise

    logger.info("Clan {} has {} members", clan_tag, len(members))

    # Read live filter values (Discord /config can update these at runtime)
    _c = config_manager.load()
    min_th        = _c.get("min_th",        MIN_TH)
    max_th        = _c.get("max_th",        MAX_TH)
    min_donations = _c.get("min_donations", MIN_DONATIONS)
    logger.debug("Filters: TH {}-{}  donations>={}", min_th, max_th, min_donations)

    matches: list[str] = []
    for m in members:
        th: int        = getattr(m, "town_hall", 0)
        donations: int = getattr(m, "donations", 0)

        if not (min_th <= th <= max_th):
            continue
        if donations < min_donations:
            continue

        logger.info("  MATCH  {} ({})  TH{}  donations={}", m.name, m.tag, th, donations)
        matches.append(m.tag)

    return matches


# ── Public entry-point ────────────────────────────────────────────────────────

def find_players(device: ADBDevice) -> int:
    """
    Called by notice_board.py between "View Clan" and the back-arrow tap.
    Reads the clan tag, queries the API, and saves matching players to
    tools/found_players.txt.
    Returns the number of new players saved.
    """
    clan_tag = _get_clan_tag(device)
    if not clan_tag:
        return 0

    try:
        matches = asyncio.run(_fetch_and_filter(clan_tag))
    except Exception as exc:
        logger.error("API call failed for {}: {}", clan_tag, exc)
        return 0

    if not matches:
        logger.info("No matching players in {}", clan_tag)
        return 0

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("a") as fh:
        for tag in matches:
            fh.write(tag + "\n")

    logger.success(
        "Saved {} player(s) from {} → {}",
        len(matches), clan_tag, OUTPUT_FILE,
    )
    return len(matches)
