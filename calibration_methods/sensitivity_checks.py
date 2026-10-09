"""Quality checks on an ionic calibration.

Pure numpy/scipy, no Qt, so every check can be unit-tested on its own. The
Ionic Calibration window runs them after each calculation and lists the
results in its Checks window.

Checks
------
* :func:`slope_uncertainty` – standard error and 95 % interval of a slope
* :func:`linearity_check` – does the top standard fall below the line?
* :func:`abundance_check` – do isotopes of one element scale with abundance?
* :func:`repeat_standard_drift` – do repeated standards agree over the run?
* :func:`blank_source` – which standard the LOD/LOQ noise comes from
* :class:`SensitivityHistory` – slopes saved per day, compared with the last day
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from collections import defaultdict

import numpy as np
from scipy import stats

LINEARITY_LIMIT_PCT = 5.0
ABUNDANCE_LIMIT_PCT = 10.0
DRIFT_LIMIT_PCT = 5.0
HISTORY_LIMIT_PCT = 20.0


def slope_uncertainty(x, y, y_std=None, method='simple'):
    """
    Standard error and 95 % confidence half-width of a calibration slope.

    * ``zero``: s² = SSres/(n−1), SE = √(s²/Σx²)
    * ``simple``: s² = SSres/(n−2), SE = √(s²/Σ(x−x̄)²)
    * ``weighted``: wᵢ = 1/σᵢ², SE = √(Σw / (Σw·Σwx² − (Σwx)²))

    Args:
        x, y: Concentrations and mean signals of the included standards.
        y_std: Signal standard deviations (``weighted`` only).
        method: 'zero', 'simple' or 'weighted'.

    Returns:
        dict with ``se`` and ``ci95`` (NaN when there are too few points).
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = len(x)
    nan = {'se': float('nan'), 'ci95': float('nan')}
    if method == 'zero':
        dof = n - 1
        sxx = float(np.sum(x * x))
        if dof < 1 or sxx == 0:
            return nan
        slope = float(np.sum(x * y)) / sxx
        s2 = float(np.sum((y - slope * x) ** 2)) / dof
        se = np.sqrt(s2 / sxx)
    elif method == 'weighted':
        dof = n - 2
        if y_std is None or dof < 1:
            return nan
        s = np.asarray(y_std, float)
        if np.any(s <= 0):
            return slope_uncertainty(x, y, method='simple')
        w = 1.0 / s ** 2
        d = float(np.sum(w) * np.sum(w * x * x) - np.sum(w * x) ** 2)
        if d <= 0:
            return nan
        se = np.sqrt(float(np.sum(w)) / d)
    else:
        dof = n - 2
        sxx = float(np.sum((x - x.mean()) ** 2))
        if dof < 1 or sxx == 0:
            return nan
        slope, intercept = np.polyfit(x, y, 1)
        s2 = float(np.sum((y - slope * x - intercept) ** 2)) / dof
        se = np.sqrt(s2 / sxx)
    return {'se': float(se), 'ci95': float(stats.t.ppf(0.975, dof) * se)}


