"""
Pydantic-Settings configuration — loads from .env / environment variables.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Official API ────────────────────────────────────────────────────────────
    # Static API token from https://developer.clashofclans.com
    # Tokens are IP-locked — create a new one if your server IP changes.
    coc_api_token: str = Field(..., description="Supercell developer API token")
    player_tag: str = Field(..., description="Player tag of the account to control")
    clan_tag: str | None = Field(None, description="Clan tag to monitor (optional)")

    # ── ADB / Emulator ────────────────────────────────────────────────────────
    adb_host: str = Field("localhost", description="Host where ADB port is exposed")
    adb_port: int = Field(5555, description="ADB TCP port")
    adb_device_serial: str | None = Field(None, description="Override device serial")
    emulator_width: int = Field(1080, description="Screen width in pixels")
    emulator_height: int = Field(1920, description="Screen height in pixels")

    # ── Bot Behaviour ─────────────────────────────────────────────────────────
    bot_tasks: str = Field(default="recruit", description="Comma-separated tasks: recruit, war")

    # ── Anti-ban ──────────────────────────────────────────────────────────────
    min_action_delay: float = Field(0.3)
    max_action_delay: float = Field(1.2)
    break_every_n_cycles: int = Field(10, description="0 = disabled")
    break_duration_min: int = Field(300)
    break_duration_max: int = Field(900)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field("INFO")
    log_file: str = Field("logs/cocbot.log")

    # ── Optional AI ───────────────────────────────────────────────────────────
    gemini_api_key: str | None = Field(None)

    # ── Recruit / Invite ──────────────────────────────────────────────────────
    recruit_min_th: int = Field(10, description="Min Town Hall shown in recruit filter")
    recruit_max_th: int = Field(17, description="Max Town Hall shown in recruit filter")
    recruit_min_donations: int = Field(500, description="Min seasonal donations")
    recruit_min_trophies: int = Field(1500, description="Min current trophies")
    recruit_min_war_stars: int = Field(100, description="Min all-time war stars")
    recruit_min_attack_wins: int = Field(500, description="Min attack wins (activity proxy)")
    recruit_required_league: str | None = Field(None, description="Required league name, e.g. 'Gold League I'")
    recruit_max_invites_per_run: int = Field(20, description="Max invites to send per run")
    recruit_cycle_interval: int = Field(3600, description="Seconds between recruit runs")

    @field_validator("player_tag", mode="before")
    @classmethod
    def normalise_tag(cls, v: str) -> str:
        """Ensure tags always start with #."""
        v = v.strip()
        return v if v.startswith("#") else f"#{v}"

    @field_validator("clan_tag", mode="before")
    @classmethod
    def normalise_clan_tag(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip()
        return v if v.startswith("#") else f"#{v}"

    @field_validator("bot_tasks", mode="before")
    @classmethod
    def parse_tasks(cls, v: str | list) -> str:
        if isinstance(v, list):
            return ",".join(v)
        return v

    def get_tasks(self) -> list[str]:
        """Return bot_tasks as a parsed list."""
        return [t.strip() for t in self.bot_tasks.split(",") if t.strip()]


# Module-level singleton — import this everywhere
settings = Settings()
