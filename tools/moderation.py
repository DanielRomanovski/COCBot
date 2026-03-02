# Scores clan members by inactivity via the CoC API (worst → best), then
# navigates the in-game member list, copies each player's tag via the share
# sheet, and kicks the configured number of worst eligible players.
#
# dry_run (config key) controls whether the kick dialog is confirmed or cancelled.
# All thresholds are read live from bot_config.json via config_manager.

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
load_dotenv()

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.api.client import CoCAPIClient
from cocbot.config import settings

# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
MY_CLAN_TAG            = "#2QQCCYQP"
PLAYERS_TO_KICK        = 2             # number of members to remove per run
OFFLINE_THRESHOLD_DAYS = 7             # never kick anyone online within this many days
DRY_RUN                = True          # True  = press Cancel (safe test mode)
                                       # False = press Confirm (real kicks)
STEP_MODE              = False        # True = pause before every tap (debug only)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Coordinates ───────────────────────────────────────────────────────────────
PROFILE_BUTTON  = (76,   62)           # top-left profile icon
MY_CLAN_BUTTON  = (814,  92)           # "my clan" button next to profile
SORT_FILTER_BTN = (1000, 842)          # sort/filter toggle (press 3× → Last Active)
SHARE_ICON      = (766,  294)          # share icon on member profile page
COPY_TAG_BTN    = (938,  310)          # "Copy player tag" from share sheet
BACK_ARROW      = (266,  80)           # back arrow (member profile → member list)
CONFIRM_KICK    = (1188, 508)          # kick confirmation dialog — OK
CANCEL_KICK     = (734,  506)          # kick confirmation dialog — Cancel

# Bottom-of-list rows after scrolling all the way down.
# Index 0 = very last player, 1 = second-to-last, … up to 5.
# Each tuple: (player_tap, profile_btn, kick_btn)
BOTTOM_ROWS = [
    ((968, 962),  (1172, 666),  (1174, 994)),   # 0 – last (very bottom)
    ((912, 832),  (1164, 648),  (1166, 992)),   # 1 – 2nd from bottom
    ((928, 710),  (1170, 550),  (1166, 874)),   # 2 – 3rd from bottom
    ((890, 584),  (1170, 416),  (1170, 758)),   # 3 – 4th from bottom
    ((906, 454),  (1172, 292),  (1172, 636)),   # 4 – 5th from bottom
    ((870, 330),  (1182, 158),  (1156, 500)),   # 5 – 6th from bottom
]

# Regex to find a CoC tag in clipboard text
_TAG_RE = re.compile(r"#([A-Z0-9]{4,12})")

# Activity snapshot file — persists between runs to measure last-seen
ACTIVITY_FILE = Path(__file__).parent / "member_activity.json"

# Scalar fields from /players/{tag} to snapshot each run.
# NOTE: attackWins / defenseWins are intentionally excluded — they reset to 0
# at each season boundary, causing false "inactive" readings.
_SCALAR_FIELDS = (
    "donations",
    "donationsReceived",
    "warStars",
    "trophies",              # changes every single raid
    "expLevel",              # gains XP from attacks, donations, build completions
    "builderBaseTrophies",   # separate game mode — changes on every BB attack
    "clanCapitalContributions",
)

# Achievements to snapshot (name in API → storage key).
# These are lifetime cumulative counters that never reset, so even 1 attack
# will bump them by 50 k+.  Extremely reliable activity signals.
_ACHIEVEMENT_FIELDS = {
    "Gold Grab":       "ach_gold_grab",       # lifetime gold looted
    "Elixir Escapade": "ach_elixir_escapade", # lifetime elixir looted
    "Friend in Need":  "ach_friend_in_need",  # lifetime donations given (never resets)
}

# Combined set of all keys used in activity snapshots.
_ALL_TRACKED = tuple(_SCALAR_FIELDS) + tuple(_ACHIEVEMENT_FIELDS.values())


