"""
Higher-level input helpers that layer on top of ADBDevice.

Provides human-like, async-friendly wrappers that:
- Add random jitter to coordinates
- Insert random delays between actions
- Combine multiple primitives into common gestures
"""

from __future__ import annotations

import asyncio
import random

from loguru import logger

from cocbot.adb.device import ADBDevice
from cocbot.utils.delays import human_delay, jitter_point, long_pause


class InputController:
    """
    Async wrapper around ADBDevice for human-like input.

    All methods are async so they can be used in the main event loop
    alongside coc.py async calls.
    """

    def __init__(
        self,
        device: ADBDevice,
        min_delay: float = 0.3,
        max_delay: float = 1.2,
    ) -> None:
        self.device = device
        self.min_delay = min_delay
        self.max_delay = max_delay

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _delay(self) -> None:
        await human_delay(self.min_delay, self.max_delay)

    def _jitter(self, x: int, y: int, radius: int = 5) -> tuple[int, int]:
        return jitter_point(x, y, radius)

    # ── Tap ───────────────────────────────────────────────────────────────────

    async def tap(self, x: int, y: int, jitter_r: int = 5) -> None:
        """Tap at (x, y) with jitter and a random post-tap delay."""
        jx, jy = self._jitter(x, y, jitter_r)
        await asyncio.get_event_loop().run_in_executor(
            None, self.device.tap, jx, jy
        )
        await self._delay()

    async def tap_exact(self, x: int, y: int) -> None:
        """Tap at exactly (x, y) — no jitter. Use sparingly."""
        await asyncio.get_event_loop().run_in_executor(
            None, self.device.tap, x, y
        )
        await self._delay()

    async def double_tap(self, x: int, y: int) -> None:
        """Two rapid taps at the same location."""
        await self.tap(x, y, jitter_r=3)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await self.tap(x, y, jitter_r=3)

    # ── Swipe ─────────────────────────────────────────────────────────────────

    async def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
    ) -> None:
        await asyncio.get_event_loop().run_in_executor(
            None, self.device.swipe, x1, y1, x2, y2, duration_ms
        )
        await self._delay()

    async def scroll_down(self, amount: int = 400) -> None:
        await asyncio.get_event_loop().run_in_executor(
            None, self.device.scroll_down, amount
        )
        await self._delay()

    async def scroll_up(self, amount: int = 400) -> None:
        await asyncio.get_event_loop().run_in_executor(
            None, self.device.scroll_up, amount
        )
        await self._delay()

    # ── Buttons ───────────────────────────────────────────────────────────────

    async def press_back(self) -> None:
        await asyncio.get_event_loop().run_in_executor(
            None, self.device.press_back
        )
        await self._delay()

    async def press_home(self) -> None:
        await asyncio.get_event_loop().run_in_executor(
            None, self.device.press_home
        )
        await long_pause(1.0, 2.5)

    # ── Screenshot ────────────────────────────────────────────────────────────

    async def screenshot(self):  # → np.ndarray
        """Async screenshot — runs in thread-pool to avoid blocking."""
        import numpy as np  # local import; already installed

        loop = asyncio.get_event_loop()
        img = await loop.run_in_executor(None, self.device.screenshot)
        return img

    # ── Drag troop deployment ─────────────────────────────────────────────────

    async def deploy_troops_line(
        self,
        start_x: int,
        y: int,
        end_x: int,
        count: int = 10,
    ) -> None:
        """
        Deploy `count` troops along a horizontal line from start_x to end_x.
        Each deployment is a tap, spaced evenly with small jitter.
        """
        step = (end_x - start_x) // max(count - 1, 1)
        for i in range(count):
            x = start_x + i * step
            jx, jy = self._jitter(x, y, radius=8)
            logger.debug("Deploying troop {} at ({}, {})", i + 1, jx, jy)
            await asyncio.get_event_loop().run_in_executor(
                None, self.device.tap, jx, jy
            )
            await asyncio.sleep(random.uniform(0.08, 0.25))
