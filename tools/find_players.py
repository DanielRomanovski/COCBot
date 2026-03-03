# Called from notice_board.py while a clan view is open.
# Copies the clan tag via ADB clipboard, fetches members from the CoC API,
# filters by TH level + donations, and appends matching tags to found_players.txt.

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

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
_TAG_RE_E = re.compile(r"(?:#|&#35;|&#x23;)([A-Z0-9]{4,12})")


# ── Tag reading ───────────────────────────────────────────────────────────────

def _read_ui_tag(device: ADBDevice) -> str | None:
    """Read the CoC tag visible on screen via Android UI dump.
    Android XML-encodes '#' as '&#35;', so we match both forms.
    """
    xml = device._shell("uiautomator dump /sdcard/ui_dump.xml >/dev/null 2>&1 && cat /sdcard/ui_dump.xml")
    logger.debug("UI dump length: {} chars", len(xml))
    # Log a snippet around any '#' or '&#' to help diagnose encoding
    upper = xml.upper()
    idx = next((i for i in range(len(upper)) if upper[i:i+1] == '#' or upper[i:i+3] == '&#3'), -1)
    if idx >= 0:
        logger.debug("XML snippet near '#': ...{}...", repr(xml[max(0,idx-10):idx+30]))
    else:
        logger.debug("XML first 200 chars: {}", repr(xml[:200]))
    match = _TAG_RE_E.search(upper)
    if match:
        tag = f"#{match.group(1)}"
        logger.info("UI tag: {}", tag)
        return tag
    logger.warning("No CoC tag found in UI dump (len={})", len(xml))
    return None


def _get_clan_tag(device: ADBDevice) -> str | None:
    """Read the clan tag from the visible UI — no clipboard needed."""
    # The tag is already displayed on the clan view screen; just dump the UI.
    return _read_ui_tag(device)


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