def _extract_stats(raw: dict) -> dict:
    """Flatten scalar fields + selected achievements into one dict."""
    stats: dict = {f: raw.get(f, 0) for f in _SCALAR_FIELDS}
    ach_map = {a["name"]: a.get("value", 0) for a in raw.get("achievements", []) if "name" in a}
    for ach_name, key in _ACHIEVEMENT_FIELDS.items():
        stats[key] = ach_map.get(ach_name, 0)
    return stats


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MemberScore:
    tag: str
    name: str
    role: str
    donations: int
    days_offline: float | None     # None = no activity data yet (new to tracker)
    excluded: bool
    badness: float = 0.0           # higher = worse


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tap(device: ADBDevice, x: int, y: int, label: str, delay: float = 1.0) -> None:
    if STEP_MODE:
        input(f"  [STEP] Press Enter to tap '{label}' at ({x}, {y})… ")
    logger.info("Tapping {} at ({}, {})", label, x, y)
    device.tap(x, y)
    time.sleep(delay)


def _press_back(device: ADBDevice, times: int = 1, delay: float = 0.5) -> None:
    for _ in range(times):
        device.press_back()
        time.sleep(delay)


def _read_clipboard() -> str | None:
    """Read the host clipboard via PowerShell and extract a CoC player tag.
    Windows-only: works because the emulator syncs its clipboard to the host.
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
        capture_output=True, text=True,
    )
    text = result.stdout.strip().upper()
    logger.debug("Clipboard content: {}", text)
    match = _TAG_RE.search(text)
    if match:
        tag = f"#{match.group(1)}"
        logger.info("Read tag from clipboard: {}", tag)
        return tag
    logger.warning("No CoC tag found in clipboard: {}", text)
    return None


def _scroll_to_bottom(device: ADBDevice) -> None:
    """Swipe upward many times to reach the very bottom of the member list."""
    logger.info("Scrolling to bottom of member list…")
    for _ in range(10):
        device.swipe(960, 800, 960, 200, 600)
        time.sleep(0.4)
    # Two final slow swipes to fully settle
    device.swipe(960, 900, 960, 200, 800)
    time.sleep(0.5)
    device.swipe(960, 900, 960, 200, 800)
    time.sleep(0.8)


# ── Activity tracker ─────────────────────────────────────────────────────────

def _load_activity() -> dict:
    """Load the activity snapshot from disk, or return empty dict."""
    if ACTIVITY_FILE.exists():
        try:
            return json.loads(ACTIVITY_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_activity(data: dict) -> None:
    ACTIVITY_FILE.write_text(json.dumps(data, indent=2))


def _update_player_activity(activity: dict, tag: str, current_stats: dict) -> float | None:
    """
    Compare current_stats against the stored snapshot for tag.
    Updates last_seen if anything changed.
    Returns days since last activity, or None if no baseline exists yet.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    entry = activity.get(tag)
    if entry is None:
        # First time we've seen this player.
        # Record stats but leave last_seen = None — we have no baseline yet.
        activity[tag] = {"last_seen": None, **{f: current_stats.get(f, 0) for f in _ALL_TRACKED}}
        return None

    # Only count a field as "changed" if it was already in the stored entry.
    # New fields (added after a schema update) are silently seeded on first run
    # without falsely marking the player as "active now".
    changed = any(
        f in entry and current_stats.get(f, 0) != entry[f]
        for f in _ALL_TRACKED
    )
    if changed:
        entry["last_seen"] = now_iso
    # Always update stored values (seeds new fields silently)
    for f in _ALL_TRACKED:
        entry[f] = current_stats.get(f, 0)

    last_seen_raw = entry.get("last_seen")
    if last_seen_raw is None:
        # Stats haven't changed since we first recorded them — we still don't
        # know when they were truly last active, only that they haven't changed
        # since our first snapshot.  Return None to use donations-only ranking.
        return None

    try:
        last_seen_dt = datetime.fromisoformat(last_seen_raw)
        if last_seen_dt.tzinfo is None:
            last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - last_seen_dt).total_seconds() / 86400)
    except Exception:
        return None


# ── API scoring ───────────────────────────────────────────────────────────────

