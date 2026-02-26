"""Tests for the vision/OCR number parser (no device needed)."""

from __future__ import annotations

from cocbot.vision.ocr import OCRReader


def test_parse_number_plain():
    ocr = OCRReader.__new__(OCRReader)
    assert ocr._parse_number("450000") == 450_000


def test_parse_number_commas():
    ocr = OCRReader.__new__(OCRReader)
    assert ocr._parse_number("1,234,567") == 1_234_567


def test_parse_number_garbage():
    ocr = OCRReader.__new__(OCRReader)
    # If OCR garbles it, should return 0 rather than crash
    assert ocr._parse_number("") == 0
    assert ocr._parse_number("abc") == 0


def test_parse_number_mixed():
    ocr = OCRReader.__new__(OCRReader)
    assert ocr._parse_number("  456,789  ") == 456_789
