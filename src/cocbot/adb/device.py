# ADB device controller — wraps adbutils to connect to the Android emulator
# and send input events, take screenshots, and manage the CoC app.

from __future__ import annotations

import io
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from adbutils import AdbClient, AdbDevice, AdbError
from loguru import logger
from PIL import Image

if TYPE_CHECKING:
    pass

# Clash of Clans package name on Android
COC_PACKAGE = "com.supercell.clashofclans"

# Bundled ADB binary (Windows). Falls back to system adb on Linux/Docker.
_BUNDLED_ADB = (
    Path(__file__).resolve().parents[3]
    / "platform-tools" / "platform-tools" / "adb.exe"
)


def _adb_bin() -> str:
    """Return the path to the adb binary, preferring the bundled one on Windows."""
    if _BUNDLED_ADB.exists():
        return str(_BUNDLED_ADB)
    found = shutil.which("adb")
    if found:
        return found
    raise FileNotFoundError(
        "adb not found — install Android platform-tools or add adb to PATH"
    )


@dataclass
class DeviceConfig:
    host: str = "localhost"
    port: int = 5555
    serial: str | None = None  # explicit serial overrides host:port
    width: int = 1920
    height: int = 1080
    connect_timeout: int = 30  # seconds


class ADBDevice:
    """High-level ADB device controller. Use as a context manager or call connect() manually."""

    def __init__(self, config: DeviceConfig) -> None:
        self.config = config
        self._client = AdbClient(host="127.0.0.1", port=5037)
        self._device: AdbDevice | None = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Connect to the emulator via ADB-over-TCP and wait until the device is ready."""
        if self.config.serial:
            serial = self.config.serial
        else:
            serial = f"{self.config.host}:{self.config.port}"

        logger.info("Connecting to ADB device: {}", serial)

        adb = _adb_bin()
        subprocess.run([adb, "kill-server"], capture_output=True)
        subprocess.run([adb, "start-server"], capture_output=True)
        time.sleep(1.0)

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
                # Give the ADB shell channel a moment to fully open
                time.sleep(2.0)
                return
            except AdbError as e:
                logger.warning("Waiting for device... ({})", e)
                time.sleep(2)

        raise ConnectionError(f"Could not connect to ADB device {serial} within timeout")

    def disconnect(self) -> None:
        if self._device:
            logger.info("Disconnecting ADB device")
            self._device = None

    @property
    def _serial(self) -> str:
        """Return the serial string used for adb -s <serial>."""
        if self.config.serial:
            return self.config.serial
        return f"{self.config.host}:{self.config.port}"

    def _shell(self, cmd: str) -> str:
        """Run an adb shell command and return stdout."""
        result = subprocess.run(
            [_adb_bin(), "-s", self._serial, "shell", cmd],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

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
        """Return the current screen as a BGR numpy array (OpenCV format)."""
        raw = self.device.screenshot()  # newer adbutils returns PIL Image directly
        if isinstance(raw, Image.Image):
            img = raw.convert("RGB")
        else:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        arr = np.array(img)
        # PIL gives RGB; convert to BGR for OpenCV
        return arr[:, :, ::-1].copy()

    def screenshot_pil(self) -> Image.Image:
        """Return the screenshot as a PIL Image (RGB)."""
        raw = self.device.screenshot()
        if isinstance(raw, Image.Image):
            return raw.convert("RGB")
        return Image.open(io.BytesIO(raw)).convert("RGB")

    # ── Input: Tap ────────────────────────────────────────────────────────────

    def tap(self, x: int, y: int) -> None:
        """Send a single tap at (x, y)."""
        logger.debug("TAP ({}, {})", x, y)
        self._shell(f"input tap {x} {y}")

    def long_press(self, x: int, y: int, duration_ms: int = 800) -> None:
        """Long press at (x, y) for duration_ms milliseconds."""
        logger.debug("LONG_PRESS ({}, {}) {}ms", x, y, duration_ms)
        self._shell(f"input swipe {x} {y} {x} {y} {duration_ms}")

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
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

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
        self._shell("input keyevent 4")

    def press_home(self) -> None:
        """Press the Android Home button."""
        self._shell("input keyevent 3")

    # ── App Control ──────────────────────────────────────────────────────────

    def launch_coc(self) -> None:
        """Launch Clash of Clans."""
        logger.info("Launching Clash of Clans ({})", COC_PACKAGE)
        self._shell(f"monkey -p {COC_PACKAGE} -c android.intent.category.LAUNCHER 1")

    def force_stop_coc(self) -> None:
        """Force-stop Clash of Clans."""
        logger.info("Force-stopping Clash of Clans")
        self._shell(f"am force-stop {COC_PACKAGE}")

    def restart_coc(self, wait_s: float = 5.0) -> None:
        """Force-stop then re-launch CoC."""
        self.force_stop_coc()
        time.sleep(wait_s)
        self.launch_coc()

    def is_coc_running(self) -> bool:
        """Return True if CoC is in the foreground."""
        output = self._shell("dumpsys window windows | grep mCurrentFocus")
        return COC_PACKAGE in output

    # ── Diagnostics ──────────────────────────────────────────────────────────

    def get_resolution(self) -> tuple[int, int]:
        """Query the actual screen resolution from the device (e.g. 1920x1080)."""
        output = self._shell("wm size")
        # Output: "Physical size: 1920x1080"
        try:
            size_part = output.split(":")[-1].strip()
            w, h = size_part.split("x")
            return int(w), int(h)
        except Exception:
            return self.config.width, self.config.height
