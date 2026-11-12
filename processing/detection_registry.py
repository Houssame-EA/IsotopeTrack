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

from statistics import NormalDist

import numpy as np

GAUSSIAN_LOW_COUNT = 5.0
"""Counts at or below which a non-zero point is a low point for the background test."""

GAUSSIAN_LOW_FRACTION = 0.05
"""Largest share of low points among the non-zero points of a Gaussian background."""

AUTOMATIC_LOW_BACKGROUND_ID = "CPLN table"
"""Method the Automatic choice uses when the background is not Gaussian."""


def gaussian_z(alpha):
    """Return the one-sided normal quantile of an error rate.

    Args:
        alpha (float): False-positive rate per point, e.g. 1e-6.

    Returns:
        float: z such that a normal value exceeds mean + z·sd with probability alpha.
    """
    alpha = min(max(float(alpha), 1e-300), 0.5)
    return -NormalDist().inv_cdf(alpha)


def is_gaussian_background(signal):
    """Tell whether a signal's background is high enough for a Gaussian threshold.

    The background is taken as Gaussian when fewer than 5 % of the non-zero
    points are at or below 5 counts, which corresponds to a background of
    about 10 counts.

    Args:
        signal (np.ndarray): Signal in counts.

    Returns:
        bool: True when the Gaussian threshold applies.
    """
    signal = np.asarray(signal)
    nonzero = signal > 0
    n_nonzero = int(np.count_nonzero(nonzero))
    if n_nonzero == 0:
        return False
    n_low = int(np.count_nonzero(nonzero & (signal <= GAUSSIAN_LOW_COUNT)))
    return n_low / n_nonzero < GAUSSIAN_LOW_FRACTION


DEFAULT_ALPHA = 1e-6
"""Default false-positive rate per point."""

AUTOMATIC_GAUSSIAN_ALPHA = 1e-7
"""Rate Automatic uses when it picks Gaussian."""


def automatic_alpha(signal):
    """Return the alpha Automatic uses for a signal unless the user set one.

    Args:
        signal (np.ndarray): Signal in counts.

    Returns:
        float: :data:`AUTOMATIC_GAUSSIAN_ALPHA` when the background is
        Gaussian, :data:`DEFAULT_ALPHA` otherwise.
    """
    return AUTOMATIC_GAUSSIAN_ALPHA if is_gaussian_background(signal) else DEFAULT_ALPHA


def _automatic_choice(signal):
    """Return the method id the Automatic choice uses for a signal."""
    return "Gaussian" if is_gaussian_background(signal) else AUTOMATIC_LOW_BACKGROUND_ID


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


def _gaussian_single(engine, lam, alpha, sigma):
    """Gaussian threshold from the background level alone.

    The detection engine uses the measured standard deviation of the
    background instead (see ``DetectionMethod.uses_spread``); with only the
    level known, the Poisson spread sqrt(lambda) stands in for it.
    """
    return lam + gaussian_z(alpha) * np.sqrt(max(float(lam), 0.0))


def _gaussian_array(method, engine, lam_arr, alpha, sigma):
    """Gaussian threshold over an array of background levels, with the Poisson spread."""
    lam_arr = np.asarray(lam_arr, dtype=np.float64)
    return lam_arr + gaussian_z(alpha) * np.sqrt(np.maximum(lam_arr, 0.0))


# ── Method type ───────────────────────────────────────────────────────────────
class DetectionMethod:
    """One detection method: metadata plus the numeric hooks the engine calls."""

    def __init__(self, id, label, *, is_manual=False, user_selectable=True,
                 single, array, uses_spread=False, resolver=None):
        """Describe one detection method.

        Args:
            id (str): Stable name stored in projects.
            label (str): Name shown in the UI.
            is_manual (bool): The threshold is typed by the user.
            user_selectable (bool): Offered in the method lists.
            single (callable): ``(engine, lambda, alpha, sigma) -> threshold``.
            array (callable): ``(method, engine, lambda array, alpha, sigma) -> thresholds``.
            uses_spread (bool): The engine computes the threshold from the mean
                and standard deviation of the background points, not from the
                background level alone.
            resolver (callable | None): ``(signal) -> method id`` for a method
                that stands for another one chosen from the signal.
        """
        self.id = id
        self.label = label
        self.is_manual = is_manual
        self.user_selectable = user_selectable
        self.uses_spread = uses_spread
        self.resolver = resolver
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


def resolve(name, signal):
    """Return the name of the method actually applied to ``signal``.

    A method with a resolver, such as Automatic, stands for another method
    chosen from the signal; every other name is returned unchanged.

    Args:
        name (str): Stored method name.
        signal (np.ndarray): Signal in counts.

    Returns:
        str: Method name to compute the threshold with.
    """
    method = get(name)
    if method.resolver is None:
        return name
    return method.resolver(signal)


def method_text(threshold_data):
    """Return the method a threshold was computed with, for display.

    Args:
        threshold_data (dict): Result of the threshold calculation.

    Returns:
        str: The method used, followed by "(automatic)" when the Automatic
        choice picked it; a dash when unknown.
    """
    used = (threshold_data or {}).get('method_used')
    if not used:
        return "—"
    requested = threshold_data.get('method_requested', used)
    if get(requested).resolver is not None and requested != used:
        return f"{used} (automatic)"
    return str(used)


def all_methods():
    """All registered methods in registration order."""
    return list(_ORDER)


def selectable_labels():
    """UI labels for the user-selectable methods, in registration order."""
    return [m.label for m in _ORDER if m.user_selectable]


register(DetectionMethod(
    "Automatic", "Automatic",
    user_selectable=True,
    single=_cpln_table_single,
    array=_analytic_interp_array,
    resolver=_automatic_choice,
))
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
    "Gaussian", "Gaussian",
    user_selectable=True,
    single=_gaussian_single,
    array=_gaussian_array,
    uses_spread=True,
))
register(DetectionMethod(
    "Poisson", "Poisson 3-sigma",
    user_selectable=False,
    single=_poisson_single,
    array=_poisson_array_clipped,
))
