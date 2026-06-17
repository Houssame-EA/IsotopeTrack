# -*- coding: utf-8 -*-
"""Equivalence tests for processing/detection_registry.py.

The registry replaced the ``if/elif`` method dispatch that used to live in
``processing/peak_detection.py`` (``_calculate_single_threshold``,
``_cached_threshold_calculation`` and ``_calculate_array_threshold``).

These tests transcribe the *original* branch logic as reference functions and
assert the registry produces byte-identical results for every method name and a
grid of inputs — including the subtle per-call-site sigma differences
(``CPLN table`` uses the caller's sigma in one path and a fixed 0.55 in the
cached path; the analytic method is always 0.55). The detection engine itself
(numba/scipy) is mocked, so this runs without those dependencies.
"""
import numpy as np
import pytest

from processing import detection_registry as reg


# ── A fake detection engine ───────────────────────────────────────────────────
class _FakeThresholdEngine:
    """Returns a deterministic value that encodes its (lam, alpha, sigma) inputs
    so any wrong routing or wrong sigma is detected by an inequality."""
    def __init__(self, base):
        self.base = base

    def get_threshold(self, lam, alpha, sigma=0.55):
        return self.base + lam * 7.0 + alpha * 13.0 + sigma * 101.0


class _FakeEngine:
    def __init__(self):
        self.compound_poisson_lognormal = _FakeThresholdEngine(1000.0)      # analytic
        self.compound_poisson_lognormal_lut = _FakeThresholdEngine(5000.0)  # table


# ── Reference transcriptions of the ORIGINAL peak_detection branches ──────────
def ref_single(engine, lam, method, alpha, sigma):
    if method == "CPLN table":
        return engine.compound_poisson_lognormal_lut.get_threshold(lam, alpha, sigma)
    elif method == "Compound Poisson LogNormal":
        return engine.compound_poisson_lognormal.get_threshold(lam, alpha, sigma=0.55)
    else:
        return lam + 3.0 * np.sqrt(lam)


def ref_cached(engine, lam, method, alpha):
    if method == "CPLN table":
        return engine.compound_poisson_lognormal_lut.get_threshold(lam, alpha, sigma=0.55)
    elif method == "Compound Poisson LogNormal":
        return engine.compound_poisson_lognormal.get_threshold(lam, alpha, sigma=0.55)
    else:
        return lam + 3.0 * np.sqrt(lam)


def ref_array(engine, lam_arr, method, alpha, sigma):
    if method == "Manual":
        return ref_single(engine, lam_arr, "Manual", alpha, sigma)
    elif method in ["Compound Poisson LogNormal", "CPLN table"]:
        min_bg = np.min(lam_arr)
        max_bg = np.max(lam_arr)
        if min_bg == max_bg:
            single_thresh = ref_single(engine, min_bg, method, alpha, sigma)
            return np.full_like(lam_arr, single_thresh)
        n_eval = min(30, max(5, int((max_bg - min_bg) / 0.5)))
        eval_bg = np.linspace(min_bg, max_bg, n_eval)
        eval_thresh = np.array([
            ref_single(engine, bg, method, alpha, sigma) for bg in eval_bg
        ])
        return np.interp(lam_arr, eval_bg, eval_thresh)
    else:
        return lam_arr + 3.0 * np.sqrt(np.maximum(lam_arr, 1))


METHODS = ["Manual", "Compound Poisson LogNormal", "CPLN table", "Totally Unknown"]
LAMBDAS = [0.0, 0.5, 1.0, 4.0, 25.0, 123.4]
ALPHAS = [0.01, 0.05]
SIGMAS = [0.55, 0.9]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("lam", LAMBDAS)
@pytest.mark.parametrize("alpha", ALPHAS)
@pytest.mark.parametrize("sigma", SIGMAS)
def test_single_threshold_matches_original(method, lam, alpha, sigma):
    eng = _FakeEngine()
    expected = ref_single(eng, lam, method, alpha, sigma)
    got = reg.get(method).single_threshold(eng, lam, alpha, sigma)
    assert got == expected


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("lam", LAMBDAS)
@pytest.mark.parametrize("alpha", ALPHAS)
def test_cached_path_matches_original(method, lam, alpha):
    # The cached path always evaluates with sigma = 0.55.
    eng = _FakeEngine()
    expected = ref_cached(eng, lam, method, alpha)
    got = reg.get(method).single_threshold(eng, lam, alpha, 0.55)
    assert got == expected


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("alpha", ALPHAS)
@pytest.mark.parametrize("sigma", SIGMAS)
def test_array_threshold_matches_original(method, alpha, sigma):
    eng = _FakeEngine()
    for lam_arr in [
        np.array([2.0, 2.0, 2.0]),          # min == max short-circuit
        np.array([0.0, 1.0, 5.0, 25.0]),
        np.linspace(0.3, 80.0, 50),
    ]:
        expected = ref_array(eng, lam_arr, method, alpha, sigma)
        got = reg.get(method).array_threshold(eng, lam_arr, alpha, sigma)
        np.testing.assert_array_equal(got, expected)


def test_unknown_method_falls_back_to_poisson():
    eng = _FakeEngine()
    assert reg.get("nope").id == reg.DEFAULT_METHOD_ID
    assert reg.get("nope").single_threshold(eng, 9.0, 0.05, 0.55) == 9.0 + 3.0 * np.sqrt(9.0)


def test_manual_flag_only_on_manual():
    assert reg.get("Manual").is_manual is True
    for other in ["Compound Poisson LogNormal", "CPLN table", "Poisson", "unknown"]:
        assert reg.get(other).is_manual is False


def test_selectable_labels_unchanged():
    # The UI dropdown must still offer exactly these, in this order.
    assert reg.selectable_labels() == ["Manual", "Compound Poisson LogNormal", "CPLN table"]
