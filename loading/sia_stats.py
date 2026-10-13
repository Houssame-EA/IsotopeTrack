"""Statistics and history for single-ion area (SIA) distributions.

Qt-free helpers used by :mod:`loading.SIA_manager`:

* per-mass sigma summary with standard errors, a robust outlier rule
  (modified z-score on the median absolute deviation) and an
  inverse-variance weighted mean,
* a weighted straight-line fit of sigma against m/z,
* isotope labels for an m/z value,
* a small JSON history of loaded SIAs with control limits.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os

import numpy as np
from scipy import stats

MASS_MATCH_TOL = 2.0
ISOTOPE_LABEL_TOL = 0.5
ROBUST_Z_LIMIT = 3.5
MIN_HISTORY_FOR_LIMITS = 3

_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def sigma_standard_error(sigma, n):
    """Approximate standard error of a lognormal sigma estimated from n events.

    Uses the large-sample result for the standard deviation of the
    log-signal, ``sigma / sqrt(2 (n - 1))``.

    Args:
        sigma (float): Estimated sigma.
        n (int): Number of single-ion events behind the estimate.

    Returns:
        float: Standard error, or ``nan`` when n < 2.
    """
    if n is None or n < 2 or not np.isfinite(sigma):
        return float("nan")
    return float(sigma) / math.sqrt(2.0 * (n - 1))


def robust_outlier_mask(values, limit=ROBUST_Z_LIMIT):
    """Flag outliers with the modified z-score of Iglewicz and Hoaglin.

    ``z = 0.6745 (x - median) / MAD``; values with ``|z| > limit`` are
    outliers. The median and MAD are not pulled by the outliers
    themselves, unlike the mean and standard deviation.

    Args:
        values (array-like): Values to test.
        limit (float): Threshold on the absolute modified z-score.

    Returns:
        np.ndarray: Boolean mask, True for outliers. All False when fewer
        than four values or when the MAD is zero.
    """
    x = np.asarray(values, dtype=float)
    mask = np.zeros(x.shape, dtype=bool)
    if x.size < 4:
        return mask
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    if mad <= 0 or not np.isfinite(mad):
        return mask
    z = 0.6745 * (x - med) / mad
    return np.abs(z) > limit


def weighted_mean_sd(values, weights):
    """Weighted mean and weighted standard deviation.

    Args:
        values (array-like): Values.
        weights (array-like): Non-negative weights.

    Returns:
        tuple: (mean, sd). Falls back to the plain mean and SD when the
        weights are unusable.
    """
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    ok = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not ok.any():
        if x.size == 0:
            return float("nan"), float("nan")
        return float(np.mean(x)), float(np.std(x))
    x, w = x[ok], w[ok]
    mean = float(np.sum(w * x) / np.sum(w))
    sd = float(np.sqrt(np.sum(w * (x - mean) ** 2) / np.sum(w)))
    return mean, sd


def linear_trend(x, y, weights=None):
    """Weighted least-squares straight line ``y = a + b x``.

    Args:
        x (array-like): Predictor (m/z).
        y (array-like): Response (sigma).
        weights (array-like | None): Weights, for example event counts.

    Returns:
        dict | None: ``intercept``, ``slope``, ``slope_se``, ``p_value``
        (two-sided t-test of slope = 0) and ``n``; None with fewer than
        three points or no spread in x.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.ones_like(x) if weights is None else np.asarray(weights, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(w) & (w > 0)
    x, y, w = x[ok], y[ok], w[ok]
    n = x.size
    if n < 3:
        return None
    xm = np.sum(w * x) / np.sum(w)
    ym = np.sum(w * y) / np.sum(w)
    sxx = np.sum(w * (x - xm) ** 2)
    if sxx <= 0:
        return None
    slope = np.sum(w * (x - xm) * (y - ym)) / sxx
    intercept = ym - slope * xm
    resid = y - (intercept + slope * x)
    dof = n - 2
    s2 = np.sum(w * resid ** 2) / dof if dof > 0 else float("nan")
    slope_se = math.sqrt(s2 / sxx) if np.isfinite(s2) and s2 >= 0 else float("nan")
    if slope_se > 0 and np.isfinite(slope_se):
        t = slope / slope_se
        p = float(2.0 * stats.t.sf(abs(t), dof))
    else:
        p = float("nan")
    return {"intercept": float(intercept), "slope": float(slope),
            "slope_se": float(slope_se), "p_value": p, "n": int(n)}


def summarize_per_mass(per_mass, exclude_outliers=False):
    """Summary of the per-mass sigma values used by the comparison plot.

    Each mass is weighted by ``n - 1``, its number of single-ion events
    minus one. This is the inverse variance of the sigma estimate with a
    common sigma; using each mass's own sigma in the weight would pull the
    mean toward the smallest values.

    Args:
        per_mass (dict): ``{key: {'mass', 'sigma', 'num_points', ...}}``.
        exclude_outliers (bool): Compute the mean and SD without outliers.

    Returns:
        dict | None: ``keys``, ``masses``, ``sigmas``, ``n``, ``se``,
        ``weights``, ``outliers`` (bool mask), ``mean``, ``sd``,
        ``n_outliers``, ``excluded`` (True when outliers were removed from
        the mean) and ``trend`` (see :func:`linear_trend`); None when
        there is no per-mass data.
    """
    if not per_mass:
        return None
    rows = sorted(per_mass.items(), key=lambda kv: kv[1]["mass"])
    keys = [k for k, _ in rows]
    masses = np.array([d["mass"] for _, d in rows], dtype=float)
    sigmas = np.array([d["sigma"] for _, d in rows], dtype=float)
    n = np.array([d.get("num_points", 0) for _, d in rows], dtype=float)
    se = np.array([sigma_standard_error(s, k) for s, k in zip(sigmas, n)])
    weights = np.clip(n - 1.0, 0.0, None)
    outliers = robust_outlier_mask(sigmas)
    excluded = bool(exclude_outliers and outliers.any())
    use = ~outliers if excluded else np.ones_like(outliers)
    mean, sd = weighted_mean_sd(sigmas[use], weights[use])
    trend = linear_trend(masses[use], sigmas[use], weights[use])
    return {"keys": keys, "masses": masses, "sigmas": sigmas, "n": n,
            "se": se, "weights": weights, "outliers": outliers,
            "mean": mean, "sd": sd, "n_outliers": int(outliers.sum()),
            "excluded": excluded, "trend": trend}


def effective_sigma(calculated_sigma, per_mass, exclude_outliers):
    """Sigma the application should use.

    Without outlier exclusion this is the sigma of the whole single-ion
    distribution. With exclusion, and at least one outlier present, it is
    the weighted mean of the remaining per-mass sigma values.

    Args:
        calculated_sigma (float): Sigma of the overall distribution.
        per_mass (dict): Per-mass distributions.
        exclude_outliers (bool): Whether outliers are excluded.

    Returns:
        tuple: (sigma, source) where source is ``'overall'`` or
        ``'per_mass_mean'``.
    """
    if exclude_outliers:
        summary = summarize_per_mass(per_mass, exclude_outliers=True)
        if summary is not None and summary["excluded"] and np.isfinite(summary["mean"]):
            return summary["mean"], "per_mass_mean"
    return float(calculated_sigma), "overall"


def nearest_per_mass(per_mass, target_mass, tol=MASS_MATCH_TOL):
    """Per-mass entry closest to a target m/z.

    Args:
        per_mass (dict): Per-mass distributions.
        target_mass (float): m/z to match.
        tol (float): Largest accepted difference.

    Returns:
        tuple | None: (key, entry) or None when nothing is within ``tol``.
    """
    best, best_diff = None, float("inf")
    for key, d in (per_mass or {}).items():
        diff = abs(d["mass"] - target_mass)
        if diff < best_diff:
            best, best_diff = (key, d), diff
    if best is None or best_diff > tol:
        return None
    return best


def superscript_label(label):
    """Turn an isotope label such as ``'56Fe'`` into ``'⁵⁶Fe'``.

    Args:
        label (str): Label with the mass number first.

    Returns:
        str: Label with the mass number in superscript digits.
    """
    digits = ""
    for ch in label:
        if ch.isdigit():
            digits += ch
        else:
            break
    return digits.translate(_SUPERSCRIPT) + label[len(digits):]


def isotope_index(elements):
    """Flat list of natural isotopes from periodic-table element records.

    Args:
        elements (list[dict]): Records with ``symbol`` and ``isotopes``
            (each isotope a dict with ``mass``, ``abundance``, ``label``).

    Returns:
        list[tuple]: ``(mass, abundance, label)`` sorted by mass, only
        isotopes with a positive natural abundance.
    """
    out = []
    for el in elements or []:
        for iso in el.get("isotopes", []) or []:
            if not isinstance(iso, dict):
                continue
            ab = iso.get("abundance") or 0
            if ab and ab > 0 and iso.get("mass") is not None:
                out.append((float(iso["mass"]), float(ab), str(iso.get("label", ""))))
    out.sort()
    return out


def isotopes_at_mass(index, mass, tol=ISOTOPE_LABEL_TOL, preferred=()):
    """Isotope labels found at an m/z value.

    Args:
        index (list[tuple]): Output of :func:`isotope_index`.
        mass (float): m/z.
        tol (float): Largest mass difference.
        preferred (iterable[str]): Labels to list first, for example the
            isotopes selected for analysis.

    Returns:
        list[str]: Labels such as ``['58Ni', '58Fe']``, preferred ones first,
        then by decreasing abundance.
    """
    pref = set(preferred)
    hits = [(lab not in pref, -ab, lab) for m, ab, lab in index if abs(m - mass) <= tol]
    hits.sort()
    return [lab for _, _, lab in hits]


def mass_label(mass, index, preferred=()):
    """Isotope label for an m/z value.

    Args:
        mass (float): m/z.
        index (list[tuple]): Output of :func:`isotope_index`.
        preferred (iterable[str]): Labels to list first.

    Returns:
        str: For example ``'⁵⁶Fe'`` or ``'⁵⁸Ni / ⁵⁸Fe'``; the rounded m/z,
        such as ``'m/z 12'``, when no isotope matches.
    """
    labels = isotopes_at_mass(index, mass, preferred=preferred)
    if labels:
        return " / ".join(superscript_label(l) for l in labels)
    return f"m/z {int(round(mass))}"


def parse_datetime(text):
    """Parse an ISO-like date string.

    Args:
        text (str): Date string, e.g. ``'2026-10-01T09:12:00Z'``.

    Returns:
        datetime.datetime | None: Naive datetime, or None when unparseable.
    """
    if not text or not isinstance(text, str):
        return None
    try:
        dt = _dt.datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=None)


