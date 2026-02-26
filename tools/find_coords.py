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


def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        scale = param["scale"]
        rx = int(x / scale)
        ry = int(y / scale)
        print(f"  Clicked display=({x}, {y})  →  device=({rx}, {ry})")


def main():
    cfg = DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    )
    device = ADBDevice(cfg)
    device.connect()

    print(f"Connected. Taking screenshot from {settings.emulator_width}×{settings.emulator_height}...")
    screenshot = device.screenshot()

    scale = 0.5
    dw = int(screenshot.shape[1] * scale)
    dh = int(screenshot.shape[0] * scale)
    display = cv2.resize(screenshot, (dw, dh))

    cv2.namedWindow("Click to get coordinates — ESC to quit")
    cv2.setMouseCallback(
        "Click to get coordinates — ESC to quit",
        on_click,
        param={"scale": scale},
    )

    print("Click anywhere on the image to print coordinates. Press ESC to quit.\n")

    while True:
        cv2.imshow("Click to get coordinates — ESC to quit", display)
        if cv2.waitKey(1) == 27:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
