"""Blanker windows and autoblank periods of a Nu Vitesse acquisition.

Qt-free helpers used to tell the user which masses the instrument blanked:

* fixed windows set by the method (``Blanker<N>EdgeTimesNs`` in ``run.info``),
* extra windows closed by autoblanking during the run (``.autob`` files),
  with the fraction of the run each one lasted.

Edge times are converted to m/z with the blanker mass calibration
(``BlMassCalStartCoef`` / ``BlMassCalEndCoef``). With these coefficients the
start of a blanked window follows the end calibration and its end follows the
start calibration, which reproduces the method's ``SkipMassRanges``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

_log = logging.getLogger("IsotopeTrack.loading.nu_blanking")

TICK_NS = 1.25
MASS_TOL = 0.5


def edges_to_windows(edges_ns, start_coef, end_coef):
    """Blanked m/z windows from a list of blanker edge times.

    Args:
        edges_ns (array-like): Edge times in ns, in on/off pairs.
        start_coef (tuple[float, float]): ``BlMassCalStartCoef``.
        end_coef (tuple[float, float]): ``BlMassCalEndCoef``.

    Returns:
        list[tuple[float, float]]: Sorted (low, high) m/z windows.
    """
    e = np.asarray(edges_ns, dtype=float)
    out = []
    for i in range(0, len(e) - 1, 2):
        lo = (end_coef[0] + end_coef[1] * e[i]) ** 2
        hi = (start_coef[0] + start_coef[1] * e[i + 1]) ** 2
        if hi > lo:
            out.append((float(lo), float(hi)))
    return sorted(out)


def subtract_windows(windows, remove):
    """Parts of ``windows`` not covered by any window in ``remove``.

    Args:
        windows (list[tuple[float, float]]): Windows to trim.
        remove (list[tuple[float, float]]): Windows to cut out.

    Returns:
        list[tuple[float, float]]: Remaining pieces, sorted.
    """
    pieces = list(windows)
    for rlo, rhi in remove:
        nxt = []
        for lo, hi in pieces:
            if rhi <= lo or rlo >= hi:
                nxt.append((lo, hi))
                continue
            if lo < rlo:
                nxt.append((lo, rlo))
            if rhi < hi:
                nxt.append((rhi, hi))
        pieces = nxt
    return sorted(p for p in pieces if p[1] - p[0] > 1e-6)


def _in_windows(mass, windows):
    return any(lo <= mass <= hi for lo, hi in windows)


def read_nu_blanking(folder):
    """Fixed and autoblank windows of one Nu Vitesse folder.

    Args:
        folder (str | Path): Acquisition folder with ``run.info``.

    Returns:
        dict | None: ``fixed`` (list of windows), ``auto`` (list of
        ``(low, high, n_acquisitions)``) and ``total_acquisitions``; None
        when the folder has no usable ``run.info``.
    """
    root = Path(folder)
    try:
        with open(root / "run.info", encoding="utf-8", errors="replace") as fp:
            info = json.load(fp)
        seg = info["SegmentInfo"][0]
        sc, ec = info["BlMassCalStartCoef"], info["BlMassCalEndCoef"]
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None
    used = info.get("BlankerUsed", 1) or 1
    edges = seg.get(f"Blanker{used}EdgeTimesNs") or seg.get("Blanker1EdgeTimesNs") or []
    fixed = edges_to_windows(edges, sc, ec)
    total = int(info.get("TotalAcquisitions") or 0)
    acc = int(info.get("NumAccumulations1", 1) or 1) * int(info.get("NumAccumulations2", 1) or 1)

    auto = []
    try:
        from loading.vitesse_loading import collect_nu_autob_data
        with open(root / "autob.index", encoding="utf-8", errors="replace") as fp:
            index = json.load(fp)
        events = collect_nu_autob_data(root, index)
    except Exception:
        _log.debug("No autoblank data in %s", root)
        events = []
    start = None
    for ev in events:
        kind = int(ev["type"][0])
        if kind == 0 and start is None:
            start = ev
        elif kind == 1 and start is not None:
            n = int(start["num_edges"][0])
            trip = edges_to_windows(start["edges"][0][:n] * TICK_NS, sc, ec)
            a0 = int(start["acq_number"][0] // acc)
            a1 = int(ev["acq_number"][0] // acc)
            for lo, hi in subtract_windows(trip, fixed):
                auto.append((lo, hi, max(0, a1 - a0)))
            start = None
    return {"fixed": fixed, "auto": auto, "total_acquisitions": total}


def mass_flags(masses, blanking):
    """Blanking state of each mass.

    Args:
        masses (array-like): m/z values.
        blanking (dict | None): Output of :func:`read_nu_blanking`.

    Returns:
        dict: ``{mass: {'blanked': bool, 'autoblank_fraction': float}}``.
    """
    out = {}
    if not blanking:
        return out
    total = blanking.get("total_acquisitions") or 0
    for m in masses:
        m = float(m)
        n_auto = sum(n for lo, hi, n in blanking.get("auto", []) if lo <= m <= hi)
        out[m] = {
            "blanked": _in_windows(m, blanking.get("fixed", [])),
            "autoblank_fraction": (n_auto / total) if total else 0.0,
        }
    return out


def isotope_flag(isotope_mass, flags, tol=MASS_TOL):
    """Blanking state of the measured mass closest to an isotope.

    Args:
        isotope_mass (float): Isotope mass.
        flags (dict): Output of :func:`mass_flags`.
        tol (float): Largest mass difference.

    Returns:
        dict | None: The matching entry, or None when no mass is close.
    """
    best, diff = None, tol
    for m, f in flags.items():
        d = abs(m - isotope_mass)
        if d <= diff:
            best, diff = f, d
    return best


def windows_text(windows, low=1.0, high=300.0):
    """Short text such as ``'m/z 27–33, 36.5–60'`` for windows inside a span.

    Args:
        windows (list[tuple]): Windows; extra tuple items are ignored.
        low (float): Ignore windows that start below this.
        high (float): Ignore windows that end above this.

    Returns:
        str: Text, empty when no window is inside the span.
    """
    parts = [f"{w[0]:.1f}–{w[1]:.1f}" for w in windows if w[0] >= low and w[1] <= high]
    return ("m/z " + ", ".join(parts)) if parts else ""