def linearity_check(x, y, limit_pct=LINEARITY_LIMIT_PCT):
    """
    Test whether the highest standard falls below the line of the others.

    The line is refitted (ordinary least squares) without the top standard;
    a top point more than *limit_pct* below that line suggests detector
    saturation or another non-linearity.

    Args:
        x, y: Concentrations and mean signals of the included standards.
        limit_pct: How far below the line (in %) is flagged.

    Returns:
        dict with ``top_x``, ``top_deviation_pct`` (top point vs the line of
        the others), ``slope_change_pct`` (slope with vs without it) and
        ``flag``; None with fewer than four standards.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 4:
        return None
    top = int(np.argmax(x))
    rest = np.arange(len(x)) != top
    if len(np.unique(x[rest])) < 2:
        return None
    slope_rest, icpt_rest = np.polyfit(x[rest], y[rest], 1)
    slope_all, _ = np.polyfit(x, y, 1)
    predicted = slope_rest * x[top] + icpt_rest
    if predicted <= 0 or slope_rest == 0:
        return None
    deviation = (y[top] - predicted) / predicted * 100.0
    return {
        'top_x': float(x[top]),
        'top_deviation_pct': float(deviation),
        'slope_change_pct': float((slope_all - slope_rest) / slope_rest * 100.0),
        'flag': bool(deviation < -limit_pct),
    }


def abundance_check(isotopes, limit_pct=ABUNDANCE_LIMIT_PCT):
    """
    Compare the isotopes of each element with their natural abundance.

    Without interference, slope/abundance is the same for every isotope of
    an element (up to the small mass bias between neighbouring masses). An
    isotope well above the element's median suggests an oxide or isobaric
    overlap adding signal; well below, a wrong abundance or a loss.

    Args:
        isotopes: {isotope_key: (element, slope, abundance_percent)}.
        limit_pct: Deviation from the element's median that is flagged.

    Returns:
        {isotope_key: {'deviation_pct', 'flag'}} for elements with at least
        two isotopes with a positive slope and abundance.
    """
    by_element = defaultdict(list)
    for key, (element, slope, abundance) in isotopes.items():
        if slope and abundance and slope > 0 and abundance > 0:
            by_element[element].append((key, slope / abundance))
    out = {}
    for members in by_element.values():
        if len(members) < 2:
            continue
        ref = float(np.median([v for _, v in members]))
        for key, value in members:
            dev = (value / ref - 1.0) * 100.0
            out[key] = {'deviation_pct': float(dev), 'flag': bool(abs(dev) > limit_pct)}
    return out


def repeat_standard_drift(x, y, limit_pct=DRIFT_LIMIT_PCT):
    """
    Compare standards measured more than once during the run.

    Points are taken in acquisition order. For every non-zero concentration
    measured at least twice, the change from its first to its last
    measurement is reported; the largest change decides the flag.

    Args:
        x, y: Concentrations and mean signals, in acquisition order.
        limit_pct: Change between repeats that is flagged.

    Returns:
        dict with ``max_drift_pct``, ``at_x``, ``repeats`` and ``flag``, or
        None when no standard was repeated.
    """
    groups = defaultdict(list)
    for xi, yi in zip(np.asarray(x, float), np.asarray(y, float)):
        if xi > 0:
            groups[round(float(xi), 9)].append(float(yi))
    worst = None
    for conc, ys in groups.items():
        if len(ys) < 2 or ys[0] <= 0:
            continue
        drift = (ys[-1] - ys[0]) / ys[0] * 100.0
        if worst is None or abs(drift) > abs(worst[0]):
            worst = (drift, conc, len(ys))
    if worst is None:
        return None
    return {'max_drift_pct': worst[0], 'at_x': worst[1], 'repeats': worst[2],
            'flag': bool(abs(worst[0]) > limit_pct)}


def blank_source(x):
    """
    Describe which standard the LOD/LOQ noise comes from.

    The figures of merit use the noise of the lowest included standard; that
    is a true blank only when a 0-concentration standard is included.

    Returns:
        dict with ``x`` and ``is_blank``, or None without standards.
    """
    x = np.asarray(x, float)
    if not len(x):
        return None
    low = float(np.min(x))
    return {'x': low, 'is_blank': low == 0.0}


class SensitivityHistory:
    """
    Slopes kept per day in a small JSON file, to follow the instrument.

    One entry per isotope and day: saving again on the same day replaces
    that day's value. :meth:`previous` returns the latest earlier day.
    """

    def __init__(self, path=None):
        if path is None:
            try:
                from platformdirs import user_data_dir
                base = user_data_dir('IsotopeTrack', appauthor=False)
            except Exception:
                base = os.path.join(os.path.expanduser('~'), '.isotopetrack')
            path = os.path.join(base, 'sensitivity_history.json')
        self.path = path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, encoding='utf-8') as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def record(self, slopes, day=None):
        """Store {isotope_key: slope} for *day* (today by default) and save."""
        day = day or _dt.date.today().isoformat()
        for key, slope in slopes.items():
            if slope and np.isfinite(slope) and slope > 0:
                self.data.setdefault(key, {})[day] = float(slope)
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as fh:
                json.dump(self.data, fh, indent=1, sort_keys=True)
        except OSError:
            pass

    def previous(self, key, day=None):
        """(day, slope) of the latest entry before *day*, or None."""
        day = day or _dt.date.today().isoformat()
        earlier = sorted(d for d in self.data.get(key, {}) if d < day)
        return (earlier[-1], self.data[key][earlier[-1]]) if earlier else None

    def compare(self, key, slope, day=None, limit_pct=HISTORY_LIMIT_PCT):
        """
        Change of *slope* against the latest earlier day.

        Returns:
            dict with ``day``, ``previous``, ``change_pct`` and ``flag``, or None.
        """
        prev = self.previous(key, day)
        if prev is None or not slope or prev[1] <= 0:
            return None
        change = (slope - prev[1]) / prev[1] * 100.0
        return {'day': prev[0], 'previous': prev[1], 'change_pct': float(change),
                'flag': bool(abs(change) > limit_pct)}


def drift_factors(x, y, included=None):
    """
    Relative sensitivity at each standard, from standards measured more than once.

    Points are taken in acquisition order (their position in the list). The
    non-zero concentration measured most often (the highest one on a tie)
    is the drift monitor: its first measurement defines a factor of 1, each
    later repeat gives the factor ``y_repeat / y_first`` at its position, and
    every other standard gets the factor interpolated linearly between the
    bracketing repeats (held constant before the first and after the last).

    Args:
        x, y: Concentrations and mean signals, in acquisition order.
        included: Optional bool mask; only included points act as monitors.

    Returns:
        numpy array of factors (divide signals by it to correct), or None
        when no standard was repeated.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.ones(len(x), bool) if included is None else np.asarray(included, bool)
    groups = defaultdict(list)
    for i, (xi, yi) in enumerate(zip(x, y)):
        if mask[i] and xi > 0 and yi > 0:
            groups[round(float(xi), 9)].append(i)
    repeated = [(len(idx), conc, idx) for conc, idx in groups.items() if len(idx) >= 2]
    if not repeated:
        return None
    _, _, idx = max(repeated)
    positions = np.array(idx, float)
    ratios = y[idx] / y[idx[0]]
    return np.interp(np.arange(len(x), dtype=float), positions, ratios)
