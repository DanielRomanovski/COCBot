"""
Vision: Template Matching
=========================
Uses OpenCV to find UI elements (buttons, icons) on the screen by comparing
against reference template images stored in assets/templates/.

Template images should be cropped screenshots of the UI element you want to
find, saved as PNG files.

Directory layout
----------------
assets/
  templates/
    attack_button.png
    next_button.png
    collect_gold.png
    collect_elixir.png
    home_village.png
    ... etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from loguru import logger


TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "templates"


@dataclass
class MatchResult:
    found: bool
    x: int  # Centre x of the best match
    y: int  # Centre y of the best match
    confidence: float  # 0.0 – 1.0

    @property
    def centre(self) -> tuple[int, int]:
        return self.x, self.y


class TemplateMatcher:
    """
    Loads template images from disk and performs cv2.matchTemplate searches.

    Usage
    -----
    matcher = TemplateMatcher()
    result = matcher.find(screenshot, "attack_button")
    if result.found:
        input_ctrl.tap(*result.centre)
    """

    def __init__(
        self,
        templates_dir: Path = TEMPLATES_DIR,
        default_threshold: float = 0.80,
    ) -> None:
        self.templates_dir = templates_dir
        self.default_threshold = default_threshold
        self._cache: dict[str, np.ndarray] = {}

    def _load_template(self, name: str) -> np.ndarray:
        """Load (and cache) a template image by name (without extension)."""
        if name in self._cache:
            return self._cache[name]

        # Try common extensions
        for ext in (".png", ".jpg", ".jpeg"):
            path = self.templates_dir / f"{name}{ext}"
            if path.exists():
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError(f"Failed to read template image: {path}")
                self._cache[name] = img
                logger.debug("Loaded template '{}' from {}", name, path)
                return img

        raise FileNotFoundError(
            f"Template '{name}' not found in {self.templates_dir}. "
            f"Add a PNG screenshot of the UI element there."
        )

    def find(
        self,
        screenshot: np.ndarray,
        template_name: str,
        threshold: float | None = None,
        scale_range: tuple[float, float] | None = None,
    ) -> MatchResult:
        """
        Search for template_name in the screenshot.

        Parameters
        ----------
        screenshot : np.ndarray
            BGR screenshot (from ADBDevice.screenshot()).
        template_name : str
            File name without extension inside assets/templates/.
        threshold : float, optional
            Confidence threshold (0–1). Defaults to self.default_threshold.
        scale_range : tuple[float, float], optional
            If provided, tries multiple scales and returns the best match.
            E.g. (0.8, 1.2) tests 5 scale levels between 80% and 120%.

        Returns
        -------
        MatchResult
        """
        thresh = threshold if threshold is not None else self.default_threshold
        template = self._load_template(template_name)

        if scale_range:
            return self._find_multiscale(screenshot, template, thresh, scale_range)
        return self._find_single(screenshot, template, thresh)

    def _find_single(
        self,
        screenshot: np.ndarray,
        template: np.ndarray,
        threshold: float,
    ) -> MatchResult:
        th, tw = template.shape[:2]
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        found = max_val >= threshold
        cx = max_loc[0] + tw // 2
        cy = max_loc[1] + th // 2

        if found:
            logger.debug("Template match found: conf={:.3f} at ({}, {})", max_val, cx, cy)
        else:
            logger.debug("Template not found: best_conf={:.3f} (threshold={})", max_val, threshold)

        return MatchResult(found=found, x=cx, y=cy, confidence=max_val)

    def _find_multiscale(
        self,
        screenshot: np.ndarray,
        template: np.ndarray,
        threshold: float,
        scale_range: tuple[float, float],
        n_scales: int = 7,
    ) -> MatchResult:
        """Try multiple scales and return the best match across all of them."""
        best = MatchResult(found=False, x=0, y=0, confidence=0.0)
        scales = np.linspace(scale_range[0], scale_range[1], n_scales)

        for scale in scales:
            th = int(template.shape[0] * scale)
            tw = int(template.shape[1] * scale)
            if th < 10 or tw < 10:
                continue
            resized = cv2.resize(template, (tw, th))
            result = cv2.matchTemplate(screenshot, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best.confidence:
                cx = max_loc[0] + tw // 2
                cy = max_loc[1] + th // 2
                best = MatchResult(
                    found=max_val >= threshold,
                    x=cx,
                    y=cy,
                    confidence=max_val,
                )

        return best

    def find_all(
        self,
        screenshot: np.ndarray,
        template_name: str,
        threshold: float | None = None,
    ) -> list[MatchResult]:
        """
        Find ALL occurrences of a template (e.g. multiple resource icons).
        Returns a list of MatchResults, sorted by confidence descending.
        """
        thresh = threshold if threshold is not None else self.default_threshold
        template = self._load_template(template_name)
        th, tw = template.shape[:2]

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        locs = np.where(result >= thresh)

        matches: list[MatchResult] = []
        for pt in zip(*locs[::-1]):  # (x, y) pairs
            cx = pt[0] + tw // 2
            cy = pt[1] + th // 2
            conf = result[pt[1], pt[0]]
            matches.append(MatchResult(found=True, x=cx, y=cy, confidence=conf))

        # Non-max suppression: remove overlapping detections
        matches = self._nms(matches, min_dist=tw // 2)
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches

    @staticmethod
    def _nms(matches: list[MatchResult], min_dist: int = 30) -> list[MatchResult]:
        """Simple greedy non-maximum suppression by distance."""
        kept: list[MatchResult] = []
        for m in sorted(matches, key=lambda x: x.confidence, reverse=True):
            if all(
                abs(m.x - k.x) > min_dist or abs(m.y - k.y) > min_dist
                for k in kept
            ):
                kept.append(m)
        return kept
