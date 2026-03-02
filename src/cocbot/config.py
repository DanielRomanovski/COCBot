# Pydantic-Settings configuration — loads from .env / environment variables.
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

    # CoC API — token from https://developer.clashofclans.com (IP-locked)
    coc_api_token: str = Field(..., description="Supercell developer API token")
    player_tag: str = Field(..., description="Player tag of the account to control")

    # ADB connection to the Android emulator
    adb_host: str = Field("127.0.0.1", description="Host where ADB is exposed")
    adb_port: int = Field(16384, description="ADB TCP port")
    adb_device_serial: str | None = Field(None, description="Override device serial (optional)")
    emulator_width: int = Field(1920, description="Screen width in pixels")
    emulator_height: int = Field(1080, description="Screen height in pixels")

    @field_validator("player_tag", mode="before")
    @classmethod
    def normalise_tag(cls, v: str) -> str:
        v = v.strip()
        return v if v.startswith("#") else f"#{v}"


# Module-level singleton — import this everywhere
settings = Settings()
