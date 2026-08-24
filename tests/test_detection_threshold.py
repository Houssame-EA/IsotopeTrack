# -*- coding: utf-8 -*-
"""Tests for the detection-threshold machinery in processing/peak_detection.py.

`get_threshold` turns a background level into the count above which a signal is
called a "particle" — it is the single most consequential number in the whole
pipeline. `_assignments_to_regions` then turns clustered points into the
particle index ranges that get integrated. Both are tested here.
"""
import numpy as np
import pytest

from processing.peak_detection import (
    CompoundPoissonLognormal,
    CompoundPoissonLognormalOptimized,
    _assignments_to_regions,
)


# --------------------------------------------------------------------------- #
# CompoundPoissonLognormal.get_threshold
# --------------------------------------------------------------------------- #
class TestGetThreshold:
    def setup_method(self):
        self.cpln = CompoundPoissonLognormal()

    def test_zero_or_negative_lambda_returns_zero(self):
        assert self.cpln.get_threshold(0.0, 0.05) == 0.0
        assert self.cpln.get_threshold(-5.0, 0.05) == 0.0

    def test_positive_lambda_gives_finite_positive_threshold(self):
        thr = self.cpln.get_threshold(10.0, 0.05)
        assert np.isfinite(thr)
        assert thr > 0.0

    def test_threshold_exceeds_background_mean(self):
        # A detection threshold must sit above the background it is screening.
        lam = 20.0
        assert self.cpln.get_threshold(lam, 0.05) > lam

    def test_higher_confidence_raises_threshold(self):
        # Smaller alpha = higher confidence = stricter (higher) threshold.
        lenient = self.cpln.get_threshold(10.0, 0.05)
        strict = self.cpln.get_threshold(10.0, 0.001)
        assert strict >= lenient


# --------------------------------------------------------------------------- #
# CompoundPoissonLognormalOptimized — same answers, plus caching
# --------------------------------------------------------------------------- #
class TestOptimizedThreshold:
    def setup_method(self):
        self.opt = CompoundPoissonLognormalOptimized()

    def test_agrees_with_reference(self):
        ref = CompoundPoissonLognormal().get_threshold(15.0, 0.05)
        fast = self.opt.get_threshold(15.0, 0.05)
        assert fast == pytest.approx(ref, rel=0.05)

    def test_zero_lambda_returns_zero(self):
        assert self.opt.get_threshold(0.0, 0.05) == 0.0

    def test_cache_returns_identical_value(self):
        a = self.opt.get_threshold(12.0, 0.05)
        b = self.opt.get_threshold(12.0, 0.05)
        assert a == b
        assert (round(12.0, 2), 0.05, 0.55) in self.opt._threshold_cache

    def test_clear_cache(self):
        self.opt.get_threshold(12.0, 0.05)
        assert self.opt._threshold_cache
        self.opt.clear_cache()
        assert self.opt._threshold_cache == {}


# --------------------------------------------------------------------------- #
# _assignments_to_regions
# --------------------------------------------------------------------------- #
class TestAssignmentsToRegions:
    def test_two_contiguous_peaks(self):
        assignments = np.array([0, 0, 1, 1, 1])
        out = _assignments_to_regions(assignments, n_peaks=2, start_idx=10)
        assert out == [(10, 11), (12, 14)]   # start_idx offset applied

    def test_regions_sorted_by_start(self):
        # Peak 0 occupies the later indices; output must still be start-sorted.
        assignments = np.array([1, 1, 0, 0])
        out = _assignments_to_regions(assignments, n_peaks=2, start_idx=0)
        assert out == [(0, 1), (2, 3)]

    def test_empty_components_dropped(self):
        assignments = np.array([0, 0])
        out = _assignments_to_regions(assignments, n_peaks=3, start_idx=0)
        assert out == [(0, 1)]            # peaks 1 and 2 are empty -> dropped

    def test_single_point_region(self):
        assignments = np.array([0])
        out = _assignments_to_regions(assignments, n_peaks=1, start_idx=5)
        assert out == [(5, 5)]            # start == end is valid
