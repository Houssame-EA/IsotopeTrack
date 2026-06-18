"""Registry of single-particle detection threshold methods.

This module is the single source of truth for the detection methods
IsotopeTrack offers. Each method declares its stable id, the label shown in the
UI, whether the user can pick it, and the numeric hooks the detection engine
uses to turn a background level (lambda) into a threshold.

Adding a new detection method is done *here* — define a :class:`DetectionMethod`
and :func:`register` it — without editing the ``if/elif`` dispatch that used to
live in ``processing/peak_detection.py``.

The numeric hooks mirror, expression for expression, the original branches they
replaced, so detection results are unchanged. ``tests/test_detection_registry.py``
checks that equivalence against a reference transcription of the old logic.

Only numpy is imported, so this module is safe to import (and unit-test) without
PySide6, numba, or scipy.
"""
from __future__ import annotations

import numpy as np


# ── Shared numeric hooks ──────────────────────────────────────────────────────
def _poisson_single(engine, lam, alpha, sigma):
    """3-sigma Poisson threshold (unclipped) — the historic ``else`` fallback."""
    return lam + 3.0 * np.sqrt(lam)


def _poisson_array_clipped(method, engine, lam_arr, alpha, sigma):
    """3-sigma Poisson threshold over an array, clipping lambda at 1.

    Mirrors the ``else`` branch of the original ``_calculate_array_threshold``.
    """
    return lam_arr + 3.0 * np.sqrt(np.maximum(lam_arr, 1))


def _manual_array(method, engine, lam_arr, alpha, sigma):
    """Manual method over an array — historically routed through the Poisson
    fallback in ``_calculate_single_threshold`` (unclipped)."""
    return lam_arr + 3.0 * np.sqrt(lam_arr)


def _analytic_interp_array(method, engine, lam_arr, alpha, sigma):
    """Interpolated thresholds across the background range for analytic methods.

    Replicates the Compound-Poisson branch of the original
    ``_calculate_array_threshold``: evaluate the method's single-value threshold
    on a small background grid and linearly interpolate.
    """
    min_bg = np.min(lam_arr)
    max_bg = np.max(lam_arr)
    if min_bg == max_bg:
        single_thresh = method.single_threshold(engine, min_bg, alpha, sigma)
        return np.full_like(lam_arr, single_thresh)
    n_eval = min(30, max(5, int((max_bg - min_bg) / 0.5)))
    eval_bg = np.linspace(min_bg, max_bg, n_eval)
    eval_thresh = np.array([
        method.single_threshold(engine, bg, alpha, sigma) for bg in eval_bg
    ])
    return np.interp(lam_arr, eval_bg, eval_thresh)


def _cpln_lognormal_single(engine, lam, alpha, sigma):
    """Analytic Compound Poisson Log-Normal threshold.

    Uses the caller-supplied per-isotope sigma (the log-normal width of the
    single-ion response) so the sigma set in the parameters table actually
    drives the threshold. Falls back to the historic 0.55 default when sigma
    is missing or non-positive, since a log-normal requires sigma > 0.
    """
    if sigma is None or sigma <= 0:
        sigma = 0.55
    return engine.compound_poisson_lognormal.get_threshold(lam, alpha, sigma=sigma)


def _cpln_table_single(engine, lam, alpha, sigma):
    """Lookup-table Compound Poisson Log-Normal threshold (uses caller sigma)."""
    return engine.compound_poisson_lognormal_lut.get_threshold(lam, alpha, sigma)


# ── Method type ───────────────────────────────────────────────────────────────
class DetectionMethod:
    """One detection method: metadata plus the numeric hooks the engine calls."""

    def __init__(self, id, label, *, is_manual=False, user_selectable=True,
                 single, array):
        self.id = id
        self.label = label
        self.is_manual = is_manual
        self.user_selectable = user_selectable
        self._single = single
        self._array = array

    def single_threshold(self, engine, lambda_bkgd, alpha, sigma):
        """Threshold for a single background value."""
        return self._single(engine, lambda_bkgd, alpha, sigma)

    def array_threshold(self, engine, lambda_bkgd_array, alpha, sigma):
        """Threshold for an array of background values (moving window)."""
        return self._array(self, engine, lambda_bkgd_array, alpha, sigma)

    def __repr__(self):
        return f"DetectionMethod({self.id!r})"


# ── Registry ──────────────────────────────────────────────────────────────────
_BY_ID = {}
_ORDER = []

#: Method used for any unrecognised name — matches the historic ``else`` branch.
DEFAULT_METHOD_ID = "Poisson"


def register(method):
    """Register a :class:`DetectionMethod` (returns it, for decorator-style use)."""
    if method.id not in _BY_ID:
        _ORDER.append(method)
    _BY_ID[method.id] = method
    return method


def get(name):
    """Return the method for ``name`` (a stored or label string).

    Unknown names fall back to the Poisson default, exactly as the old
    ``if/elif`` chains did with their trailing ``else``.
    """
    return _BY_ID.get(name, _BY_ID[DEFAULT_METHOD_ID])


def all_methods():
    """All registered methods in registration order."""
    return list(_ORDER)


def selectable_labels():
    """UI labels for the user-selectable methods, in registration order."""
    return [m.label for m in _ORDER if m.user_selectable]


# ── Built-in methods ──────────────────────────────────────────────────────────
# NOTE: ids are the exact strings already stored in saved projects and shown in
# the UI, so lookups keep working for existing data without any remapping.
register(DetectionMethod(
    "Manual", "Manual",
    is_manual=True, user_selectable=True,
    single=_poisson_single,
    array=_manual_array,
))
register(DetectionMethod(
    "Compound Poisson LogNormal", "Compound Poisson LogNormal",
    user_selectable=True,
    single=_cpln_lognormal_single,
    array=_analytic_interp_array,
))
register(DetectionMethod(
    "CPLN table", "CPLN table",
    user_selectable=True,
    single=_cpln_table_single,
    array=_analytic_interp_array,
))
register(DetectionMethod(
    "Poisson", "Poisson 3-sigma",
    user_selectable=False,
    single=_poisson_single,
    array=_poisson_array_clipped,
))
