# Reads player tags from found_players.txt and sends each one a clan invite.
# Navigates: ESC×4 → Profile → Social → Search Players → type tag → Invite.
# Each tag is removed from found_players.txt after a successful invite.
# Standalone: poetry run python tools/invite_players.py

from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
load_dotenv()

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.config import settings

# ── Coordinates (1440x720) ────────────────────────────────────────────────────
PROFILE_BUTTON  = ( 52,  38)
SOCIAL_TAB      = (1058,  62)
SEARCH_PLAYERS  = (1048, 138)
SEARCH_INPUT    = ( 634, 208)
SEARCH_BUTTON   = ( 970, 200)
INVITE_BUTTON   = ( 536, 374)
BACK_ARROW      = ( 250,  62)

# ── File ──────────────────────────────────────────────────────────────────────
PLAYERS_FILE = Path(__file__).parent / "found_players.txt"

# Clipboard HTTP bridge — clipboard_server.py on Windows (BlueStacks)
#                       — Termux clipboard server on Android phone
_CLIPBOARD_SERVER = f"http://{settings.adb_host}:8765/clipboard"


def _clipboard_set(text: str) -> None:
    """Push text to the clipboard server so we can paste it via ADB keyevent."""
    try:
        body = text.encode("utf-8")
        req = urllib.request.Request(
            _CLIPBOARD_SERVER, data=body, method="POST",
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        urllib.request.urlopen(req, timeout=3)
        logger.debug("Clipboard set via HTTP: {}", text)
    except Exception as exc:
        logger.warning("Clipboard server unreachable, falling back to input text ({})", exc)
        # Fallback: direct input text (works on BlueStacks, may drop '#' on phones)
        safe = text.replace("'", "")
        import subprocess
        subprocess.run(
            ["adb", "-s", f"{settings.adb_host}:{settings.adb_port}", "shell", f"input text '{safe}'"],
            capture_output=True,
        )

# ── Helpers ───────────────────────────────────────────────────────────────────

def _tap(device: ADBDevice, x: int, y: int, label: str, delay: float = 1.0) -> None:
    logger.info("Tapping {} at ({}, {})", label, x, y)
    device.tap(x, y)
    time.sleep(delay)


def _press_back(device: ADBDevice, times: int = 1, delay: float = 0.5) -> None:
    for _ in range(times):
        device.press_back()
        time.sleep(delay)


def _read_tags() -> list[str]:
    """Return all non-empty lines from the players file."""
    if not PLAYERS_FILE.exists():
        return []
    lines = PLAYERS_FILE.read_text().splitlines()
    return [l.strip() for l in lines if l.strip()]


def _remove_tag(tag: str) -> None:
    """Remove the first occurrence of tag from the file."""
    if not PLAYERS_FILE.exists():
        return
    tags = _read_tags()
    try:
        tags.remove(tag)
    except ValueError:
        pass
    PLAYERS_FILE.write_text("\n".join(tags) + ("\n" if tags else ""))


# ── Core ──────────────────────────────────────────────────────────────────────

def _navigate_to_search(device: ADBDevice) -> None:
    """Navigate from the main screen to the player-search input."""
    _tap(device, *PROFILE_BUTTON, "Profile")
    _tap(device, *SOCIAL_TAB,     "Social tab")
    _tap(device, *SEARCH_PLAYERS, "Search Players")


def _invite_one(device: ADBDevice, tag: str) -> None:
    """Send a single invite for the given player tag."""
    # Tap the input field and clear any existing text
    _tap(device, *SEARCH_INPUT, "Search input", delay=0.5)
    # Move cursor to end, then backspace enough to erase any tag (max ~15 chars)
    device._shell("input keyevent KEYCODE_MOVE_END " + " ".join(["KEYCODE_DEL"] * 20))
    time.sleep(0.3)

    # Put tag in clipboard via HTTP bridge, then paste — avoids '#' shell escaping issues
    _clipboard_set(tag)
    time.sleep(0.2)
    device._shell("input keyevent KEYCODE_PASTE")
    time.sleep(0.5)

    _tap(device, *SEARCH_BUTTON, "Search", delay=1.5)
    _tap(device, *INVITE_BUTTON, "Invite",  delay=1.0)
    _tap(device, *BACK_ARROW,   "Back",    delay=0.8)


def invite_players(device: ADBDevice, standalone: bool = False) -> None:
    """
    Invite all players listed in found_players.txt.

    Parameters
    ----------
    device     : connected ADBDevice
    standalone : if True, launches notice_board.py via subprocess when done
    """
    tags = _read_tags()
    if not tags:
        logger.info("found_players.txt is empty — nothing to invite")
        _go_to_main(device)
        if standalone:
            _relaunch_notice_board()
        return

    logger.info("Inviting {} player(s)…", len(tags))

    # Reach the main village screen first
    _go_to_main(device)

    # Navigate into player search
    _navigate_to_search(device)

    for tag in tags:
        logger.info("Inviting {}", tag)
        try:
            _invite_one(device, tag)
        except Exception as exc:
            logger.error("Failed to invite {}: {}", tag, exc)
        finally:
            # Always remove from file whether invite succeeded or not,
            # to avoid retrying a bad tag forever
            _remove_tag(tag)

    logger.success("All invites sent.")

    _go_to_main(device)

    # ── Moderation: only run if enabled in config AND clan is full ─────────
    try:
        import config_manager as _cm
        from moderation import is_clan_full, run_moderation
        if _cm.get("moderate_on_invite"):
            if is_clan_full():
                logger.info("Clan is full — running moderation")
                run_moderation(device)
            else:
                logger.info("Clan is not full — skipping moderation")
        else:
            logger.info("moderate_on_invite=False — skipping moderation")
    except Exception as exc:
        logger.error("Moderation failed: {}", exc)
    # ─────────────────────────────────────────────────────────────────────────

    if standalone:
        _relaunch_notice_board()


# Cancel button (dismisses any open dialog / "leave game" prompt after excess ESC presses)
_CANCEL_BTN = (572, 464)


def _go_to_main(device: ADBDevice) -> None:
    """Press Back ×3, then tap Cancel to reach the main village screen safely."""
    logger.info("Pressing Back ×3 + Cancel to reach main screen")
    _press_back(device, times=3, delay=0.6)
    _tap(device, *_CANCEL_BTN, "Cancel (failsafe)", delay=0.8)


def _relaunch_notice_board() -> None:
    """Launch notice_board.py as a new subprocess and exit this process."""
    script = str(Path(__file__).parent / "notice_board.py")
    python = sys.executable
    logger.info("Launching notice_board.py…")
    subprocess.Popen([python, script])
    sys.exit(0)


# ── Standalone entry-point ────────────────────────────────────────────────────

def main() -> None:
    import console_sink
    console_sink.setup("invite_players")
    cfg = DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    )
    device = ADBDevice(cfg)
    logger.info("Connecting to ADB at {}:{}", settings.adb_host, settings.adb_port)
    device.connect()

    invite_players(device, standalone=True)


if __name__ == "__main__":
    main()
