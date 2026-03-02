"""
Shared runtime configuration for cocbot tools.
===============================================
All mutable settings live in bot_config.json (same directory).
Discord /config commands write to this file; tool scripts read from it.
Module-level constants in the individual scripts act as fallbacks only.
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "bot_config.json"

# ── Defaults (first-run / fallback) ──────────────────────────────────────────
DEFAULTS: dict = {
    # Recruitment filters (find_players.py)
    "min_th":               14,
    "max_th":               18,
    "min_donations":        1000,
    # Invite loop (notice_board.py)
    "invite_every":         100,
    "moderate_on_invite":   False,
    # Moderation (moderation.py)
    "players_to_kick":      2,
    "offline_threshold_days": 7.0,
    "dry_run":              True,
    # Activity tracker background task
    "activity_check_interval_hours": 3.0,
}

# ── Field metadata for Discord /config autocomplete and validation ─────────────
# key -> (type_str, short description)
FIELD_META: dict[str, tuple[str, str]] = {
    "min_th":                        ("int",   "Minimum town hall level to recruit"),
    "max_th":                        ("int",   "Maximum town hall level to recruit"),
    "min_donations":                 ("int",   "Minimum seasonal donations to recruit"),
    "invite_every":                  ("int",   "Queue this many players before sending invites"),
    "moderate_on_invite":            ("bool",  "Run moderation after each invite batch if clan full"),
    "players_to_kick":               ("int",   "Number of members to kick per moderation run"),
    "offline_threshold_days":        ("float", "Never kick members active within this many days"),
    "dry_run":                       ("bool",  "If True, moderation presses Cancel (safe test mode)"),
    "activity_check_interval_hours": ("float", "How often to refresh the activity tracker (hours)"),
}


# ── I/O ───────────────────────────────────────────────────────────────────────

def load() -> dict:
    """Load config from disk, filling any missing keys with defaults."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        # Backfill any newly-added keys
        changed = False
        for k, v in DEFAULTS.items():
            if k not in data:
                data[k] = v
                changed = True
        if changed:
            save(data)
        return data
    # First run — write defaults
    save(dict(DEFAULTS))
    return dict(DEFAULTS)


def save(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get(key: str):
    """Read a single value (always fresh from disk)."""
    return load().get(key, DEFAULTS.get(key))


def set_value(key: str, raw_value: str) -> tuple[bool, str]:
    """
    Parse raw_value into the correct type for key and persist.

    Returns
    -------
    (True,  "success message")
    (False, "error message")
    """
    if key not in FIELD_META:
        known = ", ".join(f"`{k}`" for k in FIELD_META)
        return False, f"Unknown key `{key}`.  Known keys: {known}"

    type_str, _ = FIELD_META[key]
    try:
        if type_str == "int":
            value: int | float | bool | str = int(raw_value)
        elif type_str == "float":
            value = float(raw_value)
        elif type_str == "bool":
            if raw_value.lower() in ("true", "1", "yes", "on"):
                value = True
            elif raw_value.lower() in ("false", "0", "no", "off"):
                value = False
            else:
                return False, f"Expected true/false for `{key}`, got `{raw_value}`"
        else:
            value = raw_value
    except ValueError:
        return False, f"Expected {type_str} for `{key}`, got `{raw_value}`"

    cfg = load()
    old = cfg.get(key)
    cfg[key] = value
    save(cfg)
    return True, f"`{key}` changed: `{old}` → `{value}`"
