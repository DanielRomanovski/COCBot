"""
War Task
========
Uses the official API (read-only) to monitor clan war state and
report war information. Cannot automate war attacks (that requires
the screen automation stack).

Provides:
- War state polling
- Identifying remaining attacks
- Identifying recommended targets (lowest TH not yet attacked)
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from cocbot.api.client import CoCAPIClient


@dataclass
class WarTarget:
    position: int         # Position in the war map (1 = top)
    name: str
    town_hall: int
    attacks_used: int
    max_attacks: int
    stars_received: int   # Stars against this base already


class WarTask:
    """
    Reads war data via the official API and produces targeting recommendations.

    Usage
    -----
    task = WarTask(api_client)
    summary = await task.get_war_summary()
    targets = await task.get_recommended_targets()
    """

    def __init__(self, api_client: CoCAPIClient) -> None:
        self.api = api_client

    async def get_war_summary(self) -> dict:
        """Return a human-readable war summary."""
        war = await self.api.get_current_war()
        if not war:
            return {"status": "not_in_war"}

        our_attacks_remaining = sum(
            m.attacks_limit - len(m.attacks) for m in war.clan.members
        )

        return {
            "state": war.state,
            "team_size": war.team_size,
            "our_stars": war.clan.stars,
            "enemy_stars": war.opponent.stars,
            "our_attacks_used": war.clan.attacks_used,
            "our_attacks_remaining": our_attacks_remaining,
            "enemy_name": war.opponent.name,
        }

    async def get_recommended_targets(self) -> list[WarTarget]:
        """
        Return enemy bases not yet 3-starred, sorted by lowest TH first
        (easiest targets).
        """
        war = await self.api.get_current_war()
        if not war or war.state not in ("inWar",):
            return []

        targets: list[WarTarget] = []
        for member in war.opponent.members:
            best_stars = max(
                (atk.stars for atk in member.defenses), default=0
            )
            if best_stars < 3:
                targets.append(
                    WarTarget(
                        position=member.map_position,
                        name=member.name,
                        town_hall=member.town_hall,
                        attacks_used=len(member.defenses),
                        max_attacks=2,
                        stars_received=best_stars,
                    )
                )

        # Sort: fewest stars first, then lowest TH
        targets.sort(key=lambda t: (t.stars_received, t.town_hall))
        logger.info("Recommended targets: {} bases", len(targets))
        return targets
