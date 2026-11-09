# -*- coding: utf-8 -*-
"""Tests for blind interference detection (utils/interference_detection.py).

The module finds the elements of a spectrum without being told the sample
composition, predicts their oxides and doubly charged ions, and uses the
peak position in a resolved spectrum to tell which species forms a peak.
These tests use a small synthetic periodic table so the expected answers
are exact.
"""
import numpy as np
import pytest

from utils import interference_detection as idet

ELEMENTS = [
    {"symbol": "La", "isotopes": [{"mass": 137.9071, "abundance": 0.09},
                                  {"mass": 138.9064, "abundance": 99.91}]},
    {"symbol": "Ce", "isotopes": [{"mass": 139.9054, "abundance": 88.45},
                                  {"mass": 141.9092, "abundance": 11.11}]},
    {"symbol": "Nd", "isotopes": [{"mass": 141.9077, "abundance": 27.2},
                                  {"mass": 142.9098, "abundance": 12.2},
                                  {"mass": 143.9101, "abundance": 23.8},
                                  {"mass": 144.9126, "abundance": 8.3},
                                  {"mass": 145.9131, "abundance": 17.2},
                                  {"mass": 147.9169, "abundance": 5.7},
                                  {"mass": 149.9209, "abundance": 5.6}]},
    {"symbol": "Gd", "isotopes": [{"mass": 153.9209, "abundance": 2.18},
                                  {"mass": 154.9226, "abundance": 14.8},
                                  {"mass": 155.9221, "abundance": 20.47},
                                  {"mass": 156.9240, "abundance": 15.65},
                                  {"mass": 157.9241, "abundance": 24.84},
                                  {"mass": 159.9271, "abundance": 21.86}]},
]
REFERENCE = {"default": {"MO": 0.02, "M2+": 0.0},
             "elements": {"La": {"MO": 0.07}, "Ce": {"MO": 0.07}, "Nd": {"MO": 0.04},
                          "Gd": {"MO": 0.05}}}
OFFSET = 0.025


def _spectrum(amounts, oxide=1.0):
    """Nominal-mass spectrum of elements with their oxides."""
    table = idet.isotope_table(ELEMENTS)
    out = {m: 0.0 for m in range(130, 180)}
    for s, amount in amounts.items():
        mo = REFERENCE["elements"][s]["MO"] * oxide
        for n, _mass, frac in table[s]:
            out[n] += amount * frac
            out[n + 16] += amount * frac * mo
    return out


def _resolved(amounts, oxide=1.0, sigma=0.008):
    """Resolved spectrum with Gaussian peaks shifted by the calibration offset."""
    table = idet.isotope_table(ELEMENTS)
    mz = np.arange(130.0, 180.0, 0.002)
    y = np.zeros_like(mz)
    for s, amount in amounts.items():
        mo = REFERENCE["elements"][s]["MO"] * oxide
        for _n, mass, frac in table[s]:
            for centre, height in ((mass, amount * frac), (mass + idet.OXYGEN, amount * frac * mo)):
                y += height * np.exp(-0.5 * ((mz - centre - OFFSET) / sigma) ** 2)
    return mz, y


class TestIdentify:
    def test_finds_only_the_elements_present(self):
        ident = idet.identify_elements(_spectrum({"La": 400.0, "Ce": 400.0}), ELEMENTS, REFERENCE)
        assert set(ident.amounts) == {"La", "Ce"}

    def test_amount_is_recovered(self):
        ident = idet.identify_elements(_spectrum({"La": 400.0}), ELEMENTS, REFERENCE)
        assert ident.amounts["La"] == pytest.approx(400.0, rel=0.02)

    def test_oxide_scale_is_fitted(self):
        ident = idet.identify_elements(_spectrum({"La": 400.0}, oxide=0.6), ELEMENTS, REFERENCE)
        assert ident.oxide_scale == pytest.approx(0.6)

    def test_empty_spectrum_returns_none(self):
        assert idet.identify_elements({}, ELEMENTS, REFERENCE) is None

    def test_few_ions_are_not_an_element(self):
        ident = idet.identify_elements(_spectrum({"La": 8.0}), ELEMENTS, REFERENCE)
        assert ident.amounts == {}

    def test_decision_does_not_depend_on_other_elements(self):
        weak = idet.identify_elements(_spectrum({"Gd": 300.0}), ELEMENTS, REFERENCE)
        with_strong = idet.identify_elements(_spectrum({"Gd": 300.0, "Ce": 300000.0}),
                                             ELEMENTS, REFERENCE)
        assert "Gd" in weak.amounts and "Gd" in with_strong.amounts


