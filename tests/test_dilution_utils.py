# -*- coding: utf-8 -*-
"""Tests for tools/dilution_utils.py.

Dilution factors scale every per-volume concentration the app reports, so the
coercion (`normalize_factor`) and the filename auto-detection
(`detect_dilution_from_name`) need to behave predictably. These functions are
pure; the module imports Qt only for the dialog it also defines.
"""
import pytest

from tools import dilution_utils as du


class TestNormalizeFactor:
    def test_passes_through_valid_float(self):
        assert du.normalize_factor(5) == 5.0
        assert du.normalize_factor(2.5) == 2.5

    def test_parses_numeric_strings(self):
        assert du.normalize_factor("3") == 3.0

    def test_clamps_below_minimum(self):
        assert du.normalize_factor(0.2) == 1.0          # default minimum 1.0
        assert du.normalize_factor(2, minimum=5) == 5.0

    def test_above_custom_minimum_passes(self):
        assert du.normalize_factor(10, minimum=5) == 10.0

    @pytest.mark.parametrize("bad", ["abc", None, object()])
    def test_invalid_falls_back_to_minimum(self, bad):
        assert du.normalize_factor(bad) == 1.0
        assert du.normalize_factor(bad, minimum=2.0) == 2.0


class TestDetectDilutionFromName:
    @pytest.mark.parametrize("name,expected", [
        ("sample_50x", 50.0),
        ("run-2.5x", 2.5),
        ("5x.csv", 5.0),
        ("AgNP_100x.h5", 100.0),
        ("sample_10x_20x", 20.0),     # last token wins
    ])
    def test_detects_valid_tokens(self, name, expected):
        assert du.detect_dilution_from_name(name) == expected

    @pytest.mark.parametrize("name", [
        "",
        None,
        "sample.csv",       # no token
        "Ag50",             # number but no 'x'
        "100xy",            # 'x' not at a token boundary
        "0.5x",             # below 1.0 -> rejected
    ])
    def test_returns_none_when_no_valid_token(self, name):
        assert du.detect_dilution_from_name(name) is None

    def test_strips_known_extensions_before_matching(self):
        assert du.detect_dilution_from_name("dust_25x.xlsx") == 25.0
