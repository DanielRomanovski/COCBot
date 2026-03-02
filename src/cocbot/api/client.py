"""
Official Supercell API Client
==============================
Wraps coc.py to provide async access to player, clan, and war data.

coc.py docs: https://cocpy.readthedocs.io/en/latest/
API docs:    https://developer.clashofclans.com

NOTE: The official API is READ-ONLY. It cannot perform in-game actions.
Use it for: reading war state, tracking donations, monitoring clan,
            checking if your troops are ready, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import coc
from loguru import logger


@dataclass
class PlayerSnapshot:
    tag: str
    name: str
    town_hall_level: int
    trophies: int
    war_stars: int
    attack_wins: int
    defense_wins: int
    donations: int
    donations_received: int
    troops: list[dict[str, Any]]
    heroes: list[dict[str, Any]]


@dataclass
class ClanWarSnapshot:
    state: str  # "preparation", "inWar", "warEnded", "notInWar"
    team_size: int
    start_time: str | None
    end_time: str | None
    our_attacks: int
    our_stars: int
    enemy_stars: int


class CoCAPIClient:
    """
    Async client for the Supercell Clash of Clans API.

    Uses a raw API token from https://developer.clashofclans.com.
    Tokens are IP-locked — register the IP of the machine running this bot.

    Usage
    -----
    async with CoCAPIClient(token, player_tag) as client:
        player = await client.get_player()
        war = await client.get_current_war(clan_tag)
    """

    def __init__(
        self,
        token: str,
        player_tag: str,
        clan_tag: str | None = None,
    ) -> None:
        self._token = token
        self.player_tag = player_tag
        self.clan_tag = clan_tag
        self._client: coc.Client | None = None

    async def __aenter__(self) -> "CoCAPIClient":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def start(self) -> None:
        """Initialise the coc.py client using a static API token."""
        # raw_attribute=True keeps the original API dict as _raw_data on every
        # coc.py model object — needed to read fields that coc.py doesn't map
        # (e.g. lastOnline on ClanMember).
        self._client = coc.Client(raw_attribute=True)
        await self._client.login_with_tokens(self._token)
        logger.info("CoC API client started")

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            logger.info("CoC API client closed")

    @property
    def client(self) -> coc.Client:
        if not self._client:
            raise RuntimeError("Client not started — use 'async with' or call start()")
        return self._client

    # ── Player ────────────────────────────────────────────────────────────────

    async def get_player(self, tag: str | None = None) -> coc.Player:
        """Fetch live player data from the API."""
        tag = tag or self.player_tag
        player = await self.client.get_player(tag)
        logger.info(
            "Player: {} (TH{}) | Trophies: {} | Donations: {}",
            player.name,
            player.town_hall,
            player.trophies,
            player.donations,
        )
        return player

    async def get_player_snapshot(self, tag: str | None = None) -> PlayerSnapshot:
        """Return a simple serialisable snapshot of key player stats."""
        p = await self.get_player(tag)
        return PlayerSnapshot(
            tag=p.tag,
            name=p.name,
            town_hall_level=p.town_hall,
            trophies=p.trophies,
            war_stars=p.war_stars,
            attack_wins=p.attack_wins,
            defense_wins=p.defense_wins,
            donations=p.donations,
            donations_received=p.received,
            troops=[{"name": t.name, "level": t.level, "max_level": t.max_level} for t in p.troops],
            heroes=[{"name": h.name, "level": h.level, "max_level": h.max_level} for h in p.heroes],
        )

    # ── Clan ──────────────────────────────────────────────────────────────────

    async def get_clan(self, tag: str | None = None) -> coc.Clan:
        """Fetch live clan data."""
        tag = tag or self.clan_tag
        if not tag:
            raise ValueError("No clan_tag configured")
        clan = await self.client.get_clan(tag)
        logger.info("Clan: {} | Members: {}/50 | Level: {}", clan.name, clan.member_count, clan.level)
        return clan

    async def get_clan_members(self, tag: str | None = None) -> list[coc.ClanMember]:
        """Return the full member list of the clan."""
        clan = await self.get_clan(tag)
        return list(clan.members)

    # ── War ───────────────────────────────────────────────────────────────────

    async def get_current_war(self, tag: str | None = None) -> coc.ClanWar | None:
        """
        Fetch the current clan war.
        Returns None if not in war or war log is private.
        """
        tag = tag or self.clan_tag
        if not tag:
            raise ValueError("No clan_tag configured")
        try:
            war = await self.client.get_current_war(tag)
            if war.state == "notInWar":
                logger.info("Clan is not currently in a war")
                return None
            logger.info(
                "War state: {} | Size: {}v{} | Our stars: {} | Enemy stars: {}",
                war.state,
                war.team_size,
                war.team_size,
                war.clan.stars,
                war.opponent.stars,
            )
            return war
        except coc.PrivateWarLog:
            logger.warning("War log is private — cannot read war state")
            return None
        except coc.NotFound:
            logger.warning("Clan not found: {}", tag)
            return None

    async def get_war_snapshot(self, tag: str | None = None) -> ClanWarSnapshot | None:
        war = await self.get_current_war(tag)
        if not war:
            return None
        return ClanWarSnapshot(
            state=war.state,
            team_size=war.team_size,
            start_time=str(war.start_time) if war.start_time else None,
            end_time=str(war.end_time) if war.end_time else None,
            our_attacks=war.clan.attacks_used,
            our_stars=war.clan.stars,
            enemy_stars=war.opponent.stars,
        )

    # ── Raid Weekend ──────────────────────────────────────────────────────────

    async def get_raid_log(self, tag: str | None = None, limit: int = 1) -> list[Any]:
        """Fetch the Capital raid log."""
        tag = tag or self.clan_tag
        if not tag:
            raise ValueError("No clan_tag configured")
        raids = []
        async for raid in self.client.get_raid_log(tag, limit=limit):
            raids.append(raid)
        return raids

    # ── Events (webhooks-style polling) ──────────────────────────────────────

    def register_member_join_callback(self, callback) -> None:
        """
        Register a callback that fires when a member joins the clan.

        Callback signature: async def on_join(player: coc.ClanMember) -> None
        """
        self.client.add_events(callback, event=coc.ClientEvents.clan_member_join())

    def register_war_state_callback(self, callback) -> None:
        """
        Register a callback that fires when the war state changes.

        Callback signature: async def on_war_state(war: coc.ClanWar) -> None
        """
        self.client.add_events(callback, event=coc.ClientEvents.war_attack())

    async def start_event_loop(self, clan_tags: list[str] | None = None) -> None:
        """
        Start coc.py's background event polling loop.
        Must be called after start().
        """
        tags = clan_tags or ([self.clan_tag] if self.clan_tag else [])
        if tags:
            self.client.add_clan_updates(*tags)
        await self.client.start()
