# Navigates the Clan Notice Board, taps each clan card, and delegates to
# find_players() to filter and queue player tags for inviting.

from __future__ import annotations

import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.config import settings
from find_players import find_players, OUTPUT_FILE as PLAYERS_FILE
import find_players as _fp_mod
from invite_players import invite_players, _go_to_main
import config_manager


def _queued_players() -> int:
    """Return number of player tags currently waiting in found_players.txt."""
    if not PLAYERS_FILE.exists():
        return 0
    return sum(1 for line in PLAYERS_FILE.read_text().splitlines() if line.strip())


PROFILE_BUTTON = (52,  38)
CLANS_BUTTON   = (838,  54)
REFRESH_BUTTON = (738, 630)
VIEW_CLAN      = (628, 570)
BACK_ARROW     = (250,  62)

CLAN_CHORDS = [
    (468, 230),  # Clan 1
    (978, 218),  # Clan 2
    (442, 436),  # Clan 3
    (1008, 428), # Clan 4
    (480, 648),  # Clan 5
    (988, 660),  # Clan 6
]

CLAN7_10_CHORDS = [
    (466, 220),  # Clan 7
    (972, 236),  # Clan 8
    (482, 444),  # Clan 9
    (992, 448),  # Clan 10
]

DELAY_AFTER_TAP = 1.5

# ── Watchdog ────────────────────────────────────────────────────────────────
# If no clipboard tag is successfully read for this many seconds while
# notice_board/find_players are running, trigger a recovery action.
WATCHDOG_SECS = 60

# Shared watchdog state (written by watchdog thread, read by main loop)
_watchdog_event  = threading.Event()   # set = recovery needed
_watchdog_level  = [0]                 # 1 = forcemenu+restart, 2 = game restart
_post_l1_time    = [0.0]               # time at which level-1 recovery was attempted


class _WatchdogTriggered(Exception):
    def __init__(self, level: int) -> None:
        self.level = level
        super().__init__(f"Watchdog level {level}")


def _watchdog_thread_fn(stop: threading.Event) -> None:
    """Background daemon: sets _watchdog_event if clipboard has been silent too long."""
    while not stop.is_set():
        stop.wait(5)          # check every 5 seconds
        if _watchdog_event.is_set():
            continue          # already pending, don't overwrite level
        elapsed = time.time() - _fp_mod.last_tag_time
        if elapsed < WATCHDOG_SECS:
            continue
        # Decide level: if level-1 already ran and STILL nothing after WATCHDOG_SECS → level 2
        if _post_l1_time[0] > 0 and (time.time() - _post_l1_time[0]) >= WATCHDOG_SECS:
            _watchdog_level[0] = 2
        else:
            _watchdog_level[0] = 1
        logger.warning(
            "Watchdog: no clipboard success for {:.0f}s — scheduling level-{} recovery",
            elapsed, _watchdog_level[0],
        )
        _watchdog_event.set()


def _forcemenu(device: ADBDevice) -> None:
    """ESC ×7 + Cancel — identical to the /forcemenu Discord command."""
    logger.info("Running forcemenu (ESC×7 + Cancel)")
    for _ in range(7):
        device.press_back()
        time.sleep(0.4)
    time.sleep(0.3)
    device.tap(572, 464)   # CANCEL_BUTTON from coords.py
    time.sleep(0.8)


def drag_menu_down(device: ADBDevice):
    """Single swipe down to reveal clans 1-6 (half-scroll)."""
    device.swipe(724, 668, 722, 547, 600)
    time.sleep(1)


def drag_to_top(device: ADBDevice):
    """Swipe 3× to scroll down far enough to reach clans 7-10."""
    for _ in range(3):
        device.swipe(724, 668, 722, 426, 800)
        time.sleep(0.5)
    time.sleep(0.5)


def tap(device: ADBDevice, x: int, y: int, label: str):
    logger.info("Tapping {} at ({}, {})", label, x, y)
    device.tap(x, y)
    time.sleep(1)


def _ensure_clipboard_server(device: ADBDevice) -> None:
    """Ensure clipboard HTTP server is running; restart via Termux if not."""
    url = f"http://{settings.adb_host}:8765/clipboard"
    try:
        urllib.request.urlopen(url, timeout=3)
        logger.info("Clipboard server online at {}", url)
        return
    except Exception:
        logger.warning("Clipboard server offline — launching Termux to restart it")

    device._shell("am start -n com.termux/.HomeActivity")
    time.sleep(2)
    device._shell("input keyevent 113")  # Ctrl+C to kill any running process
    time.sleep(1)
    device._shell("input text 'python ~/clipboard_server.py'")
    device._shell("input keyevent 66")   # Enter

    # Wait up to 20s for server to respond
    for i in range(20):
        time.sleep(1)
        try:
            urllib.request.urlopen(url, timeout=2)
            logger.success("Clipboard server back online after {}s", i + 1)
            break
        except Exception:
            pass
    else:
        logger.error("Clipboard server did not come up after 20s — continuing anyway")

    # Relaunch CoC and wait for it to fully load
    logger.info("Relaunching Clash of Clans...")
    device._shell("am start -n com.supercell.clashofclans/com.supercell.clashofclans.GameApp")
    time.sleep(20)  # slow phone — wait for full load
    logger.info("CoC should be loaded now")


