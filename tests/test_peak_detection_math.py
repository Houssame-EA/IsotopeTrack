# -*- coding: utf-8 -*-
"""Tests for the statistical core in processing/peak_detection.py.

These cover the mathematical primitives that the Compound Poisson Log-Normal
detection threshold is built on. They are checked two ways:

  * against SciPy reference implementations (the functions are meant to agree
    with SciPy but be faster), and
  * against closed-form properties (inverses, known medians, monotonicity,
    non-negativity).

Detection thresholds decide which signal spikes become "particles", so a silent
change in any of these would change every reported particle count and size.
"""
import numpy as np
import pytest
from scipy import stats

from processing import peak_detection as pd


# --------------------------------------------------------------------------- #
# erf / erfinv
# --------------------------------------------------------------------------- #
class TestErf:
    def test_erf_known_values(self):
        assert pd.erf(0.0) == pytest.approx(0.0)
        assert pd.erf(50.0) == pytest.approx(1.0)
        assert pd.erf(-50.0) == pytest.approx(-1.0)

    def test_erf_erfinv_roundtrip(self):
        xs = np.array([-0.9, -0.3, 0.0, 0.25, 0.8])
        np.testing.assert_allclose(pd.erfinv(pd.erf(xs)), xs, atol=1e-10)


# --------------------------------------------------------------------------- #
# log-normal cdf / quantile
# --------------------------------------------------------------------------- #
class TestLogNormal:
    def test_cdf_matches_scipy(self):
        x = np.array([0.5, 1.0, 2.0, 5.0])
        mu, sigma = 0.3, 0.7
        np.testing.assert_allclose(
            pd.lognormal_cdf(x, mu, sigma),
            stats.lognorm.cdf(x, s=sigma, scale=np.exp(mu)),
        )

    def test_median_is_exp_mu(self):
        # The median of a log-normal is exp(mu) regardless of sigma.
        for mu in (-0.5, 0.0, 1.2):
            assert pd.lognormal_quantile(np.array([0.5]), mu, 0.9)[0] == pytest.approx(np.exp(mu))

    def test_cdf_quantile_are_inverses(self):
        mu, sigma = 0.1, 0.5
        q = np.array([0.05, 0.5, 0.95])
        x = pd.lognormal_quantile(q, mu, sigma)
        np.testing.assert_allclose(pd.lognormal_cdf(x, mu, sigma), q, atol=1e-9)


# --------------------------------------------------------------------------- #
# Poisson pmf
# --------------------------------------------------------------------------- #
class TestPoissonPdf:
    def test_matches_scipy_small_array(self):
        k = np.arange(0, 12)
        lam = 2.3
        np.testing.assert_allclose(pd.poisson_pdf(k, lam),
                                   stats.poisson.pmf(k, lam), atol=1e-12)

    def test_zero_count_is_exp_neg_lambda(self):
        np.testing.assert_allclose(pd.poisson_pdf(np.array([0]), 2.0), [np.exp(-2.0)])

    def test_pmf_sums_to_one_over_support(self):
        lam = 3.0
        k = np.arange(0, 40)
        assert pd.poisson_pdf(k, lam).sum() == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# zero-truncated Poisson quantile
# --------------------------------------------------------------------------- #
class TestZeroTruncQuantile:
    def test_formula(self):
        lam, y = 1.0, 1.0
        k0 = np.exp(-lam)
        expected = (y - k0) / (1.0 - k0)
        assert pd.zero_trunc_quantile(lam, y) == pytest.approx(expected)

    def test_at_k0_is_zero(self):
        lam = 2.0
        assert pd.zero_trunc_quantile(lam, np.exp(-lam)) == pytest.approx(0.0)

    def test_clamped_at_zero_below_k0(self):
        lam = 2.0
        assert pd.zero_trunc_quantile(lam, 0.0) == 0.0


# --------------------------------------------------------------------------- #
# sum of i.i.d. log-normals (Fenton-Wilkinson)
# --------------------------------------------------------------------------- #
class TestSumIidLognormals:
    def test_n_equals_one_is_identity(self):
        mu, sigma = 0.5, 0.3
        mu_x, sigma_x = pd.sum_iid_lognormals(1.0, mu, sigma)
        assert mu_x == pytest.approx(mu)
        assert sigma_x == pytest.approx(sigma)

    def test_fenton_wilkinson_formula(self):
        n, mu, sigma = 4.0, 0.0, 0.6
        sigma2_x = np.log((np.exp(sigma ** 2) - 1.0) / n + 1.0)
        exp_mu = np.log(n) + mu + 0.5 * (sigma ** 2 - sigma2_x)
        mu_x, sigma_x = pd.sum_iid_lognormals(n, mu, sigma)
        assert mu_x == pytest.approx(exp_mu)
        assert sigma_x == pytest.approx(np.sqrt(sigma2_x))

    def test_variance_decreases_with_n(self):
        # Aggregating more events makes the (log) distribution tighter.
        _, s1 = pd.sum_iid_lognormals(1.0, 0.0, 0.6)
        _, s10 = pd.sum_iid_lognormals(10.0, 0.0, 0.6)
        assert s10 < s1


# --------------------------------------------------------------------------- #
# standard normal quantile (Acklam approximation)
# --------------------------------------------------------------------------- #
class TestStandardQuantile:
    def test_median_is_zero(self):
        assert pd.standard_quantile(0.5) == pytest.approx(0.0)

    @pytest.mark.parametrize("p", [0.01, 0.1, 0.5, 0.84, 0.975, 0.999])
    def test_matches_scipy_scalar(self, p):
        assert pd.standard_quantile(p) == pytest.approx(stats.norm.ppf(p), abs=1e-4)

    def test_symmetry(self):
        assert pd.standard_quantile(0.9) == pytest.approx(-pd.standard_quantile(0.1), abs=1e-4)


# --------------------------------------------------------------------------- #
# compound Poisson log-normal quantile approximation
# --------------------------------------------------------------------------- #
class TestCompoundPoissonLognormalQuantile:
    def test_non_negative_and_finite(self):
        val = pd.compound_poisson_lognormal_quantile_approximation(0.99, 1.0, 0.0, 0.5)
        assert np.isfinite(val)
        assert val >= 0.0

    def test_monotonic_in_q(self):
        lam, mu, sigma = 1.5, 0.0, 0.5
        v_low = pd.compound_poisson_lognormal_quantile_approximation(0.90, lam, mu, sigma)
        v_high = pd.compound_poisson_lognormal_quantile_approximation(0.999, lam, mu, sigma)
        assert v_high >= v_low

    def test_fast_and_slow_agree(self):
        lam, mu, sigma = 1.0, 0.0, 0.5
        slow = pd.compound_poisson_lognormal_quantile_approximation(0.99, lam, mu, sigma)
        fast = pd.compound_poisson_lognormal_quantile_approximation_fast(0.99, lam, mu, sigma)
        # Different grid resolutions (10000 vs 2000 points) -> close, not equal.
        assert fast == pytest.approx(slow, rel=0.05)