def history_entry(info, per_mass, source_path, effective=None, now=None):
    """Build one history record from a loaded SIA.

    Args:
        info (dict): ``single_ion_info``.
        per_mass (dict): Per-mass distributions.
        source_path (str): File or folder the SIA was read from.
        effective (float | None): Sigma in use, if different from the
            calculated one.
        now (datetime.datetime | None): Time of recording.

    Returns:
        dict: JSON-serialisable record.
    """
    now = now or _dt.datetime.now()
    analysed = parse_datetime(info.get("analysis_datetime"))
    date = analysed or now
    instrument = info.get("instrument_type", "Unknown")
    key = f"{instrument}|{source_path}|{info.get('analysis_datetime', '')}"
    return {
        "key": key,
        "date": date.isoformat(timespec="seconds"),
        "date_from_file": analysed is not None,
        "recorded_at": now.isoformat(timespec="seconds"),
        "instrument": instrument,
        "sample_name": info.get("sample_name", ""),
        "source": str(source_path or ""),
        "sigma": float(info.get("calculated_sigma", float("nan"))),
        "effective_sigma": None if effective is None else float(effective),
        "mean_signal": float(info.get("mean_signal", float("nan"))),
        "average_single_ion_area": float(info.get("average_single_ion_area", float("nan"))),
        "num_valid_masses": int(info.get("num_valid_masses", len(per_mass or {}))),
        "per_mass_sigma": {f"{d['mass']:.4f}": float(d["sigma"])
                           for d in (per_mass or {}).values()},
    }


