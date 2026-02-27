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
from filter_players import filter_players


# ── Notice board navigation coords ───────────────────────────────────────────
NAV_CLAN_BUTTON    = (106,  78)   # Opens the clan tab
NAV_NOTICE_BOARD   = (1508, 120)  # Opens the notice board inside clan tab

# ── Clan card coordinates (device pixels) ─────────────────────────────────────
# After the FIRST scroll
CLANS_BATCH_1 = [
    (752,  390),
    (1772, 390),
    (774,  744),
    (1738, 728),
    (770,  1200),
    (1788, 1220),
]

# After THREE more scrolls
CLANS_BATCH_2 = [
    (748,  452),
    (1742, 466),
    (774,  880),
    (1774, 904),
]

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


def scroll_once(device: ADBDevice) -> None:
    device.swipe(SCROLL_X, SCROLL_FROM_Y, SCROLL_X, SCROLL_TO_Y, SCROLL_DURATION)
    time.sleep(DELAY_AFTER_SCROLL)


def tap_clan(device: ADBDevice, x: int, y: int, index: int) -> None:
    logger.info("Tapping clan {} at ({}, {})", index + 1, x, y)
    device.tap(x, y)
    time.sleep(DELAY_AFTER_TAP)
    filter_players(device)
    time.sleep(0.5)  # brief pause before next tap


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

    # ── 1. Navigate to notice board ───────────────────────────────────────────
    logger.info("Opening clan tab...")
    device.tap(*NAV_CLAN_BUTTON)
    time.sleep(1.0)

    logger.info("Opening notice board...")
    device.tap(*NAV_NOTICE_BOARD)
    time.sleep(1.5)

    # ── 2. First scroll ───────────────────────────────────────────────────────
    logger.info("Scrolling once to reveal first set of clans...")
    scroll_once(device)

    # ── 3. Tap first 6 clans ─────────────────────────────────────────────────
    logger.info("Processing batch 1 ({} clans)...", len(CLANS_BATCH_1))
    for i, (x, y) in enumerate(CLANS_BATCH_1):
        tap_clan(device, x, y, i)

    # ── 4. Scroll 3 more times ────────────────────────────────────────────────
    logger.info("Scrolling 3 times to reveal next set of clans...")
    for _ in range(3):
        scroll_once(device)

    # ── 5. Tap next 4 clans ───────────────────────────────────────────────────
    logger.info("Processing batch 2 ({} clans)...", len(CLANS_BATCH_2))
    for i, (x, y) in enumerate(CLANS_BATCH_2):
        tap_clan(device, x, y, len(CLANS_BATCH_1) + i)

    logger.success(
        "Done — processed {} clans total.",
        len(CLANS_BATCH_1) + len(CLANS_BATCH_2),
    )


if __name__ == "__main__":
    main()