async def _is_clan_full_async() -> bool:
    """Return True if MY_CLAN_TAG currently has 50/50 members."""
    async with CoCAPIClient(
        token=settings.coc_api_token,
        player_tag=settings.player_tag,
        clan_tag=MY_CLAN_TAG,
    ) as client:
        clan = await client.get_clan(MY_CLAN_TAG)
    full = clan.member_count >= 50
    logger.info("Clan {}: {}/50 — full={}", MY_CLAN_TAG, clan.member_count, full)
    return full


def is_clan_full() -> bool:
    """Synchronous wrapper — returns True if the clan is at 50/50."""
    return asyncio.run(_is_clan_full_async())


def _mod_cfg() -> dict:
    """Return live moderation config, falling back to module-level constants."""
    try:
        import config_manager as _cm
        c = _cm.load()
        return {
            "players_to_kick":       int(c.get("players_to_kick",       PLAYERS_TO_KICK)),
            "offline_threshold_days": float(c.get("offline_threshold_days", OFFLINE_THRESHOLD_DAYS)),
            "dry_run":               bool(c.get("dry_run",               DRY_RUN)),
        }
    except Exception:
        return {"players_to_kick": PLAYERS_TO_KICK, "offline_threshold_days": OFFLINE_THRESHOLD_DAYS, "dry_run": DRY_RUN}


async def _fetch_ranked_members() -> list[MemberScore]:
    """
    Fetch all clan members, then fetch each player's full profile in parallel
    to capture war stats, attack wins, etc.  Compare against the stored
    activity snapshot to determine days-since-last-active.
    Rank WORST → BEST: primary = days_offline desc, tiebreak = donations asc.
    Leaders, co-leaders, and elders are excluded from kicking.
    """
    async with CoCAPIClient(
        token=settings.coc_api_token,
        player_tag=settings.player_tag,
        clan_tag=MY_CLAN_TAG,
    ) as client:
        members = await client.get_clan_members(MY_CLAN_TAG)

        # Fetch all individual player profiles in parallel
        player_details = await asyncio.gather(
            *[client.client.get_player(m.tag) for m in members],
            return_exceptions=True,
        )

    activity = _load_activity()
    scores: list[MemberScore] = []

    for m, detail in zip(members, player_details):
        raw_data: dict = (m._raw_data or {}) if hasattr(m, "_raw_data") and m._raw_data else {}
        role_raw: str  = raw_data.get("role") or (str(m.role).lower().replace("-", "") if m.role else "member")
        role_display: str = str(m.role) if m.role else role_raw
        donations: int = getattr(m, "donations", 0) or 0

        # Pull tracked stats from individual profile
        if isinstance(detail, Exception):
            logger.warning("Could not fetch player profile for {}: {}", m.tag, detail)
            current_stats = {"donations": donations}
        else:
            detail_raw: dict = (detail._raw_data or {}) if hasattr(detail, "_raw_data") and detail._raw_data else {}
            current_stats = _extract_stats(detail_raw)
            current_stats["donations"] = donations   # use clan-season value, not global

        days_offline = _update_player_activity(activity, m.tag, current_stats)

        # Leaders / co-leaders / elders are never kicked.
        # Exclude anyone with known recent activity (within threshold).
        # Players with unknown activity (days_offline is None) are NOT excluded
        # — they rank by donations only until we have real data.
        offline_threshold = _mod_cfg()["offline_threshold_days"]
        excluded = (
            role_raw in ("leader", "coLeader", "admin")
            or (days_offline is not None and days_offline < offline_threshold)
        )

        # Worst = most days offline first; tiebreak by fewer donations.
        # Unknown (None) → treated as 0 days for sorting — they sink to the
        # bottom of the kick list below confirmed-inactive players.
        sort_days = days_offline if days_offline is not None else 0.0
        badness = sort_days * 1000 - donations

        scores.append(MemberScore(
            tag=m.tag,
            name=m.name,
            role=role_display,
            donations=donations,
            days_offline=round(days_offline, 1) if days_offline is not None else None,
            excluded=excluded,
            badness=badness,
        ))

    _save_activity(activity)
    scores.sort(key=lambda s: s.badness, reverse=True)   # worst first
    return scores