def control_limits(values):
    """Mean and ±2 SD / ±3 SD limits of earlier values.

    Args:
        values (array-like): Earlier values.

    Returns:
        dict | None: ``mean``, ``sd``, ``warn`` (lo, hi) and ``action``
        (lo, hi); None with fewer than :data:`MIN_HISTORY_FOR_LIMITS` values.
    """
    x = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if x.size < MIN_HISTORY_FOR_LIMITS:
        return None
    mean = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    return {"mean": mean, "sd": sd,
            "warn": (mean - 2 * sd, mean + 2 * sd),
            "action": (mean - 3 * sd, mean + 3 * sd)}


def classify(value, limits):
    """Where a value falls against control limits.

    Args:
        value (float): Value to check.
        limits (dict | None): Output of :func:`control_limits`.

    Returns:
        str: ``'unknown'`` (no limits), ``'ok'``, ``'warn'`` (beyond 2 SD)
        or ``'action'`` (beyond 3 SD).
    """
    if limits is None or value is None or not np.isfinite(value):
        return "unknown"
    lo, hi = limits["action"]
    if value < lo or value > hi:
        return "action"
    lo, hi = limits["warn"]
    if value < lo or value > hi:
        return "warn"
    return "ok"


def default_history_path():
    """Location of the SIA history file next to the other app data.

    Returns:
        str: Path to ``sia_history.json``.
    """
    try:
        from platformdirs import user_data_dir
        base = user_data_dir("IsotopeTrack", appauthor=False)
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".isotopetrack")
    return os.path.join(base, "sia_history.json")


