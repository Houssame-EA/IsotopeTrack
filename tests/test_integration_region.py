"""Tests for where a particle region starts and ends for each integration method."""

from __future__ import annotations

import numpy as np
import pytest

from processing.peak_detection import PeakDetection

BACKGROUND = 400.0
THRESHOLD = 800.0
MIDPOINT = 600.0


@pytest.fixture(scope="module")
def engine():
    """Return one detection engine for the module."""
    return PeakDetection()


def signal_with_side_bump(n: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """Return time and a signal with one particle followed by a bump under the threshold.

    The signal stays above the background between the particle and the bump,
    and drops below the background elsewhere.
    """
    y = np.full(n, 300.0)
    y[990:1030] = 450.0
    y[1000:1004] = [1000.0, 2400.0, 1700.0, 900.0]
    y[1015:1018] = [700.0, 750.0, 700.0]
    return np.arange(n) * 1e-4, y


def detect(engine, method, vectorized=False):
    """Return the particles found with one integration method."""
    time, y = signal_with_side_bump()
    finder = engine.find_particles_vectorized if vectorized else engine.find_particles_safe
    return finder(time, y, BACKGROUND, THRESHOLD, min_continuous_points=1,
                  integration_method=method, split_method="No Splitting")


def test_background_region_runs_to_the_background(engine):
    """Background integration keeps the whole run above the background."""
    (p,) = detect(engine, "Background")
    assert (p['left_idx'], p['right_idx']) == (990, 1029)
    assert p['total_counts'] == pytest.approx(33 * 50.0 + 4400.0 + 950.0)


def test_midpoint_region_ends_at_the_midpoint_level(engine):
    """Midpoint integration stops where the signal drops below the midpoint."""
    (p,) = detect(engine, "Midpoint")
    assert (p['left_idx'], p['right_idx']) == (1000, 1003)
    assert p['total_counts'] == pytest.approx(6000.0 - 4 * MIDPOINT)


def test_threshold_region_ends_at_the_threshold(engine):
    """Threshold integration stops where the signal drops below the threshold."""
    (p,) = detect(engine, "Threshold")
    assert (p['left_idx'], p['right_idx']) == (1000, 1003)
    assert p['total_counts'] == pytest.approx(6000.0 - 4 * THRESHOLD)


def test_side_bump_under_the_threshold_is_not_a_particle(engine):
    """A bump that never crosses the threshold adds nothing and is not detected."""
    for method in ("Midpoint", "Threshold"):
        particles = detect(engine, method)
        assert len(particles) == 1
        assert particles[0]['right_idx'] < 1015


def test_side_bump_over_the_threshold_becomes_its_own_particle(engine):
    """A second rise above the threshold is a separate particle with Midpoint."""
    time, y = signal_with_side_bump()
    y[1016] = 950.0
    particles = engine.find_particles_safe(time, y, BACKGROUND, THRESHOLD,
                                           integration_method="Midpoint",
                                           split_method="No Splitting")
    assert [(p['left_idx'], p['right_idx']) for p in particles] == [(1000, 1003), (1015, 1017)]


def test_windowed_levels_use_the_same_rule(engine):
    """With array background and threshold the region still ends at the midpoint."""
    time, y = signal_with_side_bump()
    background = np.full(y.size, BACKGROUND)
    threshold = np.full(y.size, THRESHOLD)
    (p,) = engine.find_particles_safe(time, y, background, threshold,
                                      integration_method="Midpoint",
                                      split_method="No Splitting")
    assert (p['left_idx'], p['right_idx']) == (1000, 1003)
    assert p['total_counts'] == pytest.approx(6000.0 - 4 * MIDPOINT)


def test_vectorized_path_counts_the_same(engine):
    """The NumPy path gives the same counts as the compiled one."""
    for method in ("Background", "Midpoint", "Threshold"):
        fast = detect(engine, method)
        slow = detect(engine, method, vectorized=True)
        assert len(fast) == len(slow) == 1
        assert slow[0]['total_counts'] == pytest.approx(fast[0]['total_counts'])
