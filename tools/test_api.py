"""
Quick test script — runs without an emulator.
Tests the official Supercell API connection only.

Usage:
    poetry run python tools/test_api.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from cocbot.api.client import CoCAPIClient
from cocbot.config import settings


async def main():
    print(f"\n{'='*50}")
    print("COCBot — API Connection Test")
    print(f"{'='*50}\n")

    print(f"Player tag:  {settings.player_tag}")
    print(f"Clan tag:    {settings.clan_tag or '(not set)'}")
    print(f"API token:   {settings.coc_api_token[:12]}...\n")

    async with CoCAPIClient(
        token=settings.coc_api_token,
        player_tag=settings.player_tag,
        clan_tag=settings.clan_tag,
    ) as client:

        # ── Test 1: Fetch your own player profile ─────────────────────────────
        print("[ TEST 1 ] Fetching player profile...")
        try:
            player = await client.get_player()
            print(f"  ✓ Name:          {player.name}")
            print(f"  ✓ Town Hall:     {player.town_hall}")
            print(f"  ✓ Trophies:      {player.trophies}")
            print(f"  ✓ Donations:     {player.donations}")
            print(f"  ✓ War Stars:     {player.war_stars}")
            print(f"  ✓ Attack Wins:   {player.attack_wins}")
            league = player.league.name if player.league else "Unranked"
            print(f"  ✓ League:        {league}")
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            print("    → Check your COC_API_TOKEN and PLAYER_TAG in .env\n")
            return

        # ── Test 2: Fetch clan (if configured) ────────────────────────────────
        if settings.clan_tag:
            print(f"\n[ TEST 2 ] Fetching clan {settings.clan_tag}...")
            try:
                clan = await client.get_clan()
                print(f"  ✓ Clan name:     {clan.name}")
                print(f"  ✓ Members:       {clan.member_count}/50")
                print(f"  ✓ Clan level:    {clan.level}")
                print(f"  ✓ War wins:      {clan.war_wins}")
            except Exception as e:
                print(f"  ✗ FAILED: {e}")
        else:
            print("\n[ TEST 2 ] Skipped — CLAN_TAG not set in .env")

        # ── Test 3: Simulate recruit filter against your own account ──────────
        print("\n[ TEST 3 ] Simulating recruit filter against your own profile...")
        from cocbot.tasks.recruit import RecruitFilters
        filters = RecruitFilters(
            min_th_level=settings.recruit_min_th,
            max_th_level=settings.recruit_max_th,
            min_donations_per_season=settings.recruit_min_donations,
            min_trophies=settings.recruit_min_trophies,
            min_war_stars=settings.recruit_min_war_stars,
            min_attack_wins=settings.recruit_min_attack_wins,
            required_league=settings.recruit_required_league,
        )
        passed, reason = filters.check(player)
        if passed:
            print(f"  ✓ Your account PASSES the current recruit filters")
        else:
            print(f"  ~ Your account would be rejected: {reason}")
            print(f"    (This is normal — adjust filter thresholds in .env to tune)")

    print(f"\n{'='*50}")
    print("API test complete.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
