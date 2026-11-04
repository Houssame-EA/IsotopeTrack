"""Interferences seen in the resolved mass spectrum of Nu runs.

Nu Instruments software writes a few raw digitizer snapshots per run, and
their sum is a resolved spectrum (see :mod:`loading.nu_raw_spectrum`). Around
each selected isotope this module looks for two signs that something other
than the isotope adds counts to its integration window:

* the peak sits off the isotope's exact mass, toward a known interfering
  species. Every peak of a run shares the run's mass calibration error, so
  the median offset of all well-measured peaks is removed first and only what
  is left counts as a shift;
* a second, partly resolved peak sits inside or right next to the
  integration window.

Candidate species come from the interference database
(:mod:`widget.interference_database`), plus isobars and doubly charged ions
built from the isotope table.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field

import numpy as np

from loading.nu_raw_spectrum import (
    integration_window, peak_check, read_nu_raw_spectrum, spectrum_masses)

_itk_log = logging.getLogger("IsotopeTrack.results.insights.spectrum")

SEARCH_HALF_WIDTH = 0.35
"""Distance from the exact mass, in Da, searched for the isotope's own peak."""

ZOOM_HALF_WIDTH = 0.5
"""Half width, in Da, of the spectrum kept for the explained figure."""

MIN_IONS = 200
"""Ions a peak needs before its centre and shape are trusted."""

MIN_PEAKS_FOR_OFFSET = 3
"""Well-measured peaks needed to estimate the run's mass calibration offset."""

SHIFT_MIN_DA = 0.006
"""Smallest shift from the exact mass, after the run offset, worth reporting."""

SHIFT_MIN_WIDTHS = 0.20
"""Smallest shift, as a fraction of the peak width (FWHM), worth reporting."""

NEIGHBOUR_MIN_HEIGHT = 0.10
"""Smallest height of a second peak, as a fraction of the main peak."""

NEIGHBOUR_MIN_SEPARATION = 0.6
"""Smallest distance between the two peaks, in peak widths (FWHM)."""

NEIGHBOUR_MAX_VALLEY = 0.85
"""Highest dip between the two peaks, as a fraction of the smaller one."""

NEIGHBOUR_MIN_IONS = 30
"""Ions the second peak needs before it is reported."""

FIGURE_POINTS = 400
"""Largest number of points kept per sample for the explained figure."""

FIGURE_ZOOM_WIDTHS = 4.0
"""Peak widths shown on each side of the integration window in the explained figure."""

OFFSET_NOTE_DA = 0.0005
"""Smallest run offset worth mentioning on the card."""

_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


@dataclass
class SpectrumSource:
    """What one sample offers for the spectrum checks.

    Attributes:
        sample: Sample name.
        run_info: Nu ``run.info`` with ``MassCalCoefficients``.
        folder: Nu run folder holding the ``.raw`` snapshots.
        entry: Spectrum already read by the main window, ``{'spectrum',
            'n_snapshots'}``; read from *folder* when ``None``.
    """

    sample: str
    run_info: dict
    folder: str | None = None
    entry: dict | None = None


@dataclass
class Peak:
    """The measured peak of one isotope in one sample.

    Attributes:
        sample: Sample name.
        label: Isotope label, e.g. ``"56Fe"``.
        exact: Exact mass of the isotope.
        centre: Measured peak centre (m/z).
        width: Peak width (FWHM, Da).
        ions: Ions in the integration window, or ``None`` without a single
            ion area.
        window: Integration window ``(start, end)`` in m/z, or ``None``.
        mz: m/z of the zoomed spectrum around the isotope.
        y: Signal of the zoomed spectrum, in ions per bin when the run has a
            single ion area.
    """

    sample: str
    label: str
    exact: float
    centre: float
    width: float
    ions: float | None
    window: tuple | None
    mz: np.ndarray = field(repr=False)
    y: np.ndarray = field(repr=False)

    @property
    def trusted(self) -> bool:
        """Whether enough ions make the peak's centre and shape meaningful."""
        return self.ions is None or self.ions >= MIN_IONS


_SPECTRA: dict = {}
_SPECTRA_LOCK = threading.Lock()


