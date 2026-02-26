"""
COCBot — Main Entry Point
==========================
Wires together all components and runs the bot.

Usage
-----
  python -m cocbot.main
  # or (if installed via poetry):
  cocbot
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from loguru import logger

# Ensure src/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.adb.input import InputController
from cocbot.api.client import CoCAPIClient
from cocbot.config import settings
from cocbot.game.navigator import Navigator
from cocbot.game.state import GameStateDetector
from cocbot.tasks.recruit import RecruitFilters, RecruitTask
from cocbot.tasks.war import WarTask
from cocbot.utils.delays import break_pause
from cocbot.utils.logging import setup_logger
from cocbot.vision.matcher import TemplateMatcher
from cocbot.vision.ocr import OCRReader


async def run_bot() -> None:
    """Main async bot runner."""

    # ── 1. ADB device connection ──────────────────────────────────────────────
    device_cfg = DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        serial=settings.adb_device_serial or None,
        width=settings.emulator_width,
        height=settings.emulator_height,
    )

    device = ADBDevice(device_cfg)
    device.connect()

    # ── 2. Input controller ───────────────────────────────────────────────────
    input_ctrl = InputController(
        device,
        min_delay=settings.min_action_delay,
        max_delay=settings.max_action_delay,
    )

    # ── 3. Vision stack ───────────────────────────────────────────────────────
    matcher = TemplateMatcher()
    ocr = OCRReader()
    state_detector = GameStateDetector(matcher)

    # ── 4. Navigator ──────────────────────────────────────────────────────────
    navigator = Navigator(input_ctrl, state_detector)

    # ── 5. Official API client ────────────────────────────────────────────────
    api_client = CoCAPIClient(
        token=settings.coc_api_token,
        player_tag=settings.player_tag,
        clan_tag=settings.clan_tag,
    )
    await api_client.start()

    # ── 6. Ensure CoC is running ──────────────────────────────────────────────
    if not device.is_coc_running():
        logger.info("CoC not running — launching...")
        device.launch_coc()
        await asyncio.sleep(10)  # Wait for game to load

    # ── 7. Run requested tasks ────────────────────────────────────────────────
    tasks = settings.get_tasks()
    logger.info("Active tasks: {}", tasks)

    cycle_count = 0

    try:
        while True:
            cycle_count += 1

            # ── War monitoring (API only, no automation) ───────────────────────────────
            if "war" in tasks:
                war_task = WarTask(api_client)
                summary = await war_task.get_war_summary()
                logger.info("War summary: {}", summary)

                if summary.get("state") == "inWar":
                    targets = await war_task.get_recommended_targets()
                    for t in targets[:3]:
                        logger.info(
                            "  Recommended target: #{} {} (TH{}, {}★)",
                            t.position,
                            t.name,
                            t.town_hall,
                            t.stars_received,
                        )

            # ── Recruitment ──────────────────────────────────────────────────────────
            if "recruit" in tasks:
                recruit_filters = RecruitFilters(
                    min_th_level=settings.recruit_min_th,
                    max_th_level=settings.recruit_max_th,
                    min_donations_per_season=settings.recruit_min_donations,
                    min_trophies=settings.recruit_min_trophies,
                    min_war_stars=settings.recruit_min_war_stars,
                    min_attack_wins=settings.recruit_min_attack_wins,
                    required_league=settings.recruit_required_league,
                )
                recruit_task = RecruitTask(
                    input_ctrl, navigator, state_detector, ocr,
                    api_client, recruit_filters,
                    max_invites_per_run=settings.recruit_max_invites_per_run,
                )
                await recruit_task.run()
                logger.info("Waiting {}s before next recruit run",
                            settings.recruit_cycle_interval)
                await asyncio.sleep(settings.recruit_cycle_interval)
                continue  # Skip the standard cycle sleep below

            # ── Anti-ban break ────────────────────────────────────────────────
            n = settings.break_every_n_cycles
            if n > 0 and cycle_count % n == 0:
                logger.info(
                    "Taking a break ({}–{}s)...",
                    settings.break_duration_min,
                    settings.break_duration_max,
                )
                await break_pause(settings.break_duration_min, settings.break_duration_max)
            else:
                logger.info("Waiting {}s before next cycle", settings.recruit_cycle_interval)
                await asyncio.sleep(settings.recruit_cycle_interval)

    except asyncio.CancelledError:
        logger.info("Bot cancelled — shutting down")
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")
    finally:
        await api_client.close()
        device.disconnect()
        logger.info("Bot stopped cleanly")


def main() -> None:
    """CLI entry point."""
    setup_logger(settings.log_level, settings.log_file)
    logger.info("COCBot starting up")
    logger.info("Player: {}", settings.player_tag)
    logger.info("Tasks: {}", settings.bot_tasks)
    logger.info("ADB target: {}:{}", settings.adb_host, settings.adb_port)

    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
