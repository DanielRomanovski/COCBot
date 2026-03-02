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


def _queued_players() -> int:
    """Return number of player tags currently waiting in found_players.txt."""
    if not PLAYERS_FILE.exists():
        return 0
    return sum(1 for line in PLAYERS_FILE.read_text().splitlines() if line.strip())


PROFILE_BUTTON = (76, 62)
CLANS_BUTTON = (1136, 90)

CLAN_CHORDS = [
  (554, 310),  # Clan 1
  (1322, 306), # Clan 2
  (584, 572),  # Clan 3
  (1328, 560), # Clan 4
  (578, 906),  # Clan 5
  (1318, 888), # Clan 6
]

CLAN7_10_CHORDS = [
  (606, 356),  # Clan 7
  (1316, 342), # Clan 8
  (594, 686),  # Clan 9
  (1336, 670), # Clan 10
]

REFRESH_BUTTON = (980, 940)

# Scroll: swipe upward (finger moves up) to reveal clans further down the list.
SCROLL_X        = 960    # horizontal centre
SCROLL_FROM_Y   = 1600   # swipe start (bottom)
SCROLL_TO_Y     = 400    # swipe end (top)
SCROLL_DURATION = 500    # ms

DELAY_AFTER_TAP    = 1.5  # seconds to wait after tapping a clan card
DELAY_AFTER_SCROLL = 0.5  # pause between consecutive scrolls


def drag_menu_down(device: ADBDevice):
    device.swipe(960, 1016, 962, 724, 600)
    time.sleep(1)


def drag_to_top(device: ADBDevice):
    device.swipe(960, 1016, 960, 0, 800)
    time.sleep(1)


def fast_scroll_to_bottom(device: ADBDevice):
    center_x = settings.emulator_width // 2
    for _ in range(10):
        device.swipe(center_x, SCROLL_FROM_Y, center_x, SCROLL_TO_Y, 200)
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

    CLAN_STEPS = [
      (554, 310,  "Clan 1"),
      (1322, 306, "Clan 2"),
      (584, 572,  "Clan 3"),
      (1328, 560, "Clan 4"),
      (578, 906,  "Clan 5"),
      (1318, 888, "Clan 6"),
    ]

    CLAN7_10_STEPS = [
      (606, 356,  "Clan 7"),
      (1316, 342, "Clan 8"),
      (594, 686,  "Clan 9"),
      (1336, 670, "Clan 10"),
    ]

    VIEW_CLAN   = (800, 868)
    BACK_ARROW  = (268, 78)

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