def main() -> None:
    import console_sink
    console_sink.setup("notice_board")
    cfg = DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    )
    device = ADBDevice(cfg)

    logger.info("Connecting to ADB at {}:{}", settings.adb_host, settings.adb_port)
    device.connect()
    _ensure_clipboard_server(device)

    CLAN_STEPS     = [(x, y, f"Clan {i+1}")  for i, (x, y) in enumerate(CLAN_CHORDS)]
    CLAN7_10_STEPS = [(x, y, f"Clan {i+7}")  for i, (x, y) in enumerate(CLAN7_10_CHORDS)]

    def process_clans(steps) -> int:
        """Tap each clan, call find_players, return total new players found.
        Raises _WatchdogTriggered if the watchdog fires mid-scan.
        """
        total = 0
        for x, y, label in steps:
            if _watchdog_event.is_set():
                raise _WatchdogTriggered(_watchdog_level[0])
            tap(device, x, y, label)
            tap(device, *VIEW_CLAN, "View Clan")
            total += find_players(device)
            tap(device, *BACK_ARROW, "Go Back to Clan Search")
        return total

    # Initialise heartbeat so the watchdog doesn't fire before the first tag attempt
    _fp_mod.last_tag_time = time.time()

    # Start watchdog daemon thread
    _wd_stop = threading.Event()
    _wd_thread = threading.Thread(
        target=_watchdog_thread_fn, args=(_wd_stop,), daemon=True, name="watchdog"
    )
    _wd_thread.start()
    logger.info("Watchdog started (timeout={}s)", WATCHDOG_SECS)

    # Navigate to the clan search page once
    tap(device, *PROFILE_BUTTON, "Profile")
    tap(device, *CLANS_BUTTON, "Clans")

    try:
        while True:
            try:
                _watchdog_event.clear()

                # Scroll down to reveal clans 1-6 in the first two columns
                drag_menu_down(device)

                # Clans 1-6
                process_clans(CLAN_STEPS)

                # Check after first batch
                if _queued_players() >= config_manager.get("invite_every"):
                    logger.info("{} players queued — switching to invite mode", _queued_players())
                    invite_players(device, standalone=False)
                    tap(device, *PROFILE_BUTTON, "Profile")
                    tap(device, *CLANS_BUTTON, "Clans")
                    continue

                # Drag back to the top to reach clans 7-10
                drag_to_top(device)

                # Clans 7-10
                process_clans(CLAN7_10_STEPS)

                # Refresh loads a new set of clans
                tap(device, *REFRESH_BUTTON, "Refresh")
                logger.info("Refresh complete — {} player(s) queued", _queued_players())

                # Check after second batch / refresh
                if _queued_players() >= config_manager.get("invite_every"):
                    logger.info("{} players queued — switching to invite mode", _queued_players())
                    invite_players(device, standalone=False)
                    tap(device, *PROFILE_BUTTON, "Profile")
                    tap(device, *CLANS_BUTTON, "Clans")

            except _WatchdogTriggered as exc:
                _watchdog_event.clear()

                if exc.level == 1:
                    logger.warning(
                        "Watchdog level 1: no clipboard success for {}s — "
                        "running forcemenu and restarting scan",
                        WATCHDOG_SECS,
                    )
                    _forcemenu(device)
                    _post_l1_time[0] = time.time()
                    _fp_mod.last_tag_time = time.time()  # reset heartbeat
                    tap(device, *PROFILE_BUTTON, "Profile")
                    tap(device, *CLANS_BUTTON, "Clans")

                else:  # level 2
                    logger.error(
                        "Watchdog level 2: clipboard still silent after level-1 recovery — "
                        "restarting game and waiting 120s"
                    )
                    device.force_stop_coc()
                    time.sleep(3)
                    device.launch_coc()
                    time.sleep(120)   # slow phone — wait for full load
                    _forcemenu(device)
                    _post_l1_time[0] = 0.0          # reset level tracking
                    _fp_mod.last_tag_time = time.time()
                    tap(device, *PROFILE_BUTTON, "Profile")
                    tap(device, *CLANS_BUTTON, "Clans")

    finally:
        _wd_stop.set()


if __name__ == "__main__":
    main()