def _log_rankings(ranked: list[MemberScore]) -> None:
    logger.info("━━━  Clan member rankings (WORST → BEST)  ━━━")
    for i, m in enumerate(ranked, 1):
        flag = " [EXCLUDED]" if m.excluded else ""
        offline_str = f"{m.days_offline:>5.1f}d" if m.days_offline is not None else "  ???"
        logger.info(
            "  {:>2}. {:20s} {:12s}  role={:10s}  donations={:>5}  offline={}  {}",
            i, m.name, m.tag, m.role, m.donations, offline_str, flag,
        )


async def _post_kick_report(kicked: list[MemberScore]) -> None:
    """Post a moderation summary embed to DISCORD_KICK_WEBHOOK (if configured)."""
    webhook_url = os.getenv("DISCORD_KICK_WEBHOOK", "")
    if not webhook_url:
        return

    dry_run = _mod_cfg()["dry_run"]

    lines: list[str] = []
    for m in kicked:
        offline = f"{m.days_offline:.1f}d" if m.days_offline is not None else "unknown"
        if dry_run:
            lines.append(f"🔇 **[DRY RUN]** Would kick **{m.name}** `{m.tag}` — {offline} offline, {m.donations} donations")
        else:
            lines.append(f"🔨 Kicked **{m.name}** `{m.tag}` — {offline} offline, {m.donations} donations")

    if not lines:
        return

    payload = {
        "username": "CoCBot",
        "embeds": [{
            "title": "⚔️ Moderation Report",
            "description": "\n".join(lines),
            "color": 0xFFA500 if dry_run else 0xFF4444,
            "footer": {"text": "DRY RUN — no real kicks were performed" if dry_run else "Live run — players removed from clan"},
        }],
    }

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(webhook_url, json=payload)
            if resp.status not in (200, 204):
                logger.warning("Discord webhook returned HTTP {}", resp.status)
            else:
                logger.info("Discord kick report posted.")
    except Exception as exc:
        logger.warning("Discord webhook failed: {}", exc)


# ── In-game navigation ────────────────────────────────────────────────────────

def _navigate_to_member_list(device: ADBDevice) -> None:
    """From the main village screen: open Profile → My Clan → sort by Last Active."""
    _tap(device, *PROFILE_BUTTON, "Profile",          delay=1.2)
    _tap(device, *MY_CLAN_BUTTON, "My Clan",          delay=1.5)
    # Press sort/filter 3× to reach "Last Active" sort
    for i in range(3):
        _tap(device, *SORT_FILTER_BTN, f"Sort filter ({i+1}/3)", delay=0.7)
    time.sleep(0.5)


def _get_tag_at_row(device: ADBDevice, row_index: int) -> str | None:
    """
    Tap the player at row_index (from bottom), open their profile page,
    copy their tag via the share sheet, press Back, and return the tag.
    Call this while already at the bottom-scrolled member list.
    """
    player_coord, profile_coord, _kick_coord = BOTTOM_ROWS[row_index]

    _tap(device, *player_coord,  f"Player row {row_index}",          delay=0.8)
    _tap(device, *profile_coord, f"Profile btn row {row_index}",     delay=1.2)
    _tap(device, *SHARE_ICON,    "Share icon",                       delay=0.8)
    _tap(device, *COPY_TAG_BTN,  "Copy player tag",                  delay=0.5)

    tag = _read_clipboard()

    # Back to the member list (closes share sheet and profile)
    _tap(device, *BACK_ARROW, "Back arrow", delay=0.8)

    return tag


