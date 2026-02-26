"""Tests for game resources."""

from __future__ import annotations

import pytest

from cocbot.game.resources import Resources


def test_meets_threshold_all_pass():
    r = Resources(gold=500_000, elixir=500_000, dark_elixir=2_000)
    assert r.meets_threshold(200_000, 200_000, 1_000) is True


def test_meets_threshold_gold_fails():
    r = Resources(gold=100_000, elixir=500_000, dark_elixir=2_000)
    assert r.meets_threshold(200_000, 200_000, 1_000) is False


def test_meets_threshold_dark_fails():
    r = Resources(gold=300_000, elixir=300_000, dark_elixir=500)
    assert r.meets_threshold(200_000, 200_000, 1_000) is False


def test_total_value_weighting():
    r = Resources(gold=100_000, elixir=100_000, dark_elixir=1_000)
    # Default weights: gold×1 + elixir×1 + de×5 = 200,000 + 5,000 = 205,000
    assert r.total_value() == pytest.approx(205_000.0)


def test_str_format():
    r = Resources(gold=1_234_567, elixir=890_000, dark_elixir=3_456)
    s = str(r)
    assert "1,234,567" in s
    assert "890,000" in s
    assert "3,456" in s
