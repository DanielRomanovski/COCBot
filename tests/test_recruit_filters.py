"""Tests for RecruitFilters logic (no device or API needed)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cocbot.tasks.recruit import RecruitFilters, RecruitTask


def _make_player(**kwargs) -> MagicMock:
    """Create a mock coc.Player object with sensible defaults."""
    defaults = dict(
        tag="#TESTPLAYER",
        name="TestPlayer",
        town_hall=12,
        donations=600,
        trophies=2000,
        war_stars=200,
        attack_wins=600,
        league=SimpleNamespace(name="Gold League I"),
    )
    defaults.update(kwargs)
    p = MagicMock()
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


# ── Filter pass/fail tests ────────────────────────────────────────────────────

def test_filter_passes_good_player():
    f = RecruitFilters()
    player = _make_player()
    passed, reason = f.check(player)
    assert passed is True
    assert reason == ""


def test_filter_rejects_low_th():
    f = RecruitFilters(min_th_level=12)
    player = _make_player(town_hall=9)
    passed, reason = f.check(player)
    assert passed is False
    assert "TH9" in reason


def test_filter_rejects_high_th():
    f = RecruitFilters(max_th_level=13)
    player = _make_player(town_hall=16)
    passed, reason = f.check(player)
    assert passed is False
    assert "TH16" in reason


def test_filter_rejects_low_donations():
    f = RecruitFilters(min_donations_per_season=1000)
    player = _make_player(donations=200)
    passed, reason = f.check(player)
    assert passed is False
    assert "donations" in reason


def test_filter_rejects_low_trophies():
    f = RecruitFilters(min_trophies=3000)
    player = _make_player(trophies=1200)
    passed, reason = f.check(player)
    assert passed is False
    assert "trophies" in reason


def test_filter_rejects_low_war_stars():
    f = RecruitFilters(min_war_stars=500)
    player = _make_player(war_stars=50)
    passed, reason = f.check(player)
    assert passed is False
    assert "war stars" in reason


def test_filter_rejects_low_attack_wins():
    f = RecruitFilters(min_attack_wins=1000)
    player = _make_player(attack_wins=100)
    passed, reason = f.check(player)
    assert passed is False
    assert "attack wins" in reason


def test_filter_rejects_wrong_league():
    f = RecruitFilters(required_league="Crystal League I")
    player = _make_player()  # league = "Gold League I"
    passed, reason = f.check(player)
    assert passed is False
    assert "league" in reason


def test_filter_passes_correct_league():
    f = RecruitFilters(required_league="Gold League I")
    player = _make_player()
    passed, reason = f.check(player)
    assert passed is True


def test_filter_rejects_excluded_tag():
    f = RecruitFilters(excluded_tags={"#TESTPLAYER"})
    player = _make_player(tag="#TESTPLAYER")
    passed, reason = f.check(player)
    assert passed is False
    assert "excluded" in reason


def test_filter_no_league_requirement_skips_league_check():
    f = RecruitFilters(required_league=None)
    player = _make_player(league=SimpleNamespace(name="Champion League I"))
    passed, reason = f.check(player)
    assert passed is True


# ── OCR tag parsing tests ─────────────────────────────────────────────────────

def test_ocr_tag_extraction():
    """RecruitTask._ocr_tag_from_card uses OCRReader.read_text — test the regex."""
    import re
    raw_outputs = [
        "#ABC123XY",       # clean
        " #ABC123XY ",     # with spaces
        "Tag: #ABC123XY",  # with prefix
        "#abc123xy",       # lowercase — should be uppercased
    ]
    pattern = r"#[0-9A-Z]{6,9}"
    for raw in raw_outputs:
        match = re.search(pattern, raw.upper())
        assert match is not None, f"Failed to extract tag from: {raw!r}"
        assert match.group().startswith("#")


def test_ocr_tag_extraction_fails_gracefully():
    import re
    bad_outputs = ["", "no tag here", "12345"]
    pattern = r"#[0-9A-Z]{6,9}"
    for raw in bad_outputs:
        match = re.search(pattern, raw.upper())
        assert match is None, f"Should not match: {raw!r}"