def load(source: SpectrumSource) -> dict | None:
    """Return a sample's resolved spectrum, reading its snapshots once per folder.

    Args:
        source: The sample's spectrum source.

    Returns:
        ``{'spectrum', 'n_snapshots'}``, or ``None`` without snapshots.
    """
    if source.entry:
        return source.entry
    if not source.folder:
        return None
    key = str(source.folder)
    with _SPECTRA_LOCK:
        if key in _SPECTRA:
            return _SPECTRA[key]
    try:
        entry = read_nu_raw_spectrum(source.folder)
    except Exception:
        _itk_log.exception("Could not read the raw spectrum of %s", source.sample)
        entry = None
    with _SPECTRA_LOCK:
        _SPECTRA[key] = entry
    return entry


_ISOTOPES: list | None = None


def isotope_table() -> list[dict]:
    """Return every natural isotope as ``{'element', 'number', 'mass'}``."""
    global _ISOTOPES
    if _ISOTOPES is None:
        try:
            from utils.isobaric_correction import _find_table_path
            with open(_find_table_path(), encoding="utf-8") as fp:
                rows = json.load(fp)
        except Exception:
            _itk_log.exception("Could not read the isotope table")
            rows = []
        out = []
        for row in rows:
            try:
                number = int(str(row["isotope_label"]).split()[-1])
                out.append({"element": row["element"], "number": number,
                            "mass": float(row["mass"]),
                            "abundance": float(row.get("abundance") or 0)})
            except (KeyError, ValueError, TypeError):
                continue
        _ISOTOPES = out
    return _ISOTOPES


def isotope_name(number: int, element: str, charge: str = "⁺") -> str:
    """Write an ion as ``⁵⁶Fe⁺``."""
    return f"{str(number).translate(_SUPERSCRIPT)}{element}{charge}"


def known_species(label: str, exact: float) -> list[tuple[str, float, str]]:
    """Known species that land within one nominal mass of an isotope.

    Args:
        label: Isotope label, e.g. ``"56Fe"``.
        exact: Exact mass of the isotope.

    Returns:
        ``(species, m/z, kind)`` for every polyatomic ion, isobar and doubly
        charged ion at the isotope's nominal mass, other than the isotope
        itself.
    """
    from results.insights.discovery import mass_symbol
    from widget.interference_database import get_interferences_for_mass
    nominal, symbol = mass_symbol(label)
    if nominal is None:
        nominal = int(round(exact))
    out = []
    for entry in get_interferences_for_mass(nominal):
        mz = entry.get("exact_mass")
        if mz is None:
            continue
        if entry.get("type") == "doubly_charged":
            continue
        out.append((entry["species"], float(mz), entry.get("type", "polyatomic")))
    for iso in isotope_table():
        if iso["abundance"] <= 0 or iso["element"] == symbol:
            continue
        if iso["number"] == nominal:
            out.append((isotope_name(iso["number"], iso["element"]), iso["mass"], "isobaric"))
        elif iso["number"] == 2 * nominal:
            out.append((isotope_name(iso["number"], iso["element"], "²⁺"), iso["mass"] / 2.0,
                        "doubly_charged"))
    seen, unique = set(), []
    for species, mz, kind in out:
        if species not in seen:
            seen.add(species)
            unique.append((species, mz, kind))
    return unique


def measure(source: SpectrumSource, isotopes) -> list[Peak]:
    """Measure the peak of every isotope in one sample's spectrum.

    Args:
        source: The sample's spectrum source.
        isotopes: ``(label, exact mass)`` pairs.

    Returns:
        One :class:`Peak` per isotope with a peak, empty without a spectrum.
    """
    run_info = source.run_info or {}
    if "MassCalCoefficients" not in run_info:
        return []
    entry = load(source)
    if not entry:
        return []
    spectrum = np.asarray(entry["spectrum"], dtype=np.float64)
    masses = spectrum_masses(run_info, len(spectrum))
    area = run_info.get("AverageSingleIonArea")
    area = float(area) if area and float(area) > 0 else None
    signal = spectrum / area if area else spectrum
    peaks = []
    for label, exact in isotopes:
        window = integration_window(run_info, exact)
        win = window["window"] if window else None
        check = peak_check(masses, spectrum, exact, win, half_width=SEARCH_HALF_WIDTH,
                           single_ion_area=area)
        if check is None:
            continue
        zoom = np.abs(masses - exact) <= ZOOM_HALF_WIDTH
        peaks.append(Peak(source.sample, label, float(exact), check["centre"], check["width"],
                          check["ions"], win, masses[zoom], signal[zoom]))
    return peaks


