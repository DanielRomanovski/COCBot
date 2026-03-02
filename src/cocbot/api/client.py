# Async wrapper around coc.py for reading CoC player and clan data.
# The official API is read-only — all in-game actions go through ADB.
#
# Token setup: https://developer.clashofclans.com
# Tokens are IP-locked — register the public IP of the machine running the bot.

from __future__ import annotations

import coc
from loguru import logger


class CoCAPIClient:
    """
    Async context manager for the Supercell CoC API.

    async with CoCAPIClient(token, player_tag, clan_tag) as client:
        members = await client.get_clan_members("#CLANTAG")
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
        """Initialise the coc.py client. raw_attribute=True preserves _raw_data on models."""
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


    async def get_player(self, tag: str) -> coc.Player:
        return await self.client.get_player(tag)

    async def get_clan(self, tag: str) -> coc.Clan:
        clan = await self.client.get_clan(tag)
        logger.info("Clan: {} | Members: {}/50", clan.name, clan.member_count)
        return clan

    async def get_clan_members(self, tag: str) -> list[coc.ClanMember]:
        clan = await self.get_clan(tag)
        return list(clan.members)

    async def get_current_war(self, tag: str) -> coc.ClanWar | None:
        """Return the current war, or None if not in war or the war log is private."""
        try:
            war = await self.client.get_current_war(tag)
            if war.state == "notInWar":
                return None
            return war
        except coc.PrivateWarLog:
            logger.warning("War log is private for {}", tag)
            return None
        except coc.NotFound:
            logger.warning("Clan not found: {}", tag)
            return None
