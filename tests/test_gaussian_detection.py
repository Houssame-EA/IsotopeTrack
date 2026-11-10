"""Tests for the Gaussian threshold and the Automatic method choice of the detection engine."""

from __future__ import annotations

import numpy as np
import pytest

from processing import detection_registry as reg
from processing.peak_detection import PeakDetection


@pytest.fixture(scope="module")
def engine():
    """Return one detection engine for the module."""
    return PeakDetection()


def background(mean: float, n: int = 60000, seed: int = 0) -> np.ndarray:
    """Return a Poisson background of ``n`` points."""
    return np.random.default_rng(seed).poisson(mean, n).astype(np.float64)


def with_particles(signal: np.ndarray, count: int = 400, height: float = 3000.0) -> np.ndarray:
    """Return the signal with evenly spaced particle spikes added."""
    out = signal.copy()
    out[np.linspace(10, out.size - 10, count).astype(int)] += height
    return out


def test_gaussian_threshold_is_mean_plus_z_standard_deviations(engine):
    """Without iteration the threshold comes from the whole signal."""
    signal = background(40.0)
    out = engine.calculate_iterative_threshold(signal, "Gaussian", alpha=1e-6, max_iters=0)
    expected = signal.mean() + reg.gaussian_z(1e-6) * signal.std()
    assert out['threshold'] == pytest.approx(expected)
    assert out['background'] == pytest.approx(signal.mean())
    assert out['method_used'] == "Gaussian" and out['method_requested'] == "Gaussian"


def test_alpha_sets_the_strictness(engine):
    """A smaller error rate gives a higher threshold."""
    signal = background(40.0)
    loose = engine.calculate_iterative_threshold(signal, "Gaussian", alpha=1e-3, max_iters=0)
    strict = engine.calculate_iterative_threshold(signal, "Gaussian", alpha=1e-9, max_iters=0)
    assert strict['threshold'] > loose['threshold']


def test_iteration_removes_the_particles_from_the_background(engine):
    """Iterating brings the threshold of a particle-rich signal back to the clean one."""
    clean = background(40.0)
    signal = with_particles(clean)
    reference = engine.calculate_iterative_threshold(clean, "Gaussian", max_iters=0)['threshold']
    once = engine.calculate_iterative_threshold(signal, "Gaussian", max_iters=0)['threshold']
    refined = engine.calculate_iterative_threshold(signal, "Gaussian", max_iters=4)
    assert once > 2 * reference
    assert refined['threshold'] == pytest.approx(reference, rel=0.03)
    assert refined['background'] == pytest.approx(clean.mean(), rel=0.01)


def test_automatic_uses_gaussian_on_a_high_background(engine):
    """Automatic gives the Gaussian result when the background is high."""
    signal = with_particles(background(30.0))
    auto = engine.calculate_iterative_threshold(signal, "Automatic")
    forced = engine.calculate_iterative_threshold(signal, "Gaussian")
    assert auto['method_used'] == "Gaussian" and auto['method_requested'] == "Automatic"
    assert auto['threshold'] == pytest.approx(forced['threshold'])


def test_automatic_uses_the_cpln_table_on_a_low_background(engine):
    """Automatic gives the CPLN table result when the background is low."""
    signal = with_particles(background(0.4), height=200.0)
    auto = engine.calculate_iterative_threshold(signal, "Automatic", sigma=0.55)
    table = engine.calculate_iterative_threshold(signal, "CPLN table", sigma=0.55)
    assert auto['method_used'] == "CPLN table"
    assert auto['threshold'] == pytest.approx(table['threshold'])


def test_windowed_gaussian_follows_a_drifting_background(engine):
    """With a window the threshold is an array that follows the local background."""
    signal = np.concatenate([background(20.0, 30000, seed=1), background(60.0, 30000, seed=2)])
    out = engine.calculate_iterative_threshold(signal, "Gaussian", use_window_size=True,
                                               window_size=2001)
    threshold = np.asarray(out['threshold'])
    assert threshold.shape == signal.shape
    assert threshold[5000:25000].mean() < threshold[35000:55000].mean()
    assert np.asarray(out['background'])[5000:25000].mean() == pytest.approx(20.0, rel=0.05)
    assert np.all(np.isfinite(threshold))