class SIAHistory:
    """SIA records kept in a JSON file to follow the detector between sessions.

    Loading the same SIA again (same instrument, source and acquisition
    time) replaces its record instead of adding a new one.

    Args:
        path (str | None): JSON file; :func:`default_history_path` when None.
    """

    def __init__(self, path=None):
        self.path = path or default_history_path()
        self.entries = self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return []
        entries = data.get("entries", []) if isinstance(data, dict) else []
        return [e for e in entries if isinstance(e, dict) and "key" in e]

    def save(self):
        """Write the history to disk.

        Returns:
            bool: True on success.
        """
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "entries": self.entries}, fh, indent=1)
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    def sorted_entries(self):
        """Records sorted by date.

        Returns:
            list[dict]: Records, oldest first.
        """
        return sorted(self.entries, key=lambda e: e.get("date", ""))

    def record(self, entry):
        """Add or replace a record and save.

        Args:
            entry (dict): Output of :func:`history_entry`.

        Returns:
            dict: ``status`` for sigma and for the mean single-ion area
            against the limits of the other records (see :func:`classify`),
            plus the ``limits`` used.
        """
        others = [e for e in self.entries if e.get("key") != entry["key"]]
        sigma_limits = control_limits([e.get("sigma") for e in others])
        area_limits = control_limits([e.get("average_single_ion_area") for e in others])
        result = {
            "sigma": classify(entry.get("sigma"), sigma_limits),
            "average_single_ion_area": classify(entry.get("average_single_ion_area"), area_limits),
            "limits": {"sigma": sigma_limits, "average_single_ion_area": area_limits},
            "n_previous": len(others),
        }
        self.entries = others + [entry]
        self.save()
        return result

    def remove(self, key):
        """Delete a record by key and save.

        Args:
            key (str): Record key.

        Returns:
            bool: True when a record was removed.
        """
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.get("key") != key]
        if len(self.entries) != before:
            self.save()
            return True
        return False
