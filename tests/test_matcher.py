"""Tests for template matching (uses a synthetic test image — no device needed)."""

from __future__ import annotations

import numpy as np
import pytest

from cocbot.vision.matcher import MatchResult, TemplateMatcher


def _make_image_with_patch(
    img_size: tuple[int, int],
    patch_colour: tuple[int, int, int],
    patch_pos: tuple[int, int],
    patch_size: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Create a test image and a template patch embedded in it."""
    h, w = img_size
    img = np.zeros((h, w, 3), dtype=np.uint8)
    ph, pw = patch_size
    py, px = patch_pos
    img[py : py + ph, px : px + pw] = patch_colour

    template = np.zeros((ph, pw, 3), dtype=np.uint8)
    template[:, :] = patch_colour
    return img, template


def test_nms_removes_nearby_duplicates():
    matches = [
        MatchResult(found=True, x=100, y=100, confidence=0.9),
        MatchResult(found=True, x=105, y=102, confidence=0.85),  # very close — should be removed
        MatchResult(found=True, x=300, y=300, confidence=0.88),  # far away — should be kept
    ]
    result = TemplateMatcher._nms(matches, min_dist=20)
    assert len(result) == 2
    xs = {m.x for m in result}
    assert 100 in xs
    assert 300 in xs
