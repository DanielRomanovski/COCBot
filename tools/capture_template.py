"""
Template Capture Utility
========================
A helper script to capture template images from a live screenshot.

Usage
-----
Run this script while the game is on the screen you want to capture:

    python tools/capture_template.py --name attack_button

This will:
1. Take a screenshot from the connected device
2. Show it to you and ask you to define the crop region (click & drag)
3. Save the cropped region to assets/templates/<name>.png

Requirements: ADB must be reachable at localhost:5555 (or set ADB_HOST/ADB_PORT).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.config import settings

TEMPLATES_DIR = Path(__file__).parent.parent / "assets" / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Global state for mouse callback
_drawing = False
_x0 = _y0 = _x1 = _y1 = 0
_crop_done = False


def _mouse_callback(event, x, y, flags, param):
    global _drawing, _x0, _y0, _x1, _y1, _crop_done
    if event == cv2.EVENT_LBUTTONDOWN:
        _drawing = True
        _x0, _y0 = x, y
        _x1, _y1 = x, y
    elif event == cv2.EVENT_MOUSEMOVE and _drawing:
        _x1, _y1 = x, y
    elif event == cv2.EVENT_LBUTTONUP:
        _drawing = False
        _x1, _y1 = x, y
        _crop_done = True


def capture_template(name: str) -> None:
    global _crop_done

    print(f"Connecting to device at {settings.adb_host}:{settings.adb_port}...")
    cfg = DeviceConfig(
        host=settings.adb_host,
        port=settings.adb_port,
        width=settings.emulator_width,
        height=settings.emulator_height,
    )
    device = ADBDevice(cfg)
    device.connect()

    print("Taking screenshot...")
    screenshot = device.screenshot()

    # Scale down for display if too large
    display_scale = 0.5
    dw = int(screenshot.shape[1] * display_scale)
    dh = int(screenshot.shape[0] * display_scale)
    display = cv2.resize(screenshot, (dw, dh))

    cv2.namedWindow("Select region — click and drag, then press ENTER")
    cv2.setMouseCallback("Select region — click and drag, then press ENTER", _mouse_callback)

    print("Click and drag to select the template region. Press ENTER to save.")

    while True:
        frame = display.copy()
        if _drawing or _crop_done:
            cv2.rectangle(frame, (_x0, _y0), (_x1, _y1), (0, 255, 0), 2)
        cv2.imshow("Select region — click and drag, then press ENTER", frame)

        key = cv2.waitKey(1)
        if key == 13 and _crop_done:  # ENTER
            break
        if key == 27:  # ESC
            print("Cancelled")
            cv2.destroyAllWindows()
            return

    cv2.destroyAllWindows()

    # Scale coordinates back to full resolution
    x0 = int(min(_x0, _x1) / display_scale)
    y0 = int(min(_y0, _y1) / display_scale)
    x1 = int(max(_x0, _x1) / display_scale)
    y1 = int(max(_y0, _y1) / display_scale)

    cropped = screenshot[y0:y1, x0:x1]
    out_path = TEMPLATES_DIR / f"{name}.png"
    cv2.imwrite(str(out_path), cropped)
    print(f"Saved template: {out_path} ({x1-x0}×{y1-y0}px)")

    # Show a preview
    cv2.imshow(f"Saved: {name}.png", cropped)
    cv2.waitKey(1500)
    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Capture a template image from the emulator screen")
    parser.add_argument("--name", required=True, help="Template name (e.g. 'attack_button')")
    args = parser.parse_args()
    capture_template(args.name)


if __name__ == "__main__":
    main()
