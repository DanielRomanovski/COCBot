"""
Vision: OCR
===========
Uses pytesseract to read text and numbers from the screen.
Primarily used to read resource amounts: Gold, Elixir, Dark Elixir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from loguru import logger
from PIL import Image


@dataclass
class ResourceReading:
    gold: int = 0
    elixir: int = 0
    dark_elixir: int = 0
    valid: bool = False  # False if OCR failed / couldn't parse


class OCRReader:
    """
    Reads resource numbers and other text from CoC screenshots.

    Strategy
    --------
    1. Crop the region of interest (ROI) around the resource HUD
    2. Pre-process: grayscale, threshold, upscale
    3. Pass to pytesseract in digits-only mode
    4. Parse the string to an integer

    Coordinate constants are for 1080×1920 resolution.
    If you use a different resolution, scale accordingly or override them.
    """

    # ── Resource HUD regions (x, y, w, h) at 1080×1920 ────────────────────
    # These crop boxes match the default CoC HUD layout.
    # Tune these by inspecting a real screenshot.
    GOLD_ROI        = (120, 28,  260, 45)
    ELIXIR_ROI      = (120, 82,  260, 45)
    DARK_ELIXIR_ROI = (120, 136, 260, 45)

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        # Tesseract config: digits only, single-line PSM
        self._digits_config = "--psm 7 -c tessedit_char_whitelist=0123456789,"

    # ── Public API ────────────────────────────────────────────────────────────

    def read_resources(self, screenshot: np.ndarray) -> ResourceReading:
        """
        Read all three resource values from a village screenshot.

        Parameters
        ----------
        screenshot : np.ndarray
            BGR screenshot at 1080×1920 resolution.

        Returns
        -------
        ResourceReading
        """
        try:
            gold = self._read_number(screenshot, self.GOLD_ROI)
            elixir = self._read_number(screenshot, self.ELIXIR_ROI)
            dark = self._read_number(screenshot, self.DARK_ELIXIR_ROI)
            logger.debug("Resources — Gold:{} Elixir:{} DE:{}", gold, elixir, dark)
            return ResourceReading(gold=gold, elixir=elixir, dark_elixir=dark, valid=True)
        except Exception as e:
            logger.warning("OCR read_resources failed: {}", e)
            return ResourceReading(valid=False)

    def read_loot_preview(self, screenshot: np.ndarray) -> ResourceReading:
        """
        Read loot shown in the attack preview screen
        (after pressing 'Next' to find a base).

        These ROI coordinates differ from the village HUD.
        Tune for your resolution.
        """
        # Example ROIs for the attack screen — adjust as needed
        LOOT_GOLD_ROI        = (560, 148, 180, 38)
        LOOT_ELIXIR_ROI      = (560, 195, 180, 38)
        LOOT_DARK_ROI        = (560, 242, 180, 38)

        try:
            gold = self._read_number(screenshot, LOOT_GOLD_ROI)
            elixir = self._read_number(screenshot, LOOT_ELIXIR_ROI)
            dark = self._read_number(screenshot, LOOT_DARK_ROI)
            logger.debug("Loot preview — Gold:{} Elixir:{} DE:{}", gold, elixir, dark)
            return ResourceReading(gold=gold, elixir=elixir, dark_elixir=dark, valid=True)
        except Exception as e:
            logger.warning("OCR read_loot_preview failed: {}", e)
            return ResourceReading(valid=False)

    def read_text(self, screenshot: np.ndarray, roi: tuple[int, int, int, int]) -> str:
        """Read arbitrary text from an ROI."""
        cropped = self._crop(screenshot, roi)
        processed = self._preprocess(cropped)
        pil_img = Image.fromarray(processed)
        text = pytesseract.image_to_string(pil_img, config="--psm 7").strip()
        return text

    # ── Internals ─────────────────────────────────────────────────────────────

    def _crop(self, img: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = roi
        return img[y : y + h, x : x + w]

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """
        Pre-process a crop for better OCR accuracy.
        1. Convert to grayscale
        2. Upscale ×2 (Tesseract works better at larger sizes)
        3. Binary threshold
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Upscale ×2
        h, w = gray.shape
        scaled = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        # Threshold — CoC resource numbers are typically white on dark background
        _, thresh = cv2.threshold(scaled, 150, 255, cv2.THRESH_BINARY)
        return thresh

    def _parse_number(self, text: str) -> int:
        """
        Extract an integer from OCR text.
        Handles commas (1,234,567 → 1234567).
        """
        text = text.replace(",", "").strip()
        match = re.search(r"\d+", text)
        if match:
            return int(match.group())
        return 0

    def _read_number(self, screenshot: np.ndarray, roi: tuple[int, int, int, int]) -> int:
        cropped = self._crop(screenshot, roi)
        processed = self._preprocess(cropped)
        pil_img = Image.fromarray(processed)
        raw = pytesseract.image_to_string(pil_img, config=self._digits_config).strip()
        value = self._parse_number(raw)
        return value