def _kick_player_at_row(device: ADBDevice, row_index: int) -> None:
    """
    Tap the player at row_index, tap their Kick button, then confirm or
    cancel based on DRY_RUN.  After this the game returns to the
    unscrolled clan member list.
    """
    player_coord, _profile_coord, kick_coord = BOTTOM_ROWS[row_index]
    dry_run = _mod_cfg()["dry_run"]

    _tap(device, *player_coord, f"Player row {row_index} (kick)",  delay=0.8)
    _tap(device, *kick_coord,   f"Kick btn row {row_index}",       delay=1.2)

    if dry_run:
        logger.warning("dry_run=True — pressing Cancel (no real kick)")
        _tap(device, *CANCEL_KICK, "Cancel kick (dry run)", delay=1.0)
    else:
        _tap(device, *CONFIRM_KICK, "Confirm kick", delay=1.0)


# ── Main moderation pass ──────────────────────────────────────────────────────

def run_moderation(device: ADBDevice) -> None:
    """
    Score every clan member via the API, navigate to the clan screen,
    scroll to the bottom, identify players by copying their tags, and
    kick the configured number of worst eligible members.
    """
    _cfg = _mod_cfg()
    players_to_kick = _cfg["players_to_kick"]
    dry_run         = _cfg["dry_run"]
    logger.info("=== Moderation start (dry_run={}, players_to_kick={}) ===", dry_run, players_to_kick)

    # 1 ── Fetch and rank members
    ranked = asyncio.run(_fetch_ranked_members())
    _log_rankings(ranked)

    kick_queue: list[MemberScore] = [m for m in ranked if not m.excluded][:players_to_kick]

    if not kick_queue:
        logger.warning("No eligible members to kick — all excluded.")
        return

    logger.info("Targeting for kick:")
    for m in kick_queue:
        offline_str = f"{m.days_offline:.1f}d" if m.days_offline is not None else "???"
        logger.info("  → {} ({})  donations={}  offline={}", m.name, m.tag, m.donations, offline_str)

    kick_tags_remaining: list[str] = [m.tag for m in kick_queue]

    # 2 ── Navigate to clan member list and scroll to bottom
    _navigate_to_member_list(device)
    _scroll_to_bottom(device)

    kicked_count = 0

    while kicked_count < len(kick_queue):
        targets = set(kick_tags_remaining[kicked_count:])
        found_row: Optional[int] = None
        found_tag: Optional[str] = None

        # Scan visible bottom rows for a target
        for row_index in range(len(BOTTOM_ROWS)):
            tag = _get_tag_at_row(device, row_index)
            if tag is None:
                logger.warning("Could not read tag at row {} — skipping", row_index)
                continue

            if tag in targets:
                logger.info("Found target {} at row {}", tag, row_index)
                found_row = row_index
                found_tag = tag
                break
            else:
                logger.info("Row {} = {} — not a target, checking next", row_index, tag)

        if found_row is None or found_tag is None:
            logger.error(
                "No kick target found in the bottom {} rows. Stopping moderation.",
                len(BOTTOM_ROWS),
            )
            break

        # 3 ── Kick them
        _kick_player_at_row(device, found_row)
        logger.success("Kicked {} (dry_run={})", found_tag, _mod_cfg()["dry_run"])
        kicked_count += 1

        if kicked_count < len(kick_queue):
            # After a kick/cancel the game always returns to the main village
            # screen, so we must navigate all the way back in.
            logger.info("Re-navigating to member list for next kick…")
            _navigate_to_member_list(device)
            _scroll_to_bottom(device)

    logger.info("=== Moderation complete — kicked {}/{} ===", kicked_count, len(kick_queue))

    # Post kick report to Discord (if webhook is configured)
    kicked_members = kick_queue[:kicked_count]
    asyncio.run(_post_kick_report(kicked_members))

    # Leave gracefully: back out to main village screen
    # Also tap Cancel at (754, 698) in case over-pressing ESC opened a "leave game" dialog.
    _press_back(device, times=3, delay=0.6)
    _tap(device, 754, 698, "Cancel (failsafe)", delay=0.8)


# ── Standalone entry-point ────────────────────────────────────────────────────

def main() -> None:
    import console_sink
    console_sink.setup("moderation")
    cfg = DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    )
    device = ADBDevice(cfg)
    logger.info("Connecting to ADB…")
    device.connect()
    run_moderation(device)


if __name__ == "__main__":
    main()
