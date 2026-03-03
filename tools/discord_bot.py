"""
Discord bot for controlling and monitoring CoCBot.

Commands:
  /leaderboard [filter]     – Clan activity table (worst → best)
  /invite start [moderate]  – Start the notice-board / invite loop  [admin]
  /invite stop              – Stop the invite loop  [admin]
  /invite status            – Loop state + current recruit filters
  /config [key] [value]     – View or change a bot setting (set requires admin)
  /screenshot               – Post a screenshot of the emulator  [admin]
  /forcemenu                – ESC ×7 + Cancel to reach the main screen  [admin]
  /help                     – Command reference

Background task:
  Every N hours (activity_check_interval_hours) the activity tracker is
  refreshed silently via the CoC API with no ADB interaction.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from loguru import logger

load_dotenv(ROOT / ".env")

# ── Console sink + stdlib-logging bridge ──────────────────────────────────────
import console_sink
console_sink.setup("discord_bot")

# Forward Python stdlib logging (discord.py, aiohttp, …) into loguru
class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[_InterceptHandler()], level=logging.DEBUG, force=True)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.WARNING)

import config_manager
from config_manager import FIELD_META
from moderation import _fetch_ranked_members, MemberScore  # noqa: E402
from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.config import settings

# ── Env config ────────────────────────────────────────────────────────────────

TOKEN    = os.getenv("DISCORD_BOT_TOKEN", "")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))

CLAN_NAME = "mariners"
CLAN_MAX  = 50

# ── ADB targets (for /adbtarget testing command) ──────────────────────────────
_ADB_TARGETS: dict[str, tuple[str, int]] = {
    "phone":      ("10.0.0.47",  5555),   # physical Android phone over WiFi
    "bluestacks": ("127.0.0.1",  5556),   # Windows BlueStacks (local)
}


_invite_proc: asyncio.subprocess.Process | None = None


async def _start_invite_loop(moderate: bool) -> str:
    global _invite_proc
    if _invite_proc is not None and _invite_proc.returncode is None:
        return f"⚠️ Already running (PID {_invite_proc.pid}). Use `/invite stop` first."
    try:
        await _adb_esc_cancel(3)
    except Exception as exc:
        return f"❌ ADB navigation failed: {exc}"
    config_manager.set_value("moderate_on_invite", "true" if moderate else "false")
    _invite_proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(ROOT / "tools" / "notice_board.py"),
        cwd=str(ROOT),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return f"✅ Invite loop started (PID {_invite_proc.pid})  •  moderate_on_invite={moderate}"


async def _stop_invite_loop() -> str:
    global _invite_proc
    if _invite_proc is None or _invite_proc.returncode is not None:
        _invite_proc = None
        return "⚠️ Invite loop is not running."
    pid = _invite_proc.pid
    _invite_proc.terminate()
    try:
        await asyncio.wait_for(_invite_proc.wait(), timeout=6.0)
    except asyncio.TimeoutError:
        _invite_proc.kill()
    _invite_proc = None
    try:
        await _adb_esc_cancel(3)
    except Exception as exc:
        return f"🛑 Invite loop stopped (PID {pid}) — ADB cleanup failed: {exc}"
    return f"🛑 Invite loop stopped (PID {pid}).  Navigated back to main screen."


def _invite_status() -> str:
    if _invite_proc is None:
        return "🔴 Invite loop: **not running**"
    if _invite_proc.returncode is None:
        moderate = config_manager.get("moderate_on_invite")
        return (
            f"🟢 Invite loop: **running** (PID {_invite_proc.pid})\n"
            f"   moderate_on_invite = `{moderate}`"
        )
    return f"🔴 Invite loop: **exited** (code {_invite_proc.returncode})"


# ── Admin guard ───────────────────────────────────────────────────────────────

def _is_admin(interaction: discord.Interaction) -> bool:
    """Return True when the invoking member has Administrator or Manage Guild."""
    perms = interaction.user.guild_permissions  # type: ignore[union-attr]
    return perms.administrator or perms.manage_guild


_ADMIN_DENIED = "❌ This command requires **Administrator** or **Manage Guild** permission."


# ── ADB helpers (synchronous, run in executor) ────────────────────────────────

def _make_device() -> ADBDevice:
    device = ADBDevice(DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    ))
    device.connect()
    return device


def _adb_esc_cancel_sync(times: int) -> None:
    device = _make_device()
    for _ in range(times):
        device.press_back()
        time.sleep(0.5)
    time.sleep(0.3)
    device.tap(754, 698)
    time.sleep(0.8)


async def _adb_esc_cancel(times: int = 3) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _adb_esc_cancel_sync, times)


def _adb_screenshot_sync() -> bytes:
    device = _make_device()
    img = device.screenshot_pil()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ── Embed helpers ─────────────────────────────────────────────────────────────

def _table_field(members: list[tuple[int, MemberScore]], kick_tags: set[str]) -> str:
    """Monospace code-block table for one embed section. Max 1024 chars."""
    NAME_W = 18
    rows: list[str] = []
    for rank, m in members:
        name    = m.name[:NAME_W].ljust(NAME_W)
        offline = f"{m.days_offline:.1f}d".rjust(6) if m.days_offline is not None else "   ???"
        don     = str(m.donations).rjust(5)
        note    = " <KICK" if m.tag in kick_tags else ""
        rows.append(f"{rank:>2}  {name}  {offline}  {don}{note}")
    header  = f"{'#':>2}  {'Name':<{NAME_W}}  {'Offln':>6}  {'Don':>5}"
    divider = "-" * len(header)
    body    = "\n".join([header, divider] + rows)
    block   = f"```\n{body}\n```"
    if len(block) > 1020:
        block = block[:1017] + "...\n```"
    return block


def _build_embed(ranked: list[MemberScore]) -> discord.Embed:
    """Single flat table, best (most active) → worst, split into 20-row fields."""
    players_to_kick: int = config_manager.get("players_to_kick")

    # `ranked` arrives worst→best; identify kick targets from the worst end
    eligible   = [m for m in ranked if not m.excluded]
    kick_tags: set[str] = {m.tag for m in eligible[:players_to_kick]}

    # Reverse so rank 1 = most active
    best_to_worst = list(reversed(ranked))
    total = len(best_to_worst)

    worst = eligible[0] if eligible else None
    if worst and worst.days_offline is not None and worst.days_offline > 30:
        color = discord.Color.red()
    elif worst and worst.days_offline is not None and worst.days_offline > 14:
        color = discord.Color.orange()
    else:
        color = discord.Color.green()

    now_str = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(
        title=f"🏆 {CLAN_NAME}  —  Activity Leaderboard",
        description=(
            f"**{total}/{CLAN_MAX}** members  •  "
            f"**{len(eligible)}** eligible to kick  •  "
            f"Updated {now_str}"
        ),
        color=color,
    )

    CHUNK = 20
    for start in range(0, total, CHUNK):
        slice_ = best_to_worst[start : start + CHUNK]
        numbered = [(start + i + 1, m) for i, m in enumerate(slice_)]
        end = min(start + CHUNK, total)
        embed.add_field(
            name=f"📊 Best → Worst — #{start + 1}–#{end}",
            value=_table_field(numbered, kick_tags),
            inline=False,
        )

    embed.set_footer(text="<KICK = kick target  •  Protected (leader/co-leader) are included but won't be kicked")
    return embed


# ── Bot ───────────────────────────────────────────────────────────────────────

class CoCBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._last_activity_check: datetime = datetime.now(timezone.utc)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=GUILD_ID)
        self.tree.add_command(InviteGroup(), guild=guild)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.success("Slash commands synced to guild {}", GUILD_ID)
        self.activity_check_task.start()

    async def on_ready(self) -> None:
        logger.success("Logged in as {} (ID: {})", self.user, self.user.id)

    @tasks.loop(minutes=30)
    async def activity_check_task(self) -> None:
        """Silently refresh the activity tracker on the configured schedule."""
        interval_hours: float = config_manager.get("activity_check_interval_hours")
        elapsed = (datetime.now(timezone.utc) - self._last_activity_check).total_seconds()
        if elapsed < interval_hours * 3600:
            return
        self._last_activity_check = datetime.now(timezone.utc)
        try:
            await _fetch_ranked_members()
            logger.success("[activity] Tracker refreshed at {}", self._last_activity_check.strftime("%H:%M UTC"))
        except Exception as exc:
            logger.error("[activity] Refresh failed: {}", exc)

    @activity_check_task.before_loop
    async def before_activity_check(self) -> None:
        await self.wait_until_ready()


client = CoCBot()


# ── /leaderboard ──────────────────────────────────────────────────────────────

@client.tree.command(name="leaderboard", description="Show clan member activity rankings (best to worst)")
async def leaderboard(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    try:
        ranked = await _fetch_ranked_members()
    except Exception as exc:
        await interaction.followup.send(f"❌ Failed to fetch member data: {exc}")
        return
    embed = _build_embed(ranked)
    await interaction.followup.send(embed=embed)


# ── /invite (command group) ───────────────────────────────────────────────────

class InviteGroup(app_commands.Group):
    def __init__(self) -> None:
        super().__init__(name="invite", description="Control the notice-board / invite loop")

    @app_commands.command(name="start", description="Start scanning clans and sending invites")
    @app_commands.describe(moderate="Also kick inactive members after each invite batch when clan is full")
    async def start(self, interaction: discord.Interaction, moderate: bool = False) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message(_ADMIN_DENIED, ephemeral=True)
            return
        await interaction.response.defer()
        result = await _start_invite_loop(moderate)
        await interaction.followup.send(result)

    @app_commands.command(name="stop", description="Stop the running invite loop")
    async def stop(self, interaction: discord.Interaction) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message(_ADMIN_DENIED, ephemeral=True)
            return
        await interaction.response.defer()
        result = await _stop_invite_loop()
        await interaction.followup.send(result)

    @app_commands.command(name="status", description="Check invite loop status and current recruit filters")
    async def status(self, interaction: discord.Interaction) -> None:
        cfg = config_manager.load()
        lines = [
            _invite_status(),
            "",
            "**Current recruit filters:**",
            f"  Town Hall: `{cfg['min_th']}` – `{cfg['max_th']}`",
            f"  Min donations: `{cfg['min_donations']}`",
            f"  Invite every: `{cfg['invite_every']}` players queued",
            f"  Moderate on invite: `{cfg['moderate_on_invite']}`",
        ]
        await interaction.response.send_message("\n".join(lines))


# ── /config ───────────────────────────────────────────────────────────────────

@client.tree.command(name="config", description="View or change a bot setting")
@app_commands.describe(
    key="Setting name — leave empty to show all settings",
    value="New value — leave empty to view current value only",
)
async def config_cmd(
    interaction: discord.Interaction,
    key: str = "",
    value: str = "",
) -> None:
    cfg = config_manager.load()

    # Show all settings
    if not key:
        embed = discord.Embed(title="⚙️ Current Configuration", color=discord.Color.blurple())
        recruit_lines, mod_lines, other_lines = [], [], []
        for k, (type_str, desc) in FIELD_META.items():
            line = f"`{k}` = **{cfg.get(k)}**  *({type_str})* — {desc}"
            if k in ("min_th", "max_th", "min_donations", "invite_every", "moderate_on_invite"):
                recruit_lines.append(line)
            elif k in ("players_to_kick", "offline_threshold_days", "dry_run"):
                mod_lines.append(line)
            else:
                other_lines.append(line)
        if recruit_lines:
            embed.add_field(name="🎯 Recruit Filters", value="\n".join(recruit_lines), inline=False)
        if mod_lines:
            embed.add_field(name="🔪 Moderation", value="\n".join(mod_lines), inline=False)
        if other_lines:
            embed.add_field(name="⏱️ Other", value="\n".join(other_lines), inline=False)
        await interaction.response.send_message(embed=embed)
        return

    # Show a single key (no value provided)
    if not value:
        if key not in FIELD_META:
            await interaction.response.send_message(
                f"❌ Unknown key `{key}`. Use `/config` (no arguments) to see all keys.", ephemeral=True
            )
            return
        type_str, desc = FIELD_META[key]
        current = cfg.get(key, "N/A")
        await interaction.response.send_message(f"⚙️ `{key}` = **{current}**  *({type_str})*\n{desc}")
        return

    # Set a value — admin only
    if not _is_admin(interaction):
        await interaction.response.send_message(_ADMIN_DENIED, ephemeral=True)
        return
    ok, msg = config_manager.set_value(key, value)
    if ok:
        await interaction.response.send_message(f"✅ {msg}")
    else:
        await interaction.response.send_message(f"❌ {msg}", ephemeral=True)


@config_cmd.autocomplete("key")
async def config_key_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=f"{k}  ({t}) — {desc}"[:100], value=k)
        for k, (t, desc) in FIELD_META.items()
        if current.lower() in k.lower()
    ][:25]


# ── /screenshot ───────────────────────────────────────────────────────────────

@client.tree.command(name="screenshot", description="[Admin] Capture the emulator screen and post it here")
async def screenshot_cmd(interaction: discord.Interaction) -> None:
    if not _is_admin(interaction):
        await interaction.response.send_message(_ADMIN_DENIED, ephemeral=True)
        return
    await interaction.response.defer()
    try:
        loop = asyncio.get_event_loop()
        png_bytes = await loop.run_in_executor(None, _adb_screenshot_sync)
    except Exception as exc:
        await interaction.followup.send(f"❌ Screenshot failed: {exc}")
        return
    file = discord.File(io.BytesIO(png_bytes), filename="screenshot.png")
    await interaction.followup.send(file=file)


# ── /forcemenu ────────────────────────────────────────────────────────────────

@client.tree.command(name="forcemenu", description="[Admin] Press ESC ×7 + Cancel to force-return to the main screen")
async def forcemenu_cmd(interaction: discord.Interaction) -> None:
    if not _is_admin(interaction):
        await interaction.response.send_message(_ADMIN_DENIED, ephemeral=True)
        return
    await interaction.response.defer()
    try:
        await _adb_esc_cancel(7)
    except Exception as exc:
        await interaction.followup.send(f"❌ ADB command failed: {exc}")
        return
    await interaction.followup.send("✅ Pressed ESC ×7 + Cancel — should be on the main screen now.")


# ── /help ─────────────────────────────────────────────────────────────────────

@client.tree.command(name="help", description="List all available bot commands")
async def help_cmd(interaction: discord.Interaction) -> None:
    embed = discord.Embed(title="🤖 CoCBot — Command Reference", color=discord.Color.blurple())
    embed.add_field(
        name="📊 /leaderboard",
        value=(
            "Clan activity ranked **best → worst** (most active at top).\n"
            "Members marked `<KICK` are the configured kick targets."
        ),
        inline=False,
    )
    embed.add_field(
        name="▶️ /invite start [moderate]  🔒",
        value=(
            "Start the automated loop: scan notice board → filter players → send invites.\n"
            "`moderate=True` — also kick the worst members after each batch when clan is full."
        ),
        inline=False,
    )
    embed.add_field(name="⏹️ /invite stop  🔒",   value="Stop the running invite loop.", inline=False)
    embed.add_field(name="ℹ️ /invite status", value="Check whether the loop is running + current filter values.", inline=False)
    embed.add_field(
        name="⚙️ /config",
        value=(
            "Show all current settings (any member).\n"
            "**`/config <key>`** — Show one setting.\n"
            "**`/config <key> <value>`** 🔒 — Change a setting live (admin only).\n"
            "Key autocomplete is available. Configurable settings:\n"
            "`min_th`  `max_th`  `min_donations`  `invite_every`  `moderate_on_invite`\n"
            "`players_to_kick`  `offline_threshold_days`  `dry_run`  `activity_check_interval_hours`"
        ),
        inline=False,
    )
    embed.add_field(
        name="📸 /screenshot  🔒",
        value="Capture the emulator screen and post it in this channel.",
        inline=False,
    )
    embed.add_field(
        name="🔧 /forcemenu  🔒",
        value="Press ESC ×7 then tap Cancel to force-navigate back to the main screen.",
        inline=False,
    )
    embed.add_field(name="❓ /help", value="Show this message.", inline=False)
    embed.set_footer(text="🔒 = Admin / Manage Guild required  •  Activity tracker auto-refreshes every N hours (activity_check_interval_hours)")
    await interaction.response.send_message(embed=embed)

# ── /adbtarget ───────────────────────────────────────────────────────────────────────

@client.tree.command(name="adbtarget", description="[Admin] Switch ADB target between phone and BlueStacks (testing)")
@app_commands.describe(target="Which device to connect to")
@app_commands.choices(target=[
    app_commands.Choice(name="phone — physical Android (10.0.0.47:5555)",  value="phone"),
    app_commands.Choice(name="bluestacks — Windows emulator (127.0.0.1:5556)", value="bluestacks"),
])
async def adbtarget_cmd(interaction: discord.Interaction, target: str = "") -> None:
    if not _is_admin(interaction):
        await interaction.response.send_message(_ADMIN_DENIED, ephemeral=True)
        return

    if not target:
        current = f"{settings.adb_host}:{settings.adb_port}"
        lines = ["**Current ADB target:** `" + current + "`", ""]
        for name, (host, port) in _ADB_TARGETS.items():
            marker = " ◀ active" if (settings.adb_host == host and settings.adb_port == port) else ""
            lines.append(f"• `{name}` — `{host}:{port}`{marker}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return

    host, port = _ADB_TARGETS[target]
    settings.adb_host = host  # type: ignore[misc]
    settings.adb_port = port  # type: ignore[misc]
    logger.info("[adbtarget] Switched to {} ({}:{})", target, host, port)
    await interaction.response.send_message(
        f"✅ ADB target switched to **{target}** — `{host}:{port}`\n"
        f"⚠️ This is in-memory only; the bot reverts to `.env` values on restart."
    )

# ── Entry-point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_BOT_TOKEN is not set in .env")
        raise SystemExit(1)
    if not GUILD_ID:
        logger.error("DISCORD_GUILD_ID is not set in .env")
        raise SystemExit(1)
    client.run(TOKEN)
