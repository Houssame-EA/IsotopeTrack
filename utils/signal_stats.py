"""Exclusion-aware signal statistics (non-visual).

The mean signal reported in summaries, mass-spectrum bars and exports must be
computed over the *analyzed* part of a trace only: time windows the user has
dropped with an exclusion region are not part of the acquisition any more, so
they must not contribute to the mean, the standard deviation or the RSD --
exactly as ``utils.dilution.effective_acquisition_time`` already removes them
from the acquisition time.

This also removes non-finite samples. Nu autoblanking writes ``np.nan`` into
the blanked mass/time windows (``loading.vitesse_loading.blank_nu_signal_data``),
and a single NaN turns a plain ``np.mean`` into NaN for the whole trace. A
sample that is not a number was never measured, so it is treated like excluded
time rather than poisoning the result.

Pure logic, no Qt dependency, so it can be unit-tested without a GUI.
"""
import logging

import numpy as np

_itk_log = logging.getLogger("IsotopeTrack.utils.signal_stats")


def _time_array_for(window, sample_name):
    """
    Return the time axis stored for a sample, or None.

    Args:
        window (Any): Owning window exposing time arrays.
        sample_name (str): Sample identifier.

    Returns:
        np.ndarray | None: The sample's time axis, or None when unavailable.
    """
    by_sample = getattr(window, 'time_array_by_sample', {}) or {}
    time_array = by_sample.get(sample_name)
    if time_array is None and sample_name == getattr(window, 'current_sample', None):
        time_array = getattr(window, 'time_array', None)
    if time_array is None:
        return None
    return np.asarray(time_array, dtype=float)


def analyzed_mask(window, sample_name, element_key, signal):
    """
    Boolean keep-mask over a signal: True where the sample counts.

    A point is dropped when it falls inside a visible exclusion region for
    this sample/element, or when its value is not finite (NaN from
    autoblanking, +/-inf).

    Sample-scope exclusions apply to every element; element-scope exclusions
    apply only when element_key matches the stored region -- the same rule
    ``_visible_exclusion_entries_for`` uses for drawing the bands.

    Args:
        window (Any): Owning window exposing time arrays and exclusion regions.
        sample_name (str): Sample identifier.
        element_key (str): Element key such as ``"Ag-106.9051"``, or None.
        signal (Any): 1D signal array aligned with the sample's time axis.

    Returns:
        np.ndarray: Boolean mask the same length as signal.
    """
    arr = np.asarray(signal, dtype=float)
    mask = np.isfinite(arr)
    if not mask.any():
        return mask

    time_array = _time_array_for(window, sample_name)
    if time_array is None or len(time_array) != len(arr):
        return mask

    entries = []
    if hasattr(window, '_visible_exclusion_entries_for'):
        try:
            entries = window._visible_exclusion_entries_for(sample_name, element_key)
        except Exception:
            _itk_log.exception("Handled exception in analyzed_mask")
            entries = []

    for entry in entries or []:
        bounds = entry.get('bounds') if isinstance(entry, dict) else None
        if not bounds:
            continue
        try:
            x0, x1 = float(bounds[0]), float(bounds[1])
        except (TypeError, ValueError):
            _itk_log.exception("Handled exception in analyzed_mask")
            continue
        if x1 < x0:
            x0, x1 = x1, x0
        mask &= ~((time_array >= x0) & (time_array <= x1))

    return mask


def analyzed_signal(window, sample_name, element_key, signal):
    """
    Return only the samples that count towards signal statistics.

    Args:
        window (Any): Owning window exposing time arrays and exclusion regions.
        sample_name (str): Sample identifier.
        element_key (str): Element key such as ``"Ag-106.9051"``, or None.
        signal (Any): 1D signal array aligned with the sample's time axis.

    Returns:
        np.ndarray: 1D float array of the retained samples, possibly empty.
    """
    arr = np.asarray(signal, dtype=float)
    if arr.size == 0:
        return arr
    return arr[analyzed_mask(window, sample_name, element_key, arr)]


def mean_signal(window, sample_name, element_key, signal, default=0.0):
    """
    Mean signal over the analyzed part of a trace.

    Args:
        window (Any): Owning window exposing time arrays and exclusion regions.
        sample_name (str): Sample identifier.
        element_key (str): Element key such as ``"Ag-106.9051"``, or None.
        signal (Any): 1D signal array aligned with the sample's time axis.
        default (float): Value returned when nothing is left to average.

    Returns:
        float: Mean of the retained samples, or default when none remain.
    """
    kept = analyzed_signal(window, sample_name, element_key, signal)
    return float(np.mean(kept)) if kept.size else float(default)


def mean_std_signal(window, sample_name, element_key, signal, ddof=0,
                    default=0.0):
    """
    Mean and standard deviation over the analyzed part of a trace.

    Args:
        window (Any): Owning window exposing time arrays and exclusion regions.
        sample_name (str): Sample identifier.
        element_key (str): Element key such as ``"Ag-106.9051"``, or None.
        signal (Any): 1D signal array aligned with the sample's time axis.
        ddof (int): Delta degrees of freedom for the standard deviation.
        default (float): Value returned when nothing is left to average.

    Returns:
        tuple[float, float]: (mean, standard deviation); the deviation is 0.0
            when fewer than ddof+1 samples remain.
    """
    kept = analyzed_signal(window, sample_name, element_key, signal)
    if kept.size == 0:
        return float(default), 0.0
    mean = float(np.mean(kept))
    std = float(np.std(kept, ddof=ddof)) if kept.size > ddof else 0.0
    return mean, std
