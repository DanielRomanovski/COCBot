# Navigates the Clan Notice Board, taps each clan card, and delegates to
# find_players() to filter and queue player tags for inviting.

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.config import settings
from find_players import find_players, OUTPUT_FILE as PLAYERS_FILE
from invite_players import invite_players, _go_to_main
import config_manager
from coords import (
    sc,
    PROFILE_BUTTON,
    NB_CLANS_BUTTON   as CLANS_BUTTON,
    NB_REFRESH_BUTTON as REFRESH_BUTTON,
    NB_VIEW_CLAN,
    NB_BACK_ARROW,
    NB_CLAN_CHORDS,
    NB_CLAN7_10_CHORDS,
    NB_SCROLL_X       as SCROLL_X,
    NB_SCROLL_FROM_Y  as SCROLL_FROM_Y,
    NB_SCROLL_TO_Y    as SCROLL_TO_Y,
    NB_DRAG_MENU_DOWN_FROM,
    NB_DRAG_MENU_DOWN_TO,
    NB_DRAG_TO_TOP_FROM,
    NB_DRAG_TO_TOP_TO,
)

SCROLL_DURATION = 500    # ms


def _queued_players() -> int:
    """Return number of player tags currently waiting in found_players.txt."""
    if not PLAYERS_FILE.exists():
        return 0
    return sum(1 for line in PLAYERS_FILE.read_text().splitlines() if line.strip())

DELAY_AFTER_TAP    = 1.5  # seconds to wait after tapping a clan card
DELAY_AFTER_SCROLL = 0.5  # pause between consecutive scrolls


def drag_menu_down(device: ADBDevice):
    x1, y1 = NB_DRAG_MENU_DOWN_FROM
    x2, y2 = NB_DRAG_MENU_DOWN_TO
    device.swipe(x1, y1, x2, y2, 600)
    time.sleep(1)


def drag_to_top(device: ADBDevice):
    x1, y1 = NB_DRAG_TO_TOP_FROM
    x2, y2 = NB_DRAG_TO_TOP_TO
    device.swipe(x1, y1, x2, y2, 800)
    time.sleep(1)


def fast_scroll_to_bottom(device: ADBDevice):
    for _ in range(10):
        device.swipe(SCROLL_X, SCROLL_FROM_Y, SCROLL_X, SCROLL_TO_Y, 200)
        time.sleep(0.2)


def tap(device: ADBDevice, x: int, y: int, label: str):
    logger.info("Tapping {} at ({}, {})", label, x, y)
    device.tap(x, y)
    time.sleep(1)


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

    CLAN_STEPS     = [(x, y, f"Clan {i+1}")  for i, (x, y) in enumerate(NB_CLAN_CHORDS)]
    CLAN7_10_STEPS = [(x, y, f"Clan {i+7}")  for i, (x, y) in enumerate(NB_CLAN7_10_CHORDS)]
    VIEW_CLAN  = NB_VIEW_CLAN
    BACK_ARROW = NB_BACK_ARROW

    def process_clans(steps) -> int:
        """Tap each clan, call find_players, return total new players found."""
        total = 0
        for x, y, label in steps:
            tap(device, x, y, label)
            tap(device, *VIEW_CLAN, "View Clan")
            total += find_players(device)
            tap(device, *BACK_ARROW, "Go Back to Clan Search")
        return total

    # Navigate to the clan search page once
    tap(device, *PROFILE_BUTTON, "Profile")
    tap(device, *CLANS_BUTTON, "Clans")

    while True:
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


if __name__ == "__main__":
    main()
