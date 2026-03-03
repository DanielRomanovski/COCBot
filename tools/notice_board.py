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
from find_players import find_players, get_queue, clear_queue
from invite_players import invite_players, _go_to_main
import config_manager


PROFILE_BUTTON = (52,  38)
CLANS_BUTTON   = (838,  54)
REFRESH_BUTTON = (738, 630)
VIEW_CLAN      = (628, 570)
BACK_ARROW     = (250,  62)

CLAN_CHORDS = [
    (474, 214),  # Clan 1
    (970, 210),  # Clan 2
    (440, 396),  # Clan 3
    (966, 386),  # Clan 4
    (434, 612),  # Clan 5
    (976, 614),  # Clan 6
]

CLAN7_10_CHORDS = [
    (466, 220),  # Clan 7
    (972, 236),  # Clan 8
    (482, 444),  # Clan 9
    (992, 448),  # Clan 10
]

DELAY_AFTER_TAP = 1.5


def drag_menu_down(device: ADBDevice):
    """Single swipe down to reveal clans 1-6."""
    device.swipe(724, 668, 722, 426, 600)
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

    CLAN_STEPS = [(x, y, f"Clan {i+1}") for i, (x, y) in enumerate(CLAN_CHORDS)]
    CLAN7_10_STEPS = [(x, y, f"Clan {i+7}") for i, (x, y) in enumerate(CLAN7_10_CHORDS)]

    def _queued() -> int:
        return len(get_queue())

    def _do_invite():
        queue_snapshot = list(get_queue())
        clear_queue()
        invite_players(device, standalone=False, tags=queue_snapshot)
        tap(device, *PROFILE_BUTTON, "Profile")
        tap(device, *CLANS_BUTTON, "Clans")

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
      if _queued() >= config_manager.get("invite_every"):
          logger.info("{} players queued — switching to invite mode", _queued())
          _do_invite()
          continue

      # Drag back to the top to reach clans 7-10
      drag_to_top(device)

      # Clans 7-10
      process_clans(CLAN7_10_STEPS)

      # Refresh loads a new set of clans
      tap(device, *REFRESH_BUTTON, "Refresh")
      logger.info("Refresh complete — {} player(s) queued", _queued())

      # Check after second batch / refresh
      if _queued() >= config_manager.get("invite_every"):
          logger.info("{} players queued — switching to invite mode", _queued())
          _do_invite()


if __name__ == "__main__":
    main()
