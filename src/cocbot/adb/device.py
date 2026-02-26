"""
ADB Device Manager
==================
Wraps `adbutils` to provide a clean interface for:
- Connecting to the Android emulator over TCP
- Taking screenshots → numpy arrays
- Sending tap, swipe, long-press, and key events
- Launching / force-stopping apps
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from adbutils import AdbClient, AdbDevice, AdbError
from loguru import logger
from PIL import Image

if TYPE_CHECKING:
    pass

# Clash of Clans package name on Android
COC_PACKAGE = "com.supercell.clashofclans"


@dataclass
class DeviceConfig:
    host: str = "localhost"
    port: int = 5555
    serial: str | None = None  # Explicit serial overrides host:port
    width: int = 1080
    height: int = 1920
    connect_timeout: int = 30  # seconds


class ADBDevice:
    """
    High-level ADB device controller.

    Usage
    -----
    async with ADBDevice(config) as dev:
        screenshot = await dev.screenshot()
        await dev.tap(540, 960)
    """

    def __init__(self, config: DeviceConfig) -> None:
        self.config = config
        self._client = AdbClient(host="127.0.0.1", port=5037)
        self._device: AdbDevice | None = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Connect to the emulator via ADB-over-TCP and verify the connection."""
        if self.config.serial:
            serial = self.config.serial
        else:
            serial = f"{self.config.host}:{self.config.port}"

        logger.info("Connecting to ADB device: {}", serial)

        # Tell the local ADB server to connect to the remote emulator
        if not self.config.serial:
            result = self._client.connect(serial, timeout=self.config.connect_timeout)
            logger.debug("ADB connect result: {}", result)

        # Get the device handle
        deadline = time.time() + self.config.connect_timeout
        while time.time() < deadline:
            try:
                self._device = self._client.device(serial)
                info = self._device.prop.model
                logger.success("Connected to device: {} (model={})", serial, info)
                return
            except AdbError as e:
                logger.warning("Waiting for device... ({})", e)
                time.sleep(2)

        raise ConnectionError(f"Could not connect to ADB device {serial} within timeout")

    def disconnect(self) -> None:
        if self._device:
            logger.info("Disconnecting ADB device")
            self._device = None

    def __enter__(self) -> "ADBDevice":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

    @property
    def device(self) -> AdbDevice:
        if self._device is None:
            raise RuntimeError("Not connected — call connect() first")
        return self._device

    # ── Screenshot ────────────────────────────────────────────────────────────

    def screenshot(self) -> np.ndarray:
        """
        Capture the current screen.

        Returns
        -------
        np.ndarray
            BGR image array (OpenCV format), shape (height, width, 3)
        """
        raw: bytes = self.device.screenshot()  # returns PNG bytes via adbutils
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        arr = np.array(img)
        # PIL gives RGB; convert to BGR for OpenCV
        return arr[:, :, ::-1].copy()

    def screenshot_pil(self) -> Image.Image:
        """Return the screenshot as a PIL Image (RGB)."""
        raw: bytes = self.device.screenshot()
        return Image.open(io.BytesIO(raw)).convert("RGB")

    # ── Input: Tap ────────────────────────────────────────────────────────────

    def tap(self, x: int, y: int) -> None:
        """Send a single tap at (x, y)."""
        logger.debug("TAP ({}, {})", x, y)
        self.device.shell(f"input tap {x} {y}")

    def long_press(self, x: int, y: int, duration_ms: int = 800) -> None:
        """Long press at (x, y) for duration_ms milliseconds."""
        logger.debug("LONG_PRESS ({}, {}) {}ms", x, y, duration_ms)
        # swipe to same point with a duration = long press
        self.device.shell(f"input swipe {x} {y} {x} {y} {duration_ms}")

    # ── Input: Swipe ─────────────────────────────────────────────────────────

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
    ) -> None:
        """Swipe from (x1, y1) to (x2, y2) over duration_ms milliseconds."""
        logger.debug("SWIPE ({},{}) → ({},{}) {}ms", x1, y1, x2, y2, duration_ms)
        self.device.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def scroll_down(self, amount: int = 400) -> None:
        """Scroll down by `amount` pixels from the centre of the screen."""
        cx = self.config.width // 2
        cy = self.config.height // 2
        self.swipe(cx, cy, cx, cy - amount, duration_ms=400)

    def scroll_up(self, amount: int = 400) -> None:
        cx = self.config.width // 2
        cy = self.config.height // 2
        self.swipe(cx, cy, cx, cy + amount, duration_ms=400)

    # ── Input: Keys ──────────────────────────────────────────────────────────

    def press_back(self) -> None:
        """Press the Android Back button."""
        self.device.shell("input keyevent 4")

    def press_home(self) -> None:
        """Press the Android Home button."""
        self.device.shell("input keyevent 3")

    # ── App Control ──────────────────────────────────────────────────────────

    def launch_coc(self) -> None:
        """Launch Clash of Clans."""
        logger.info("Launching Clash of Clans ({})", COC_PACKAGE)
        self.device.shell(
            f"monkey -p {COC_PACKAGE} -c android.intent.category.LAUNCHER 1"
        )

    def force_stop_coc(self) -> None:
        """Force-stop Clash of Clans."""
        logger.info("Force-stopping Clash of Clans")
        self.device.shell(f"am force-stop {COC_PACKAGE}")

    def restart_coc(self, wait_s: float = 5.0) -> None:
        """Force-stop then re-launch CoC."""
        self.force_stop_coc()
        time.sleep(wait_s)
        self.launch_coc()

    def is_coc_running(self) -> bool:
        """Return True if CoC is in the foreground."""
        output = self.device.shell("dumpsys window windows | grep mCurrentFocus")
        return COC_PACKAGE in output

    # ── Diagnostics ──────────────────────────────────────────────────────────

    def get_resolution(self) -> tuple[int, int]:
        """Query actual screen resolution from the device."""
        output = self.device.shell("wm size")
        # Output: "Physical size: 1080x1920"
        try:
            size_part = output.split(":")[-1].strip()
            w, h = size_part.split("x")
            return int(w), int(h)
        except Exception:
            return self.config.width, self.config.height
