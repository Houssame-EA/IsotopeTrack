# -*- coding: utf-8 -*-
"""Tests for the calibration fits in calibration_methods/te_common.py.

The app fits three calibration models per isotope — force-through-zero, ordinary
least squares ("simple"), and weighted least squares — and auto-selects the one
with the highest R². Those fits convert raw counts to mass, so a wrong slope or
R² silently miscalibrates everything downstream.

The fits used to be private methods on ``IonicCalibrationWindow`` and were
borrowed onto a proxy object here so they could run without the GUI. They are
now module-level functions in ``te_common`` shared by every calibration window,
so they are imported and called directly.
"""
import numpy as np
import pytest

from calibration_methods.te_common import (
    compute_figures_of_merit,
    fit_simple,
    fit_weighted,
    fit_zero,
)


class TestFitZero:
    """Force-through-zero regression, the app's default method."""

    def test_perfect_proportional_line(self):
        """A clean y = 4x must recover the slope exactly, with R² of 1."""
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = 4.0 * x
        res = fit_zero(x, y)
        assert res["slope"] == pytest.approx(4.0)
        assert res["intercept"] == 0.0
        assert res["r_squared"] == pytest.approx(1.0)

    def test_intercept_is_always_zero(self):
        """Data with a real offset still gets intercept 0, and R² below 1.

        The model cannot represent the offset, which is the whole point of the
        method, so the fit must degrade rather than silently absorb it.
        """
        x = np.array([1.0, 2.0, 3.0])
        y = 2.0 * x + 5.0
        res = fit_zero(x, y)
        assert res["intercept"] == 0.0
        assert res["r_squared"] < 1.0


class TestFitSimple:
    """Ordinary least squares."""

    def test_recovers_slope_and_intercept(self):
        """A clean y = 3x + 2 must recover both parameters exactly."""
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = 3.0 * x + 2.0
        res = fit_simple(x, y)
        assert res["slope"] == pytest.approx(3.0)
        assert res["intercept"] == pytest.approx(2.0)
        assert res["r_squared"] == pytest.approx(1.0)

    def test_r_squared_drops_with_noise(self):
        """Scatter around y = 3x must lower R² without collapsing the fit."""
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([3.1, 5.9, 9.2, 11.8, 15.1])
        res = fit_simple(x, y)
        assert 0.99 < res["r_squared"] <= 1.0


class TestFitWeighted:
    """Weighted least squares, where 1/σ² sets each point's influence."""

    def test_equal_weights_match_ols(self):
        """Uniform uncertainties must reduce the weighted fit to plain OLS."""
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = 2.0 * x + 1.0
        y_std = np.ones_like(y)
        res = fit_weighted(x, y, y_std)
        assert res["slope"] == pytest.approx(2.0)
        assert res["intercept"] == pytest.approx(1.0)
        assert res["r_squared"] == pytest.approx(1.0)

    def test_downweights_noisy_point(self):
        """An outlier carrying a huge σ must barely move the slope.

        The last point sits far off the line of slope 2 but is declared very
        uncertain, so the fit should stay near 2 rather than chase it.
        """
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = np.array([2.0, 4.0, 6.0, 50.0])
        y_std = np.array([0.1, 0.1, 0.1, 100.0])
        res = fit_weighted(x, y, y_std)
        assert res["slope"] == pytest.approx(2.0, abs=0.2)


class TestFiguresOfMerit:
    """LOD, LOQ and BEC derived from a fit."""

    def test_iupac_formulas(self):
        """Values must follow the IUPAC 3σ/10σ and intercept-over-slope rules."""
        res = compute_figures_of_merit(slope=2.0, intercept=4.0, sigma_blank=1.0)
        assert res["lod"] == pytest.approx(3.0 * 1.0 / 2.0)
        assert res["loq"] == pytest.approx(10.0 * 1.0 / 2.0)
        assert res["bec"] == pytest.approx(4.0 / 2.0)

    def test_zero_slope_returns_nan(self):
        """A zero slope must yield NaN rather than divide by zero."""
        res = compute_figures_of_merit(slope=0.0, intercept=1.0, sigma_blank=1.0)
        assert np.isnan(res["lod"]) and np.isnan(res["loq"]) and np.isnan(res["bec"])


class TestModelSelection:
    """The auto-selection rule the calibration window applies."""

    def test_best_r2_picks_model_with_intercept(self):
        """Data with a genuine offset must rank OLS above force-through-zero.

        The window selects by max R², so this is the same comparison it makes.
        """
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = 3.0 * x + 10.0
        r2 = {
            "zero": fit_zero(x, y)["r_squared"],
            "simple": fit_simple(x, y)["r_squared"],
        }
        assert r2["simple"] > r2["zero"]
        assert max(r2, key=r2.get) == "simple"
