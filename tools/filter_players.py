"""
Tool: filter_players.py
=======================
Called after tapping into a clan from the notice board.
Filters/processes the players in the open clan view.

Currently: just presses ESC (Back) to close the clan and return to the board.
Future:    OCR player tags, apply filters, send invites.

This script is NOT meant to be run directly — it is imported and called
by notice_board.py after each clan tap.
"""

from __future__ import annotations

import time

from loguru import logger

from cocbot.adb.device import ADBDevice


def filter_players(device: ADBDevice) -> None:
    """
    Process the currently open clan view.

    Parameters
    ----------
    device : ADBDevice
        Connected ADB device to send input to.
    """
    logger.info("filter_players: pressing Back to close clan view")
    device.press_back()
    # Small wait so the UI finishes animating back to the notice board
    time.sleep(0.8)