def run_offset(peaks: list[Peak]) -> float:
    """The run's mass calibration offset: the median shift of its trusted peaks.

    Returns 0 when too few peaks are trusted to tell calibration from
    interference.
    """
    shifts = [p.centre - p.exact for p in peaks if p.trusted]
    if len(shifts) < MIN_PEAKS_FOR_OFFSET:
        return 0.0
    return float(np.median(shifts))


def nearest_species(species, target: float, exact: float, width: float, side: float = 0.0):
    """The known species closest to *target*, within one peak width of it.

    Args:
        species: ``(name, m/z, kind)`` candidates.
        target: m/z where the extra signal sits.
        exact: Exact mass of the isotope.
        width: Peak width (FWHM).
        side: When non-zero, only species on this side of *exact* qualify.

    Returns:
        The closest ``(name, m/z, kind)``, or ``None``.
    """
    best = None
    for name, mz, kind in species:
        if side and np.sign(mz - exact) != np.sign(side):
            continue
        d = abs(mz - target)
        if d <= max(width, 0.01) and (best is None or d < best[0]):
            best = (d, (name, mz, kind))
    return best[1] if best else None


def _smooth(y: np.ndarray) -> np.ndarray:
    """Three-point running mean, to keep counting noise from making extra maxima."""
    if y.size < 3:
        return y
    return np.convolve(y, np.ones(3) / 3.0, mode="same")


def find_neighbour(peak: Peak, offset: float) -> dict | None:
    """Find a second, partly resolved peak next to an isotope's peak.

    Args:
        peak: The isotope's measured peak.
        offset: The run's mass calibration offset.

    Returns:
        ``{'centre', 'height', 'ions'}`` of the strongest qualifying neighbour,
        with *centre* corrected for the run offset and *height* relative to
        the main peak, or ``None``.
    """
    mz, y = peak.mz, _smooth(peak.y)
    if y.size < 5:
        return None
    main = int(np.argmin(np.abs(mz - peak.centre)))
    top = y[main]
    if top <= 0:
        return None
    lo_edge = (peak.window[0] if peak.window else peak.centre - 2 * peak.width) - peak.width
    hi_edge = (peak.window[1] if peak.window else peak.centre + 2 * peak.width) + peak.width
    is_max = np.r_[False, (y[1:-1] >= y[:-2]) & (y[1:-1] > y[2:]), False]
    step = float(np.median(np.diff(mz))) if mz.size > 1 else 0.0
    in_ions = peak.ions is not None
    best = None
    for i in np.flatnonzero(is_max):
        if i == main or not (lo_edge <= mz[i] <= hi_edge):
            continue
        if abs(mz[i] - peak.centre) < NEIGHBOUR_MIN_SEPARATION * peak.width:
            continue
        height = y[i] / top
        if height < NEIGHBOUR_MIN_HEIGHT or height >= 1.0:
            continue
        a, b = sorted((i, main))
        if y[a:b + 1].min() > NEIGHBOUR_MAX_VALLEY * y[i]:
            continue
        half = max(int(round(peak.width / max(step, 1e-12) / 2)), 1)
        ions = None
        if in_ions:
            ions = float(np.clip(peak.y[max(i - half, 0):i + half + 1], 0, None).sum())
            if ions < NEIGHBOUR_MIN_IONS:
                continue
        if best is None or height > best["height"]:
            best = {"centre": float(mz[i] - offset), "height": float(height), "ions": ions}
    return best


def thin(mz: np.ndarray, y: np.ndarray, n: int = FIGURE_POINTS) -> tuple[list, list]:
    """Keep at most *n* points of a zoomed spectrum, keeping every local maximum."""
    if mz.size <= n:
        return [round(float(v), 5) for v in mz], [round(float(v), 4) for v in y]
    step = int(np.ceil(mz.size / n))
    idx = []
    for start in range(0, mz.size, step):
        block = slice(start, min(start + step, mz.size))
        idx.append(start + int(np.argmax(y[block])))
    return ([round(float(mz[i]), 5) for i in idx], [round(float(y[i]), 4) for i in idx])


