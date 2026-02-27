"""
Tool: test_ocr_recruit.py
=========================
Standalone debug script to test the OCR recruit tag reading pipeline.

What it does:
  1. Connects to the ADB device (emulator)
  2. Takes a screenshot and saves it to debug_screenshot.png
  3. Runs OCR on each expected card position
  4. Prints the raw OCR text AND the parsed tag for each card

Run it:
  poetry run python tools/test_ocr_recruit.py

Make sure:
  - Your emulator is running with CoC open on the Recruit board
  - ADB is connected (adb connect localhost:5555)
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cocbot.adb.device import ADBDevice, DeviceConfig
from cocbot.vision.ocr import OCRReader

# ── Config ────────────────────────────────────────────────────────────────────
ADB_HOST = "localhost"
ADB_PORT = 5555

# Card layout — must match recruit.py
FIRST_CARD_Y = 450
CARD_HEIGHT = 210
CARDS_PER_PAGE = 4
TAG_ROI = lambda card_y: (60, card_y + 55, 250, 35)  # noqa: E731

SCREENSHOT_PATH = Path("debug_screenshot.png")
ANNOTATED_PATH  = Path("debug_annotated.png")


def draw_roi(img: np.ndarray, roi: tuple, label: str, color=(0, 255, 0)) -> None:
    """Draw a labelled bounding box on the image."""
    x, y, w, h = roi
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
    cv2.putText(img, label, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


def main() -> None:
    # ── Connect to device ─────────────────────────────────────────────────────
    config = DeviceConfig(host=ADB_HOST, port=ADB_PORT)
    device = ADBDevice(config)

    print(f"Connecting to ADB at {ADB_HOST}:{ADB_PORT} ...")
    try:
        device.connect()
    except Exception as e:
        print(f"[ERROR] Could not connect to ADB device: {e}")
        print("  Make sure your emulator is running and ADB is enabled.")
        print(f"  Try: adb connect {ADB_HOST}:{ADB_PORT}")
        sys.exit(1)

    # ── Take screenshot ───────────────────────────────────────────────────────
    print("Taking screenshot...")
    screenshot = device.screenshot()
    cv2.imwrite(str(SCREENSHOT_PATH), screenshot)
    print(f"  Saved to {SCREENSHOT_PATH.resolve()}")

    # ── Run OCR on each card position ─────────────────────────────────────────
    ocr = OCRReader()
    annotated = screenshot.copy()

    print("\n── OCR Results ──────────────────────────────────────────────────────")
    for i in range(CARDS_PER_PAGE):
        card_y = FIRST_CARD_Y + i * CARD_HEIGHT
        roi = TAG_ROI(card_y)
        x, y, w, h = roi

        # Crop the ROI
        crop = screenshot[y : y + h, x : x + w]

        # Raw OCR output
        raw_text = ocr.read_text(screenshot, roi).strip()

        # Try to find a player tag pattern
        import re
        match = re.search(r"#[0-9A-Z]{6,9}", raw_text.upper())
        tag = match.group() if match else None

        status = f"✓  Tag: {tag}" if tag else "✗  No tag found"
        print(f"  Card {i} (y={card_y})  raw='{raw_text}'  →  {status}")

        # Draw on annotated image
        color = (0, 200, 0) if tag else (0, 0, 255)
        draw_roi(annotated, roi, f"Card {i}: {tag or '???'}", color)

        # Save individual crop for inspection
        crop_path = Path(f"debug_card_{i}_crop.png")
        cv2.imwrite(str(crop_path), crop)

    # ── Save annotated screenshot ─────────────────────────────────────────────
    cv2.imwrite(str(ANNOTATED_PATH), annotated)
    print(f"\nAnnotated screenshot saved to {ANNOTATED_PATH.resolve()}")
    print("Open it to see exactly where the bot is looking for tags.")
    print("\nTip: if all cards show 'No tag found', the ROI coordinates")
    print("     (FIRST_CARD_Y, CARD_HEIGHT, TAG_ROI) need calibrating.")
    print("     Use tools/find_coords.py to find the right values.")


if __name__ == "__main__":
    main()
