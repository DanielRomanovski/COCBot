"""Tests for utility functions."""

from __future__ import annotations

import pytest

from cocbot.utils.delays import jitter, jitter_point


def test_jitter_within_range():
    for _ in range(100):
        result = jitter(100.0, pct=0.10)
        assert 90.0 <= result <= 110.0, f"Jitter out of range: {result}"


def test_jitter_point_within_radius():
    for _ in range(100):
        x, y = jitter_point(500, 500, radius=10)
        assert 490 <= x <= 510, f"x out of range: {x}"
        assert 490 <= y <= 510, f"y out of range: {y}"


def test_jitter_zero_pct():
    result = jitter(100.0, pct=0.0)
    assert result == 100.0
