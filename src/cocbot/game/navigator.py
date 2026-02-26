"""
Game Navigator
==============
High-level navigation helpers that combine state detection + input to
move between CoC screens.

Each method:
1. Waits for the expected current state (with timeout)
2. Taps/swipes to reach the next state
3. Waits for the new state to appear
4. Returns the new state (or raises on timeout)
"""

from __future__ import annotations

import asyncio
import time

import numpy as np
from loguru import logger

from cocbot.adb.input import InputController
from cocbot.game.state import GameState, GameStateDetector
from cocbot.utils.delays import human_delay, long_pause


# ── Coordinate constants for 1080×1920 ───────────────────────────────────────
# These are approximate tap positions — tune from real screenshots.

class Coords:
    """Pixel coordinates for key UI buttons at 1080×1920."""

    # Main village HUD
    ATTACK_BUTTON   = (85,  1820)  # Red sword button bottom-left
    FIND_A_MATCH    = (590, 1550)  # "Find a Match" inside attack menu

    # Loot preview screen
    NEXT_BUTTON     = (980, 1845)  # Skip to next base
    ATTACK_NOW      = (590, 1845)  # Confirm attack on this base

    # In-battle
    END_BATTLE_BTN  = (980, 60)    # Red 'End Battle' / surrender button
    CONFIRM_END     = (610, 1080)  # Confirm dialog yes button

    # Battle result
    RETURN_HOME     = (590, 1845)  # Return to village button

    # General
    CLOSE_BTN       = (980, 60)    # Generic X / close button (top right)
    OK_BTN          = (590, 1080)  # Generic OK confirmation

    # ── Recruit / Notice Board ────────────────────────────────────────────────
    # Tap the people/magnifying-glass icon at the bottom of the village screen
    RECRUIT_TAB     = (540, 1820)  # Bottom nav: 'Recruit' tab icon
    # Inside the recruit board
    FILTER_BTN      = (980, 120)   # Funnel/filter icon top-right
    # Filter panel sliders — calibrate these from a real screenshot
    FILTER_MIN_TH   = (750, 600)   # Min Town Hall slider right handle
    FILTER_CONFIRM  = (540, 1750)  # 'Apply' / 'Done' button in filter panel
    # Player card actions (first visible card)
    FIRST_CARD      = (540, 500)   # Centre of the first player card
    CARD_INVITE_BTN = (850, 500)   # 'Invite' button on the first card
    # When a profile is open
    PROFILE_INVITE  = (540, 1700)  # 'Invite to Clan' button on profile
    PROFILE_CLOSE   = (980, 60)    # Close / back on profile


