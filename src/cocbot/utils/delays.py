"""Utility: human-like random delays to avoid bot detection."""

from __future__ import annotations

import asyncio
import random


async def human_delay(min_s: float = 0.3, max_s: float = 1.2) -> None:
    """
    Async sleep for a random duration between min_s and max_s seconds.
    Simulates human reaction time between actions.
    """
    await asyncio.sleep(random.uniform(min_s, max_s))


async def long_pause(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Longer pause — use when navigating between menus."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def break_pause(min_s: float = 300, max_s: float = 900) -> None:
    """
    Multi-minute random break — simulates the player stepping away.
    Call this every N attack cycles.
    """
    duration = random.uniform(min_s, max_s)
    await asyncio.sleep(duration)


def jitter(value: float, pct: float = 0.15) -> float:
    """Add ±pct% random jitter to a value (e.g. coordinates, timings)."""
    delta = value * pct
    return value + random.uniform(-delta, delta)


def jitter_point(x: int, y: int, radius: int = 5) -> tuple[int, int]:
    """
    Return (x, y) with a small random offset so taps never land at exactly
    the same pixel every time.
    """
    dx = random.randint(-radius, radius)
    dy = random.randint(-radius, radius)
    return x + dx, y + dy
