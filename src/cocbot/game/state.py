"""
Game State Machine
==================
Detects which screen CoC is currently on by matching known template images.

States
------
LOADING         — Game is loading / splash screen
VILLAGE         — Main village screen (home base)
ATTACK_MENU     — Attack menu is open (before pressing 'Find a Match')
SEARCHING       — Searching for opponent (spinner)
LOOT_PREVIEW    — Opponent found, showing their base + loot
IN_BATTLE       — Battle is active (troops deployed)
BATTLE_RESULT   — Battle ended, showing stars / loot gained
SETTINGS        — Settings screen
UNKNOWN         — Could not determine the current screen

Templates needed (add to assets/templates/)
-------------------------------------------
state_village.png       — A distinctive element of the village HUD (e.g. shield icon)
state_attack_menu.png   — Attack button / panel
state_searching.png     — The spinning search animation
state_loot_preview.png  — The 'Next' button on the opponent preview
state_in_battle.png     — End battle button visible during a fight
state_battle_result.png — The trophy / loot result screen
"""

from __future__ import annotations

from enum import Enum

import numpy as np
from loguru import logger

from cocbot.vision.matcher import TemplateMatcher


class GameState(Enum):
    LOADING = "loading"
    VILLAGE = "village"
    ATTACK_MENU = "attack_menu"
    SEARCHING = "searching"
    LOOT_PREVIEW = "loot_preview"
    IN_BATTLE = "in_battle"
    BATTLE_RESULT = "battle_result"
    RECRUIT_BOARD = "recruit_board"   # Player recruitment / notice board
    RECRUIT_PROFILE = "recruit_profile"  # Individual player profile card
    SETTINGS = "settings"
    UNKNOWN = "unknown"


# Maps each state to the template file that identifies it
STATE_TEMPLATES: dict[GameState, str] = {
    GameState.VILLAGE: "state_village",
    GameState.ATTACK_MENU: "state_attack_menu",
    GameState.SEARCHING: "state_searching",
    GameState.LOOT_PREVIEW: "state_loot_preview",
    GameState.IN_BATTLE: "state_in_battle",
    GameState.BATTLE_RESULT: "state_battle_result",
    GameState.RECRUIT_BOARD: "state_recruit_board",
    GameState.RECRUIT_PROFILE: "state_recruit_profile",
}


class GameStateDetector:
    """
    Detects the current CoC game state from a screenshot.

    Usage
    -----
    detector = GameStateDetector(matcher)
    state = detector.detect(screenshot)
    """

    def __init__(
        self,
        matcher: TemplateMatcher,
        confidence_threshold: float = 0.75,
    ) -> None:
        self.matcher = matcher
        self.threshold = confidence_threshold
        self._last_state = GameState.UNKNOWN

    def detect(self, screenshot: np.ndarray) -> GameState:
        """
        Identify the current screen by checking templates in priority order.

        Returns
        -------
        GameState
        """
        # Check states in priority order (most likely first for speed)
        priority_order = [
            GameState.VILLAGE,
            GameState.LOOT_PREVIEW,
            GameState.IN_BATTLE,
            GameState.BATTLE_RESULT,
            GameState.ATTACK_MENU,
            GameState.SEARCHING,
            GameState.RECRUIT_PROFILE,
            GameState.RECRUIT_BOARD,
        ]

        for state in priority_order:
            template_name = STATE_TEMPLATES[state]
            try:
                result = self.matcher.find(screenshot, template_name, threshold=self.threshold)
                if result.found:
                    if state != self._last_state:
                        logger.info(
                            "Game state: {} → {} (conf={:.2f})",
                            self._last_state.value,
                            state.value,
                            result.confidence,
                        )
                        self._last_state = state
                    return state
            except FileNotFoundError:
                # Template not yet added — skip this state check
                logger.trace("Template missing for state: {}", state.value)
                continue

        if self._last_state != GameState.UNKNOWN:
            logger.debug("Game state: UNKNOWN (no template matched)")
            self._last_state = GameState.UNKNOWN

        return GameState.UNKNOWN

    @property
    def last_state(self) -> GameState:
        return self._last_state