class Navigator:
    """
    Orchestrates movement between game screens.

    Usage
    -----
    nav = Navigator(input_ctrl, state_detector)
    await nav.go_to_village()
    await nav.open_attack_menu()
    await nav.find_match()
    """

    def __init__(
        self,
        input_ctrl: InputController,
        state_detector: GameStateDetector,
        state_timeout: float = 30.0,
        poll_interval: float = 1.5,
    ) -> None:
        self.input = input_ctrl
        self.detector = state_detector
        self.timeout = state_timeout
        self.poll_interval = poll_interval

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _wait_for_state(
        self,
        expected: GameState,
        timeout: float | None = None,
    ) -> bool:
        """
        Poll until the screen shows `expected` state (or timeout).
        Returns True if state reached, False on timeout.
        """
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            screenshot = await self.input.screenshot()
            state = self.detector.detect(screenshot)
            if state == expected:
                return True
            await asyncio.sleep(self.poll_interval)
        logger.warning("Timed out waiting for state: {}", expected.value)
        return False

    async def _current_state(self) -> GameState:
        screenshot = await self.input.screenshot()
        return self.detector.detect(screenshot)

    async def _current_screenshot(self) -> np.ndarray:
        return await self.input.screenshot()

    # ── Navigation methods ────────────────────────────────────────────────────

    async def go_to_village(self) -> bool:
        """
        Ensure we are on the main village screen.
        Presses Back several times if lost, then waits for VILLAGE state.
        """
        state = await self._current_state()
        if state == GameState.VILLAGE:
            return True

        logger.info("Navigating back to village...")
        for _ in range(5):
            await self.input.press_back()
            state = await self._current_state()
            if state == GameState.VILLAGE:
                return True
            await long_pause(1.0, 2.0)

        return await self._wait_for_state(GameState.VILLAGE)

    async def open_attack_menu(self) -> bool:
        """
        From the village screen, tap the Attack button to open the attack menu.
        """
        logger.info("Opening attack menu")
        await self.input.tap(*Coords.ATTACK_BUTTON)
        return await self._wait_for_state(GameState.ATTACK_MENU)

    async def start_search(self) -> bool:
        """
        From the attack menu, tap 'Find a Match' to start searching.
        """
        logger.info("Starting match search")
        await self.input.tap(*Coords.FIND_A_MATCH)
        return await self._wait_for_state(GameState.LOOT_PREVIEW, timeout=60.0)

    async def skip_base(self) -> bool:
        """
        On the loot preview screen, tap 'Next' to skip to the next base.
        """
        await self.input.tap(*Coords.NEXT_BUTTON)
        return await self._wait_for_state(GameState.LOOT_PREVIEW, timeout=15.0)

    async def confirm_attack(self) -> bool:
        """
        On the loot preview screen, tap 'Attack!' to enter the battle.
        """
        logger.info("Confirming attack")
        await self.input.tap(*Coords.ATTACK_NOW)
        return await self._wait_for_state(GameState.IN_BATTLE, timeout=15.0)

    async def end_battle(self) -> bool:
        """
        Tap the End Battle button to surrender / end the battle early.
        Only call this when you've finished deploying all troops.
        """
        logger.info("Ending battle")
        await self.input.tap(*Coords.END_BATTLE_BTN)
        await human_delay(0.5, 1.0)
        await self.input.tap(*Coords.CONFIRM_END)
        return await self._wait_for_state(GameState.BATTLE_RESULT, timeout=30.0)

    async def return_home(self) -> bool:
        """
        From the battle result screen, tap Return Home.
        """
        logger.info("Returning home")
        await self.input.tap(*Coords.RETURN_HOME)
        return await self._wait_for_state(GameState.VILLAGE, timeout=20.0)

    # ── Recruit navigation ────────────────────────────────────────────────────

    async def open_recruit_board(self) -> bool:
        """
        From the village, tap the Recruit tab to open the notice board.
        """
        logger.info("Opening recruit board")
        if not await self.go_to_village():
            return False
        await self.input.tap(*Coords.RECRUIT_TAB)
        return await self._wait_for_state(GameState.RECRUIT_BOARD, timeout=15.0)

    async def open_recruit_filters(self) -> bool:
        """Tap the filter icon on the recruit board."""
        logger.info("Opening recruit filters")
        await self.input.tap(*Coords.FILTER_BTN)
        await long_pause(0.8, 1.5)
        return True

    async def apply_recruit_filters(self) -> bool:
        """Tap the Apply/Done button to confirm filter selections."""
        await self.input.tap(*Coords.FILTER_CONFIRM)
        await long_pause(1.0, 2.0)
        return True

    async def scroll_recruit_board(self, direction: str = "up", amount: int = 350) -> None:
        """
        Scroll the recruit board to reveal more player cards.
        direction: 'up' scrolls the list upward (reveals cards below).
        """
        if direction == "up":
            await self.input.scroll_down(amount)
        else:
            await self.input.scroll_up(amount)

    async def open_player_profile(self, card_x: int, card_y: int) -> bool:
        """Tap a player card to open their full profile."""
        await self.input.tap(card_x, card_y)
        return await self._wait_for_state(GameState.RECRUIT_PROFILE, timeout=8.0)

    async def invite_from_profile(self) -> bool:
        """Tap 'Invite to Clan' on the open profile page."""
        logger.info("Sending invite from profile")
        await self.input.tap(*Coords.PROFILE_INVITE)
        await long_pause(0.5, 1.2)
        return True

    async def close_profile(self) -> bool:
        """Close the player profile and return to the recruit board."""
        await self.input.tap(*Coords.PROFILE_CLOSE)
        return await self._wait_for_state(GameState.RECRUIT_BOARD, timeout=8.0)