def check_sample(source: SpectrumSource, isotopes) -> list[dict]:
    """Run both spectrum checks on every isotope of one sample.

    Args:
        source: The sample's spectrum source.
        isotopes: ``(label, exact mass)`` pairs.

    Returns:
        One dict per problem found, with ``kind`` set to ``"shift"`` or
        ``"neighbour"``, the :class:`Peak`, the run ``offset`` and the
        likely ``species`` (or ``None``).
    """
    peaks = measure(source, isotopes)
    offset = run_offset(peaks)
    found = []
    for p in peaks:
        if not p.trusted:
            continue
        species = known_species(p.label, p.exact)
        shift = p.centre - offset - p.exact
        if abs(shift) >= max(SHIFT_MIN_DA, SHIFT_MIN_WIDTHS * p.width):
            likely = nearest_species(species, p.centre - offset, p.exact, p.width, side=shift)
            found.append({"kind": "shift", "peak": p, "offset": offset, "shift": shift,
                          "species": likely})
        neighbour = find_neighbour(p, offset)
        if neighbour is not None:
            likely = nearest_species(species, neighbour["centre"], p.exact, p.width)
            inside = bool(p.window and p.window[0] <= neighbour["centre"] + offset <= p.window[1])
            found.append({"kind": "neighbour", "peak": p, "offset": offset,
                          "neighbour": neighbour, "inside": inside, "species": likely})
    return found


SOURCES_KEY = "spectrum_sources"
"""Key in ``AnalysisContext.cache`` holding the spectrum sources of the scope."""


def _mda(value: float) -> str:
    """A mass difference in mDa, signed."""
    return f"{value * 1000:+.0f} mDa"


def _figure_facts(kind: str, items: list[dict], species, units: str) -> dict:
    """What the explained figure needs: each sample's zoomed spectrum and the marks."""
    first = items[0]["peak"]
    traces = {}
    for f in items:
        p = f["peak"]
        mz, y = thin(p.mz - f["offset"], p.y)
        traces[p.sample] = {"mz": mz, "y": y}
    marks = [{"mz": round(mz, 5), "label": name} for name, mz, _k in species]
    window = ([round(v - items[0]["offset"], 5) for v in first.window]
              if first.window else [])
    points = window + [first.exact] + [m["mz"] for m in marks]
    pad = FIGURE_ZOOM_WIDTHS * first.width
    zoom = [round(max(min(points) - pad, first.exact - ZOOM_HALF_WIDTH), 4),
            round(min(max(points) + pad, first.exact + ZOOM_HALF_WIDTH), 4)]
    return {"kind": kind, "label": first.label, "exact": first.exact, "window": window,
            "marks": marks, "traces": traces, "units": units, "zoom": zoom,
            "focus": first.sample}


def _shift_card(rr, label: str, items: list[dict], n_samples: int, units: str):
    """Card for an isotope whose peak sits off its exact mass."""
    from results.insights.robustness import Evidence
    items.sort(key=lambda f: -abs(f["shift"]))
    top = items[0]
    p = top["peak"]
    species = top["species"]
    where = "above" if top["shift"] > 0 else "below"
    title = f"{label} peak sits {abs(top['shift']) * 1000:.0f} mDa {where} its mass"
    if species:
        title += f", on {species[0]}"
    offset_note = (f" (after removing the run's mass calibration offset of "
                   f"{_mda(top['offset'])})" if abs(top["offset"]) >= OFFSET_NOTE_DA else "")
    reasoning = (f"In the resolved spectrum of {p.sample} the {label} peak centre is m/z "
                 f"{p.centre - top['offset']:.3f}, not {p.exact:.3f}{offset_note}.")
    if species:
        reasoning += (f" {species[0]} falls at m/z {species[1]:.3f}, so part of the {label} "
                      "signal is likely that ion, which raises its background and detection "
                      "threshold.")
    else:
        reasoning += (" No known species sits there; check the mass calibration and the "
                      "integration window.")
    samples = [f["peak"].sample for f in items]
    if n_samples > 1:
        reasoning += f" Seen in {len(samples)} of {n_samples} samples with a spectrum."
    score = (0.45 + 0.35 * min(abs(top["shift"]) / max(p.width, 1e-6), 1.0)
             + (0.1 if species else 0.0))
    details = [("Isotope", label), ("Exact mass", f"{p.exact:.4f}"),
               ("Peak centre", f"{p.centre - top['offset']:.4f}"),
               ("Shift", _mda(top["shift"])), ("Peak width (FWHM)", f"{p.width * 1000:.0f} mDa"),
               ("Run calibration offset", _mda(top["offset"])),
               ("Likely species", f"{species[0]} (m/z {species[1]:.4f})" if species else "none known"),
               ("Samples", ", ".join(samples))]
    if p.ions is not None:
        details.insert(5, ("Ions in window", f"{p.ions:,.0f}"))
    s = rr.Suggestion(
        title=title, reasoning=reasoning, category="interference",
        confidence=min(score, 0.92), node_type="spectrum_view", config={},
        elements=(label,), samples=tuple(samples), explain_key="spectrum_shift",
        details=details,
        facts={"spectrum": _figure_facts("shift", items,
                                         [species] if species else [], units)})
    s.evidence = Evidence(effect=_mda(top["shift"]))
    return s


