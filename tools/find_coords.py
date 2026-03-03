"""
Calibration Tool
================
Prints the pixel coordinates when you tap on a screenshot.
Use this to find the exact (x, y) coordinates for Coords in navigator.py.

Usage
-----
    python tools/find_coords.py

Click anywhere on the screenshot window to print the coordinates.
Press ESC to quit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
from dotenv import load_dotenv

load_dotenv()

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.config import settings

# ── Device toggle ─────────────────────────────────────────────────────────────
# Set to "phone" to connect to the physical phone (10.0.0.47:5555, 1440×720)
# Set to "emulator" to connect to BlueStacks via the .env settings
DEVICE = "phone"   # "phone" | "emulator"

_DEVICE_CONFIGS = {
    "emulator": dict(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    ),
    "phone": dict(
        host="10.0.0.47",
        port=5555,
        width=1440,
        height=720,
    ),
}
# ──────────────────────────────────────────────────────────────────────────────


def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        scale = param["scale"]
        rx = int(x / scale)
        ry = int(y / scale)
        print(f"  Clicked display=({x}, {y})  →  device=({rx}, {ry})")


def main():
    cfg_kwargs = _DEVICE_CONFIGS[DEVICE]
    print(f"Connecting to: {DEVICE} ({cfg_kwargs['host']}:{cfg_kwargs['port']}, {cfg_kwargs['width']}×{cfg_kwargs['height']})")
    cfg = DeviceConfig(
        host=cfg_kwargs["host"],
        port=cfg_kwargs["port"],
        width=cfg_kwargs["width"],
        height=cfg_kwargs["height"],
    )
    device = ADBDevice(cfg)
    device.connect()

    print(f"Connected. Taking screenshot from {cfg.width}×{cfg.height}...")

    scale = 0.5
    cv2.namedWindow("Click to get coordinates — ESC to quit")
    cv2.setMouseCallback(
        "Click to get coordinates — ESC to quit",
        on_click,
        param={"scale": scale},
    )

    print("Click anywhere on the image to print coordinates. Press ESC to quit. Press 'r' in terminal to retake screenshot.\n")

    import threading
    import queue

    key_queue = queue.Queue()

    def key_listener():
        while True:
            key = input()
            key_queue.put(key)
            if key.lower() == 'esc':
                break

    listener_thread = threading.Thread(target=key_listener, daemon=True)
    listener_thread.start()

    def take_screenshot():
        screenshot = device.screenshot()
        dw = int(screenshot.shape[1] * scale)
        dh = int(screenshot.shape[0] * scale)
        return cv2.resize(screenshot, (dw, dh))

    display = take_screenshot()

    while True:
        cv2.imshow("Click to get coordinates — ESC to quit", display)
        key = cv2.waitKey(1)
        # ESC key in window
        if key == 27:
            break
        # Check for 'r' in terminal
        if not key_queue.empty():
            user_key = key_queue.get()
            if user_key.lower() == 'r':
                print("Retaking screenshot...")
                display = take_screenshot()
            elif user_key.lower() == 'esc':
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
