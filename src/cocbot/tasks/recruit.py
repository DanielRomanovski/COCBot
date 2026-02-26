"""
Recruit Task
============
Automates the CoC in-game recruitment board ("Recruit" tab).

Flow
----
1. Navigate to the Recruit board
2. (Optionally) open filters and set min TH level
3. Scan visible player cards via OCR to extract player tags
4. For each tag, call the official API to check:
     - Monthly donations
     - Town Hall level
     - Trophy count
     - War stars
     - Last active (attack wins as a proxy)
5. If the player passes ALL configured filters → send an Invite
6. Scroll down to reveal more cards, repeat until daily invite limit hit
   or max_invites_per_run reached

Template images needed (add to assets/templates/)
--------------------------------------------------
  state_recruit_board.png     — Distinctive element of the recruit board HUD
  state_recruit_profile.png   — Player profile page (when tapped open)
  recruit_invite_sent.png     — The green "Invite sent" confirmation toast (optional)
  recruit_player_tag_area.png — (optional) The tag region on a card for cropping

ROI note
--------
The player tag on each card is typically rendered as small white text.
The default ROI assumes 1080×1920 and the first visible card at ~y=450.
Each subsequent card is ~200px lower. Adjust CARD_HEIGHT and TAG_ROI_OFFSET
to match your emulator.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

import coc
from loguru import logger

from cocbot.adb.input import InputController
from cocbot.api.client import CoCAPIClient
from cocbot.game.navigator import Coords, Navigator
from cocbot.game.state import GameState, GameStateDetector
from cocbot.utils.delays import human_delay, long_pause
from cocbot.vision.matcher import TemplateMatcher
from cocbot.vision.ocr import OCRReader


# ── Layout constants for 1080×1920 ────────────────────────────────────────────
# y-coordinate of the CENTRE of the first player card on the board
FIRST_CARD_Y = 450
# Vertical distance between card centres
CARD_HEIGHT = 210
# How many cards are visible at once (before scrolling)
CARDS_PER_PAGE = 4
# (x, y, w, h) of the player tag text on a card, relative to card centre y
# The tag "#XXXXXXXX" is typically bottom-left of the card
TAG_ROI = lambda card_y: (60, card_y + 55, 250, 35)  # noqa: E731


@dataclass
class RecruitFilters:
    """All configurable filters for deciding whether to invite a player."""

    # ── Screen filters (applied via the in-game filter UI) ────────────────────
    min_th_level: int = 10          # Minimum Town Hall level to show in board
    max_th_level: int = 17          # Maximum Town Hall level

    # ── API filters (checked after reading the player tag) ────────────────────
    min_donations_per_season: int = 500    # Minimum donations this season
    min_trophies: int = 1500               # Minimum current trophies
    min_war_stars: int = 100               # Minimum all-time war stars
    min_attack_wins: int = 500             # Attack wins (proxy for activity)
    required_league: str | None = None     # e.g. "Gold League I" — None = any
    excluded_tags: set[str] = field(default_factory=set)  # Never invite these

    def check(self, player: "coc.Player") -> tuple[bool, str]:
        """
        Run all API-based filters against a fetched player object.

        Returns
        -------
        (passed: bool, reason: str)
            passed=True if the player should be invited.
            reason explains why they were rejected (empty string if passed).
        """
        if player.tag in self.excluded_tags:
            return False, "tag in excluded list"

        if player.town_hall < self.min_th_level:
            return False, f"TH{player.town_hall} < min TH{self.min_th_level}"

        if player.town_hall > self.max_th_level:
            return False, f"TH{player.town_hall} > max TH{self.max_th_level}"

        if player.donations < self.min_donations_per_season:
            return False, f"donations {player.donations} < {self.min_donations_per_season}"

        if player.trophies < self.min_trophies:
            return False, f"trophies {player.trophies} < {self.min_trophies}"

        if player.war_stars < self.min_war_stars:
            return False, f"war stars {player.war_stars} < {self.min_war_stars}"

        if player.attack_wins < self.min_attack_wins:
            return False, f"attack wins {player.attack_wins} < {self.min_attack_wins}"

        if self.required_league and player.league:
            if player.league.name != self.required_league:
                return False, f"league '{player.league.name}' != '{self.required_league}'"

        return True, ""


@dataclass
class RecruitStats:
    players_scanned: int = 0
    invites_sent: int = 0
    rejected_no_tag: int = 0
    rejected_by_filter: int = 0
    api_errors: int = 0


class RecruitTask:
    """
    Runs the recruitment loop.

    Usage
    -----
    task = RecruitTask(input_ctrl, navigator, state_detector, ocr, api, filters)
    await task.run(max_invites=20)
    """

    def __init__(
        self,
        input_ctrl: InputController,
        navigator: Navigator,
        state_detector: GameStateDetector,
        ocr: OCRReader,
        api_client: CoCAPIClient,
        filters: RecruitFilters | None = None,
        max_invites_per_run: int = 20,
    ) -> None:
        self.input = input_ctrl
        self.nav = navigator
        self.detector = state_detector
        self.ocr = ocr
        self.api = api_client
        self.filters = filters or RecruitFilters()
        self.max_invites = max_invites_per_run
        self.stats = RecruitStats()
        # Track tags we've already processed this run to avoid duplicates
        self._seen_tags: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self, max_invites: int | None = None) -> RecruitStats:
        """
        Run the full recruitment loop until max_invites is reached or
        no new cards are found after several scrolls.
        """
        limit = max_invites or self.max_invites
        logger.info("=== Recruit run starting (max_invites={}) ===", limit)

        # 1. Open the recruit board
        if not await self.nav.open_recruit_board():
            logger.error("Could not open recruit board")
            return self.stats

        # 2. Apply in-game filters (TH range)
        await self._apply_ingame_filters()

        # 3. Main scroll-and-invite loop
        no_new_cards_streak = 0
        while self.stats.invites_sent < limit:
            new_tags = await self._scan_visible_cards()

            if not new_tags:
                no_new_cards_streak += 1
                logger.debug("No new tags found (streak={})", no_new_cards_streak)
                if no_new_cards_streak >= 3:
                    logger.info("No new cards after 3 scrolls — stopping")
                    break
            else:
                no_new_cards_streak = 0
                for tag in new_tags:
                    if self.stats.invites_sent >= limit:
                        break
                    await self._process_player(tag)
                    await human_delay(0.5, 1.0)

            # Scroll down to reveal more cards
            await self.nav.scroll_recruit_board(direction="up", amount=350)
            await long_pause(0.8, 1.5)

        logger.success(
            "Recruit run complete — scanned={} invited={} rejected={}",
            self.stats.players_scanned,
            self.stats.invites_sent,
            self.stats.rejected_by_filter,
        )
        return self.stats

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _apply_ingame_filters(self) -> None:
        """
        Open the filter panel and set the TH level range.
        The actual slider interaction depends on your emulator resolution —
        you may need to calibrate Coords.FILTER_MIN_TH.
        """
        logger.info("Applying in-game recruit filters (TH {}-{})",
                    self.filters.min_th_level, self.filters.max_th_level)
        await self.nav.open_recruit_filters()
        # TODO: drag TH slider to min_th_level — requires calibration.
        # For now, just confirm whatever the current filter state is.
        await self.nav.apply_recruit_filters()
        await long_pause(1.0, 2.0)

    async def _scan_visible_cards(self) -> list[str]:
        """
        Take a screenshot and OCR each card position to extract player tags.
        Returns a list of new (not yet seen) player tags found on screen.
        """
        screenshot = await self.input.screenshot()
        new_tags: list[str] = []

        for i in range(CARDS_PER_PAGE):
            card_y = FIRST_CARD_Y + i * CARD_HEIGHT
            tag = self._ocr_tag_from_card(screenshot, card_y)
            if tag and tag not in self._seen_tags:
                self._seen_tags.add(tag)
                new_tags.append(tag)
                logger.debug("Found player tag on card {}: {}", i, tag)

        return new_tags

    def _ocr_tag_from_card(self, screenshot, card_y: int) -> str | None:
        """
        OCR the player tag area of a single card.
        Returns the tag string (e.g. '#ABC123XY') or None if not readable.
        """
        roi = TAG_ROI(card_y)
        raw = self.ocr.read_text(screenshot, roi).strip()
        # Player tags: # followed by 6-9 uppercase letters/digits
        match = re.search(r"#[0-9A-Z]{6,9}", raw.upper())
        if match:
            return match.group()
        self.stats.rejected_no_tag += 1
        return None

    async def _process_player(self, tag: str) -> None:
        """
        Fetch the player from the API, run filters, invite if they pass.
        """
        self.stats.players_scanned += 1
        logger.info("Checking player {} ({}/{})", tag,
                    self.stats.players_scanned, self.max_invites)

        try:
            player = await self.api.get_player(tag)
        except Exception as e:
            logger.warning("API error for {}: {}", tag, e)
            self.stats.api_errors += 1
            return

        passed, reason = self.filters.check(player)

        if not passed:
            logger.info("  ✗ {} rejected: {}", player.name, reason)
            self.stats.rejected_by_filter += 1
            return

        logger.success("  ✓ {} (TH{} | {} trophies | {} donations) — inviting",
                       player.name, player.town_hall,
                       player.trophies, player.donations)
        await self._send_invite(tag, player.name)

    async def _send_invite(self, tag: str, name: str) -> None:
        """
        Find the player's card on screen (by re-scanning), tap it to open
        their profile, then tap Invite.
        """
        # Re-scan to find which card position still shows this tag
        screenshot = await self.input.screenshot()
        card_y = self._find_card_y_for_tag(screenshot, tag)

        if card_y is None:
            # Card scrolled off — open profile directly via search isn't possible
            # in CoC, so we skip and rely on re-encountering them
            logger.warning("Card for {} no longer visible — skipping invite", name)
            return

        # Open the player's profile
        if not await self.nav.open_player_profile(Coords.FIRST_CARD[0], card_y):
            logger.warning("Could not open profile for {}", name)
            return

        # Tap invite
        await self.nav.invite_from_profile()
        self.stats.invites_sent += 1
        logger.success("Invite sent to {} ({})", name, tag)

        # Close profile and return to board
        await self.nav.close_profile()
        await long_pause(0.5, 1.0)

    def _find_card_y_for_tag(self, screenshot, tag: str) -> int | None:
        """Scan all card positions and return the y-coordinate of the matching tag."""
        for i in range(CARDS_PER_PAGE):
            card_y = FIRST_CARD_Y + i * CARD_HEIGHT
            found = self._ocr_tag_from_card(screenshot, card_y)
            if found == tag:
                return card_y
        return None
