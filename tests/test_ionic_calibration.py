# -*- coding: utf-8 -*-
"""Tests for the ionic calibration regression in calibration_methods/ionic_CAL.py.

The app fits three calibration models per isotope — force-through-zero, ordinary
least squares ("simple"), and weighted least squares — and auto-selects the one
with the highest R². Those fits convert raw counts to mass, so a wrong slope or
R² silently miscalibrates everything downstream.

The fit routines (`_fit_zero`, `_fit_simple`, `_fit_weighted`,
`_compute_figures_of_merit`) are pure numerics that happen to live on the
calibration window. To test them without constructing the GUI, we borrow the
unbound methods onto a tiny proxy object — no QMainWindow is created.
"""
import numpy as np
import pytest

from calibration_methods.ionic_CAL import IonicCalibrationWindow


class _Fitter:
    """Hosts the pure fit methods so they can be called without the GUI."""
    _fit_zero = IonicCalibrationWindow._fit_zero
    _fit_simple = IonicCalibrationWindow._fit_simple
    _fit_weighted = IonicCalibrationWindow._fit_weighted
    _compute_figures_of_merit = IonicCalibrationWindow._compute_figures_of_merit


@pytest.fixture
def fit():
    return _Fitter()


# --------------------------------------------------------------------------- #
# Force-through-zero
# --------------------------------------------------------------------------- #
class TestFitZero:
    def test_perfect_proportional_line(self, fit):
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = 4.0 * x                       # y = 4x, no intercept
        res = fit._fit_zero(x, y)
        assert res["slope"] == pytest.approx(4.0)
        assert res["intercept"] == 0.0
        assert res["r_squared"] == pytest.approx(1.0)

    def test_intercept_is_always_zero(self, fit):
        x = np.array([1.0, 2.0, 3.0])
        y = 2.0 * x + 5.0                 # real intercept, but model forces 0
        res = fit._fit_zero(x, y)
        assert res["intercept"] == 0.0
        assert res["r_squared"] < 1.0    # can't fit the offset perfectly


# --------------------------------------------------------------------------- #
# Ordinary least squares
# --------------------------------------------------------------------------- #
class TestFitSimple:
    def test_recovers_slope_and_intercept(self, fit):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = 3.0 * x + 2.0
        res = fit._fit_simple(x, y)
        assert res["slope"] == pytest.approx(3.0)
        assert res["intercept"] == pytest.approx(2.0)
        assert res["r_squared"] == pytest.approx(1.0)

    def test_r_squared_drops_with_noise(self, fit):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([3.1, 5.9, 9.2, 11.8, 15.1])   # ~3x+0 with scatter
        res = fit._fit_simple(x, y)
        assert 0.99 < res["r_squared"] <= 1.0


# --------------------------------------------------------------------------- #
# Weighted least squares
# --------------------------------------------------------------------------- #
class TestFitWeighted:
    def test_equal_weights_match_ols(self, fit):
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = 2.0 * x + 1.0
        y_std = np.ones_like(y)
        res = fit._fit_weighted(x, y, y_std)
        assert res["slope"] == pytest.approx(2.0)
        assert res["intercept"] == pytest.approx(1.0)
        assert res["r_squared"] == pytest.approx(1.0)

    def test_downweights_noisy_point(self, fit):
        # One point is far off the line but given huge uncertainty, so the
        # weighted fit should stay close to the clean slope of 2.
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = np.array([2.0, 4.0, 6.0, 50.0])         # last point is an outlier
        y_std = np.array([0.1, 0.1, 0.1, 100.0])    # ...but very uncertain
        res = fit._fit_weighted(x, y, y_std)
        assert res["slope"] == pytest.approx(2.0, abs=0.2)


# --------------------------------------------------------------------------- #
# Figures of merit (LOD / LOQ / BEC)
# --------------------------------------------------------------------------- #
class TestFiguresOfMerit:
    def test_iupac_formulas(self, fit):
        res = fit._compute_figures_of_merit(slope=2.0, intercept=4.0, sigma_blank=1.0)
        assert res["lod"] == pytest.approx(3.0 * 1.0 / 2.0)    # 1.5
        assert res["loq"] == pytest.approx(10.0 * 1.0 / 2.0)   # 5.0
        assert res["bec"] == pytest.approx(4.0 / 2.0)          # 2.0

    def test_zero_slope_returns_nan(self, fit):
        res = fit._compute_figures_of_merit(slope=0.0, intercept=1.0, sigma_blank=1.0)
        assert np.isnan(res["lod"]) and np.isnan(res["loq"]) and np.isnan(res["bec"])


# --------------------------------------------------------------------------- #
# Model selection (auto "best R²")
# --------------------------------------------------------------------------- #
class TestModelSelection:
    def test_best_r2_picks_model_with_intercept(self, fit):
        # Data with a genuine intercept: OLS should fit better than force-zero.
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = 3.0 * x + 10.0
        r2 = {
            "zero": fit._fit_zero(x, y)["r_squared"],
            "simple": fit._fit_simple(x, y)["r_squared"],
        }
        assert r2["simple"] > r2["zero"]
        # This is the same selection rule the window uses (max by R²).
        assert max(r2, key=r2.get) == "simple"
