"""
Tool: notice_board.py
=====================
Navigates to the Clan Notice Board, scrolls through it, and taps each clan.
After tapping a clan, it hands off to filter_players() to process it.

Path to Notice Board
--------------------
  1. Tap the clan button  → device=(106, 78)
  2. Tap the notice board → device=(1508, 120)

Clan card layout (device coordinates)
--------------------------------------
  SCROLL ONCE, then tap 6 clans:
    (752,  390)  (1772,  390)
    (774,  744)  (1738,  728)
    (770, 1200)  (1788, 1220)

  SCROLL THREE MORE TIMES (0.5s apart), then tap 4 clans:
    (748,  452)  (1742,  466)
    (774,  880)  (1774,  904)

Run
---
  poetry run python tools/notice_board.py
"""

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

# Placeholder for find_players
def find_players(device):
  pass



# ── Chord definitions (device coordinates) ───────────────────────────────────
PROFILE_BUTTON = (76, 62)
CLANS_BUTTON = (1136, 90)
SCROLL_X = 540  # middle of 1080-wide screen
SCROLL_FROM_Y = 1600
SCROLL_TO_Y = 400
SCROLL_DURATION = 500

CLAN_CHORDS = [
  (554, 310),  # Clan 1
  (800, 868),  # View Clan
  (268, 78),   # Go Back to Clan Search
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

# ── Scroll settings ───────────────────────────────────────────────────────────
# A swipe upward (finger moves up) scrolls the list down to reveal more clans.
# The swipe goes from the bottom-centre to the top-centre of the screen.
SCROLL_X          = 960    # horizontal centre (for 1920-wide screen)
SCROLL_FROM_Y     = 1600   # start of swipe (bottom area)
SCROLL_TO_Y       = 400    # end of swipe (top area)
SCROLL_DURATION   = 500    # ms

# Delay between actions (seconds)
DELAY_AFTER_TAP   = 1.5    # time to let a clan profile open
DELAY_AFTER_SCROLL = 0.5   # pause between scrolls




def drag_menu_down(device: ADBDevice):
  # Hold at (960, 1016), drag to (962, 724)
  device.swipe(960, 1016, 962, 724, 600)
  time.sleep(1)

def drag_to_top(device: ADBDevice):
  # Drag from (960, 1016) to (960, 0) to reach the top
  device.swipe(960, 1016, 960, 0, 800)
  time.sleep(1)

def fast_scroll_to_bottom(device: ADBDevice):
    # 10 fast swipes to go to the bottom
    center_x = settings.emulator_width // 2
    for _ in range(10):
        device.swipe(center_x, SCROLL_FROM_Y, center_x, SCROLL_TO_Y, 200)
        time.sleep(0.2)



def tap(device: ADBDevice, x: int, y: int, label: str):
  logger.info(f"Tapping {label} at ({x}, {y})")
  device.tap(x, y)
  time.sleep(1)


def main() -> None:
    cfg = DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    )
    device = ADBDevice(cfg)


    logger.info("Connecting to ADB at {}:{}", settings.adb_host, settings.adb_port)
    device.connect()

    while True:
      # Step 1: Press Profile
      tap(device, *PROFILE_BUTTON, "Profile")

      # Step 2: Press Clans
      tap(device, *CLANS_BUTTON, "Clans")

      # Step 3: Drag menu down
      drag_menu_down(device)

      # Steps 4-9: Tap clans 1-6 (with view, find_players, back)
      clan_steps = [
        (554, 310, "Clan 1"),
        (800, 868, "View Clan"),
        (268, 78, "Go Back to Clan Search"),
        (1322, 306, "Clan 2"),
        (584, 572, "Clan 3"),
        (1328, 560, "Clan 4"),
        (578, 906, "Clan 5"),
        (1318, 888, "Clan 6"),
      ]
      for i in range(6):
        tap(device, clan_steps[i*1][0], clan_steps[i*1][1], clan_steps[i*1][2])
        tap(device, 800, 868, "View Clan")
        find_players(device)
        tap(device, 268, 78, "Go Back to Clan Search")

      # Step 10: Drag to top after 6 clans
      drag_to_top(device)

      # Steps 11-14: Tap clans 7-10 (with view, find_players, back)
      clan7_10 = [
        (606, 356, "Clan 7"),
        (1316, 342, "Clan 8"),
        (594, 686, "Clan 9"),
        (1336, 670, "Clan 10"),
      ]
      for x, y, label in clan7_10:
        tap(device, x, y, label)
        tap(device, 800, 868, "View Clan")
        find_players(device)
        tap(device, 268, 78, "Go Back to Clan Search")

      # Step 15: Tap Refresh button
      tap(device, *REFRESH_BUTTON, "Refresh")

      logger.info("Cycle complete. Restarting...")


if __name__ == "__main__":
    main()