def _neighbour_card(rr, label: str, items: list[dict], n_samples: int, units: str):
    """Card for an isotope with a second peak next to its own."""
    from results.insights.robustness import Evidence
    items.sort(key=lambda f: -f["neighbour"]["height"])
    top = items[0]
    p, nb, species = top["peak"], top["neighbour"], top["species"]
    title = f"Second peak next to {label}"
    if species:
        title += f", at {species[0]}"
    place = "inside" if top["inside"] else "just outside"
    reasoning = (f"In the resolved spectrum of {p.sample} a peak at m/z {nb['centre']:.3f} "
                 f"reaches {nb['height']:.0%} of the {label} peak, {place} its integration "
                 "window.")
    if species:
        reasoning += f" It matches {species[0]} (m/z {species[1]:.3f})"
        reasoning += (f", which adds counts to {label}." if top["inside"]
                      else "; a wider window would take in its counts.")
    else:
        reasoning += " No known species sits there."
    samples = [f["peak"].sample for f in items]
    if n_samples > 1:
        reasoning += f" Seen in {len(samples)} of {n_samples} samples with a spectrum."
    score = 0.4 + 0.4 * min(nb["height"] / 0.5, 1.0) + (0.1 if top["inside"] else 0.0)
    details = [("Isotope", label), ("Main peak", f"{p.centre - top['offset']:.4f}"),
               ("Second peak", f"{nb['centre']:.4f}"),
               ("Height of second peak", f"{nb['height']:.0%}"),
               ("In integration window", "yes" if top["inside"] else "no"),
               ("Likely species", f"{species[0]} (m/z {species[1]:.4f})" if species else "none known"),
               ("Samples", ", ".join(samples))]
    if nb.get("ions") is not None:
        details.insert(4, ("Ions in second peak", f"{nb['ions']:,.0f}"))
    marks = [species] if species else [(f"m/z {nb['centre']:.3f}", nb["centre"], "")]
    s = rr.Suggestion(
        title=title, reasoning=reasoning, category="interference",
        confidence=min(score, 0.92), node_type="spectrum_view", config={},
        elements=(label,), samples=tuple(samples), explain_key="spectrum_neighbour",
        details=details, facts={"spectrum": _figure_facts("neighbour", items, marks, units)})
    s.evidence = Evidence(effect=f"{nb['height']:.0%} height")
    return s


def analyse(ctx, progress=None) -> list:
    """Insights detector: spectrum interferences on the scope's isotopes.

    Reads the spectrum sources the panel stored in ``ctx.cache`` under
    :data:`SOURCES_KEY`; finds nothing without them.

    Args:
        ctx: Analysis context over the whole scope.
        progress: Optional callable receiving status strings.

    Returns:
        One card per isotope and kind of problem, naming every sample where
        it is seen, strongest first.
    """
    from results.insights import engine as rr
    sources = ctx.cache.get(SOURCES_KEY) or {}
    isotopes = [(label, exact) for label, exact in sources.get("isotopes", ())
                if label in ctx.matrix and ctx.involves(label)]
    if ctx.scope.labels:
        isotopes = [(label, exact) for label, exact in isotopes if label in ctx.scope.labels]
    wanted = set(ctx.sample_names)
    samples = [s for s in sources.get("samples", ()) if s.sample in wanted]
    if not isotopes or not samples:
        return []
    rr._say(progress, "Checking the resolved spectra for interferences…")
    groups: dict = {}
    measured = 0
    units = "a.u."
    for source in samples:
        try:
            found = check_sample(source, isotopes)
        except Exception:
            _itk_log.exception("Spectrum check failed for %s", source.sample)
            continue
        if source.entry or load(source):
            measured += 1
        if (source.run_info or {}).get("AverageSingleIonArea"):
            units = "ions / bin"
        for f in found:
            groups.setdefault((f["kind"], f["peak"].label), []).append(f)
    out = []
    for (kind, label), items in groups.items():
        make = _shift_card if kind == "shift" else _neighbour_card
        out.append(make(rr, label, items, measured, units))
    out.sort(key=lambda s: -s.confidence)
    return out[:ctx.cap(6)]