class TestBlank:
    def test_element_at_blank_level_is_background(self):
        sample = _spectrum({"La": 400.0, "Ce": 200.0})
        blank = _spectrum({"Ce": 200.0})
        ident = idet.identify_elements(sample, ELEMENTS, REFERENCE, blank=blank)
        assert set(ident.amounts) == {"La"}
        assert ident.background == ["Ce"]
        assert ident.blank_used

    def test_blank_is_scaled_to_the_sample_length(self):
        sample = _spectrum({"Ce": 400.0})
        blank = _spectrum({"Ce": 200.0})
        ident = idet.identify_elements(sample, ELEMENTS, REFERENCE, blank=blank, blank_scale=2.0)
        assert "Ce" not in ident.amounts and "Ce" in ident.background


class TestContributions:
    def test_lanthanum_oxide_explains_mass_155(self):
        ident = idet.identify_elements(_spectrum({"La": 400.0}), ELEMENTS, REFERENCE)
        parts = idet.contributions(ident, 155)
        assert parts[0][0] == "La" and parts[0][2] == "oxide"
        assert parts[0][3] == pytest.approx(1.0, abs=0.02)

    def test_isobaric_share_at_142(self):
        ident = idet.identify_elements(_spectrum({"Ce": 100.0, "Nd": 100.0}), ELEMENTS, REFERENCE)
        shares = {el: sh for el, _l, kind, sh in idet.contributions(ident, 142) if kind == "atom"}
        assert shares["Nd"] == pytest.approx(27.2 / (27.2 + 11.11), abs=0.02)


class TestPosition:
    def test_offset_is_measured_on_clean_peaks(self):
        amounts = {"Ce": 300.0, "Nd": 300.0, "Gd": 300.0}
        ident = idet.identify_elements(_spectrum(amounts), ELEMENTS, REFERENCE)
        mz, y = _resolved(amounts)
        offset = idet.mass_offset(mz, y, ident, idet.isotope_table(ELEMENTS), min_ions=0)
        assert offset == pytest.approx(OFFSET, abs=0.002)

    def test_peak_position_points_to_the_oxide(self):
        table = idet.isotope_table(ELEMENTS)
        mz, y = _resolved({"La": 400.0})
        centre, _ions = idet.peak_centre(mz, y, 154.9226 + OFFSET)
        ranked = idet.position_match(centre, OFFSET, idet.candidate_species(155, table, ["La"]))
        assert ranked[0][0] == "¹³⁹La¹⁶O⁺"
        assert abs(ranked[0][1]) < 0.002


class TestCheckIsotope:
    def test_gadolinium_peak_made_of_lanthanum_oxide(self):
        ident = idet.identify_elements(_spectrum({"La": 400.0, "Ce": 400.0, "Nd": 200.0}),
                                       ELEMENTS, REFERENCE)
        result = idet.check_isotope("Gd", 154.9226, ident, ELEMENTS)
        assert result["severity"] == "major"
        assert "La" in result["verdict"]

    def test_clean_isotope(self):
        ident = idet.identify_elements(_spectrum({"Gd": 400.0}), ELEMENTS, REFERENCE)
        result = idet.check_isotope("Gd", 154.9226, ident, ELEMENTS)
        assert result["severity"] == "clean"

    def test_no_identification(self):
        assert idet.check_isotope("Gd", 154.9226, None, ELEMENTS)["severity"] == "unknown"

    def test_nothing_above_detection_limit(self):
        ident = idet.identify_elements(_spectrum({"La": 8.0}), ELEMENTS, REFERENCE)
        result = idet.check_isotope("La", 138.9064, ident, ELEMENTS)
        assert result["verdict"] == "No element above detection limit"

    def test_background_isotope(self):
        ident = idet.identify_elements(_spectrum({"La": 400.0, "Ce": 200.0}), ELEMENTS, REFERENCE,
                                       blank=_spectrum({"Ce": 200.0}))
        result = idet.check_isotope("Ce", 139.9054, ident, ELEMENTS)
        assert "same as blank" in result["verdict"]
