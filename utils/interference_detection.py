"""
Blind interference detection for spICP-ToF-MS spectra.

Pure logic: numpy only, no GUI. Element data (isotope masses and abundances)
is passed in as the same list of element dicts PeriodicTableWidget provides.

The sample composition is not needed. It is found from the spectrum itself:

1. ``nominal_spectrum`` sums the signal of every nominal mass, from the
   integrated data or from the resolved ``.raw`` spectrum.
2. ``identify_elements`` explains that spectrum as a non-negative sum of
   element patterns. Each pattern holds the natural isotopes, the oxide MO+
   at +16 and the doubly charged ion M2+ at half mass, with rates from
   ``data/interference_reference.json`` (measured with single-element
   standards). The oxide level of each element is fitted per sample,
   because it changes with plasma conditions. An element is kept only when
   it is statistically significant (Poisson), and, when a blank is given,
   significantly above the blank; elements only as high as in the blank are
   reported as background.
3. ``contributions`` splits the signal at one nominal mass between the
   selected isotope and every other species of the identified elements.
4. ``mass_offset`` and ``position_match`` use the resolved spectrum: after
   the calibration offset is measured on clean peaks, the peak centre tells
   which species of that nominal mass really forms the peak.
5. ``check_isotope`` combines both into rows for the Spectrum view.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

_itk_log = logging.getLogger("IsotopeTrack.utils.interference_detection")

OXYGEN = 15.99491
REFERENCE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "data", "interference_reference.json")
NOT_ANALYTES = frozenset({"H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Si", "P",
                          "S", "Cl", "Ar", "Kr", "Xe", "Rn"})
NOBLE_GASES = frozenset({"He", "Ne", "Ar", "Kr", "Xe", "Rn"})
PLASMA_SPECIES = frozenset({"Ar", "O", "N", "H", "C"})
PLASMA_MASSES = frozenset({23, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 52, 54,
                           56, 57, 76, 78, 80, 81, 82})
OXIDE_SCALES = (0.3, 0.45, 0.6, 0.75, 0.9, 1.0, 1.2, 1.5)
Z_MIN = 5.0
MODEL_ERROR = 0.05
MOLECULAR_ERROR = 0.5
MIN_ELEMENT_IONS = 20.0
MIN_IONS = 50
TIE_DA = 0.005
SUPERSCRIPT = str.maketrans("0123456789+", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺")
_ELEMENTS: Optional[List[dict]] = None


def sup(number) -> str:
    """Return a number written in superscript digits."""
    return str(number).translate(SUPERSCRIPT)


def load_reference(path: Optional[str] = None) -> dict:
    """Read the measured MO+, MOH+, M2+ and MH+ rates.

    Args:
        path: JSON file; the bundled reference when None.

    Returns:
        dict: ``{'default': {...}, 'elements': {symbol: {kind: fraction}}}``.
    """
    try:
        with open(path or REFERENCE_FILE, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        data.setdefault("default", {"MO": 0.02, "M2+": 0.0})
        data.setdefault("elements", {})
        return data
    except (OSError, ValueError):
        _itk_log.exception("Could not read the interference reference")
        return {"default": {"MO": 0.02, "M2+": 0.0}, "elements": {}}


def isotope_table(elements: Sequence[dict]) -> Dict[str, List[Tuple[int, float, float]]]:
    """Return ``{symbol: [(nominal, exact mass, fraction), ...]}`` for natural isotopes."""
    table = {}
    for el in elements or []:
        isos = [(int(round(i["mass"])), float(i["mass"]), float(i.get("abundance", 0)) / 100.0)
                for i in el.get("isotopes", []) if float(i.get("abundance", 0)) > 0]
        if isos:
            table[el["symbol"]] = isos
    return table


def nominal_spectrum(masses, values) -> Dict[int, float]:
    """Sum signals by nominal mass.

    Args:
        masses: Channel masses.
        values: Mean signal of each channel.

    Returns:
        dict: ``{nominal mass: signal}``.
    """
    out: Dict[int, float] = {}
    for m, v in zip(np.asarray(masses, dtype=float), np.asarray(values, dtype=float)):
        if np.isfinite(v):
            out[int(round(m))] = out.get(int(round(m)), 0.0) + float(v)
    return out


def nominal_spectrum_from_raw(masses, spectrum, windows, single_ion_area=None) -> Dict[int, float]:
    """Sum a resolved spectrum inside each integration window.

    Args:
        masses (np.ndarray): m/z of every spectrum point.
        spectrum (np.ndarray): Summed signal.
        windows (list): ``(start, end)`` m/z of every integration region.
        single_ion_area (float | None): Converts the signal to ions.

    Returns:
        dict: ``{nominal mass: signal}``.
    """
    masses = np.asarray(masses, dtype=float)
    spectrum = np.clip(np.asarray(spectrum, dtype=float), 0, None)
    scale = float(single_ion_area) if single_ion_area and single_ion_area > 0 else 1.0
    out: Dict[int, float] = {}
    for lo, hi in windows or []:
        sel = (masses >= lo) & (masses <= hi)
        if sel.any():
            out[int(round(0.5 * (lo + hi)))] = float(spectrum[sel].sum() / scale)
    return out


def _nnls(A: np.ndarray, b: np.ndarray, max_iter: int = 5000) -> np.ndarray:
    """Solve min ||Ax - b|| with x >= 0 (Lawson-Hanson active set)."""
    n = A.shape[1]
    passive = np.zeros(n, dtype=bool)
    x = np.zeros(n)
    w = A.T @ (b - A @ x)
    for _ in range(max_iter):
        if passive.all() or w[~passive].max() <= 1e-10:
            break
        passive[int(np.argmax(np.where(passive, -np.inf, w)))] = True
        while True:
            z = np.zeros(n)
            z[passive] = np.linalg.lstsq(A[:, passive], b, rcond=None)[0]
            if (z[passive] > 0).all():
                x = z
                break
            neg = passive & (z <= 0)
            alpha = np.min(x[neg] / (x[neg] - z[neg]))
            x = x + alpha * (z - x)
            passive &= x > 1e-12
        w = A.T @ (b - A @ x)
    return x


def _rate(reference: dict, symbol: str, kind: str) -> float:
    """Return the reference rate of one species, or the default."""
    value = reference.get("elements", {}).get(symbol, {}).get(kind)
    if value is None:
        value = reference.get("default", {}).get(kind, 0.0)
    return max(float(value or 0.0), 0.0)


@dataclass
class Identification:
    """Elements found in one spectrum and how they explain it.

    ``amounts`` holds the elements significantly above zero, or above the
    blank when one was given. ``background`` lists elements that are present
    but not above the blank. ``significance`` is the fitted amount divided by
    its Poisson uncertainty.
    """

    amounts: Dict[str, float]
    oxide_scale: float
    measured: Dict[int, float]
    predicted: Dict[int, float]
    species: Dict[int, List[Tuple[str, str, str, float]]] = field(default_factory=dict)
    significance: Dict[str, float] = field(default_factory=dict)
    background: List[str] = field(default_factory=list)
    blank_used: bool = False
    oxide_scales: Dict[str, float] = field(default_factory=dict)

    def residual(self, nominal: int) -> float:
        """Signal at a nominal mass that no identified species explains."""
        return self.measured.get(nominal, 0.0) - self.predicted.get(nominal, 0.0)


def _species_signals(symbol, amount, isotopes, reference, oxide_scale, usable):
    """Yield ``(nominal, label, kind, signal)`` for every species of one element."""
    mo = _rate(reference, symbol, "MO") * oxide_scale
    m2 = _rate(reference, symbol, "M2+")
    for nominal, _mass, frac in isotopes:
        if nominal in usable:
            yield nominal, f"{sup(nominal)}{symbol}", "atom", amount * frac
        if mo > 0 and nominal + 16 in usable:
            yield nominal + 16, f"{sup(nominal)}{symbol}¹⁶O", "oxide", amount * frac * mo
        if m2 > 0 and nominal % 2 == 0 and nominal // 2 in usable:
            yield nominal // 2, f"{sup(nominal)}{symbol}²⁺", "doubly charged", amount * frac * m2


def _design_parts(usable, table, symbols, reference):
    """Return the element patterns split into a fixed part and the oxide part.

    The full matrix for oxide scales ``k`` (one per element) is
    ``fixed + oxide * k``; the fixed part holds the isotopes and the doubly
    charged ions, the oxide part the MO+ at a scale of 1.
    """
    row = {m: i for i, m in enumerate(usable)}
    fixed = np.zeros((len(usable), len(symbols)))
    oxide = np.zeros((len(usable), len(symbols)))
    for j, s in enumerate(symbols):
        for nominal, _label, kind, value in _species_signals(s, 1.0, table[s], reference, 1.0, row):
            (oxide if kind == "oxide" else fixed)[row[nominal], j] += value
    return fixed, oxide


def _fit(values, variance, usable, table, symbols, reference, molecular_error=0.0,
         scale_variance=None, refine=True):
    """Fit element patterns to a spectrum and return the oxide scales, amounts and z-scores.

    The oxide scale is first chosen for all elements together, then refined
    element by element, because each element forms oxides to a different
    extent in each sample.

    Args:
        values (np.ndarray): Signal at each usable mass, in ions.
        variance (np.ndarray): Poisson variance of each value.
        usable (list): Nominal masses of the rows.
        table (dict): Isotopes of each candidate element.
        symbols (list): Candidate elements, one column each.
        reference (dict): Molecular ion rates.
        molecular_error (float): Relative uncertainty of the predicted oxide
            and doubly charged signal; masses dominated by them weigh less.
        scale_variance (np.ndarray | None): Variance used to choose the oxide
            scales, the pure counting noise; ``variance`` when None.
        refine (bool): Refine the oxide scale of each strong element.

    Returns:
        tuple: ``(oxide scale of each element, amounts array, z-score array)``.
    """
    fixed, oxide = _design_parts(usable, table, symbols, reference)
    choose = 1.0 / np.sqrt(variance if scale_variance is None else scale_variance)

    def solve(scales):
        A = fixed + oxide * scales
        x = _nnls(A * choose[:, None], values * choose)
        return float(np.sum(((A @ x - values) * choose) ** 2)), x

    best = None
    for scale in OXIDE_SCALES:
        scales = np.full(len(symbols), scale)
        cost, x = solve(scales)
        if best is None or cost < best[0]:
            best = (cost, scales, x)
    cost, scales, x = best
    strong = (x * fixed.max(axis=0) >= MIN_ELEMENT_IONS) & oxide.any(axis=0)
    for j in np.flatnonzero(strong) if refine else []:
        for candidate in OXIDE_SCALES:
            if candidate == scales[j]:
                continue
            trial = scales.copy()
            trial[j] = candidate
            trial_cost, trial_x = solve(trial)
            if trial_cost < cost:
                cost, scales, x = trial_cost, trial, trial_x
    A = fixed + oxide * scales
    var = np.asarray(variance, dtype=float)
    if molecular_error > 0:
        mol = (oxide * scales) @ x
        mol = mol + _doubly_charged(usable, table, symbols, reference) @ x
        var = var + (molecular_error * mol) ** 2
    weight = 1.0 / np.sqrt(var)
    x = _nnls(A * weight[:, None], values * weight)
    z = np.zeros(len(symbols))
    active = np.flatnonzero(x > 0)
    if active.size:
        Aw = (A * weight[:, None])[:, active]
        sigma = np.sqrt(np.clip(np.diag(np.linalg.pinv(Aw.T @ Aw)), 0, None))
        z[active] = np.where(sigma > 0, x[active] / np.where(sigma > 0, sigma, 1.0), 0.0)
    return scales, x, z


def _doubly_charged(usable, table, symbols, reference):
    """Return the doubly charged part of the element patterns."""
    row = {m: i for i, m in enumerate(usable)}
    out = np.zeros((len(usable), len(symbols)))
    for j, s in enumerate(symbols):
        for nominal, _label, kind, value in _species_signals(s, 1.0, table[s], reference, 1.0, row):
            if kind == "doubly charged":
                out[row[nominal], j] += value
    return out


def identify_elements(measured: Dict[int, float], elements: Sequence[dict],
                      reference: Optional[dict] = None,
                      blank: Optional[Dict[int, float]] = None,
                      blank_scale: float = 1.0,
                      z_min: float = Z_MIN,
                      min_ions: float = MIN_ELEMENT_IONS,
                      model_error: float = MODEL_ERROR) -> Optional[Identification]:
    """Find which elements explain a nominal-mass spectrum, without prior knowledge.

    An element is accepted when its fitted amount is at least ``z_min`` times
    its Poisson uncertainty and its main isotope holds at least ``min_ions``
    ions, so the decision does not depend on how strong other elements are.
    With a blank, the scaled blank is subtracted first and elements that are
    only as high as in the blank are reported as background.

    Args:
        measured: ``{nominal mass: ions}`` of the sample.
        elements: Element dicts with ``isotopes``.
        reference: Rates from ``load_reference``.
        blank: ``{nominal mass: ions}`` of a blank, or None.
        blank_scale: Factor bringing the blank to the sample's acquisition
            length (sample snapshots / blank snapshots).
        z_min: Minimum significance of an element.
        min_ions: Minimum ions in the element's main isotope.
        model_error: Relative error of the molecular-ion model, added to the
            Poisson noise so that small misfits under large peaks are not
            mistaken for extra elements.

    Returns:
        Identification | None: None when the spectrum is empty.
    """
    reference = reference or load_reference()
    usable = sorted(m for m, v in measured.items() if m not in PLASMA_MASSES and m >= 24)
    if not usable:
        return None
    row = {m: i for i, m in enumerate(usable)}
    table = {s: iso for s, iso in isotope_table(elements).items()
             if s not in NOT_ANALYTES and any(n in row for n, _m, _f in iso)}
    symbols = sorted(table)
    if not symbols:
        return None
    gross = np.array([max(measured[m], 0.0) for m in usable])
    if gross.max() <= 0:
        return None
    main = {s: max(f for n, _m, f in table[s] if n in row) for s in symbols}

    def accepted(x, z):
        return {s for j, s in enumerate(symbols) if z[j] >= z_min and x[j] * main[s] >= min_ions}

    scale, x, z = _fit(gross, gross + 1.0 + (model_error * gross) ** 2, usable, table, symbols,
                       reference, MOLECULAR_ERROR, scale_variance=gross + 1.0,
                       refine=not blank)
    present = accepted(x, z)
    background: List[str] = []
    used = dict(measured)
    if blank:
        bl = np.array([max(blank.get(m, 0.0), 0.0) * blank_scale for m in usable])
        net = gross - bl
        variance = gross + blank_scale * bl + 1.0 + (model_error * gross) ** 2
        scale_n, x_n, z_n = _fit(net, variance, usable, table, symbols, reference,
                                 MOLECULAR_ERROR,
                                 scale_variance=gross + blank_scale * bl + 1.0)
        above = accepted(x_n, z_n)
        background = sorted(present - above, key=lambda s: -x[symbols.index(s)])
        scale, x, z, present = scale_n, x_n, z_n, above
        used = {m: float(v) for m, v in zip(usable, net)}

    amounts = {s: float(x[symbols.index(s)]) for s in present}
    significance = {s: float(z[symbols.index(s)]) for s in present}
    oxide_scales = {s: float(scale[symbols.index(s)]) for s in present}
    predicted: Dict[int, float] = {}
    species: Dict[int, List[Tuple[str, str, str, float]]] = {}
    for s, amount in amounts.items():
        for nominal, label, kind, value in _species_signals(s, amount, table[s], reference,
                                                            oxide_scales[s], row):
            predicted[nominal] = predicted.get(nominal, 0.0) + value
            species.setdefault(nominal, []).append((s, label, kind, value))
    for lst in species.values():
        lst.sort(key=lambda t: -t[3])
    typical = float(np.median(list(oxide_scales.values()))) if oxide_scales else float(np.median(scale))
    return Identification(amounts=amounts, oxide_scale=typical, measured=used,
                          predicted=predicted, species=species, significance=significance,
                          background=background, blank_used=bool(blank),
                          oxide_scales=oxide_scales)


def contributions(ident: Identification, nominal: int) -> List[Tuple[str, str, str, float]]:
    """Return ``(element, label, kind, share)`` of every species at a nominal mass.

    Shares are fractions of the measured signal; the part no species explains
    is returned as ``('?', 'unexplained', 'unknown', share)``.
    """
    measured = ident.measured.get(nominal, 0.0)
    total = max(measured, ident.predicted.get(nominal, 0.0), 1e-12)
    out = [(s, label, kind, value / total) for s, label, kind, value in ident.species.get(nominal, [])]
    rest = measured - ident.predicted.get(nominal, 0.0)
    if measured > 0 and rest / measured > 0.1:
        out.append(("?", "unexplained", "unknown", rest / total))
    return out


def database_species(nominal: int, present: Optional[Sequence[str]] = None
                     ) -> List[Tuple[str, float, str, str]]:
    """Polyatomic ions of the interference database at a nominal mass.

    Plasma-based ions (ArO+, ArN+, N2+...) are always listed. Ions built from
    a sample element (CaO+, ArCl+...) are listed only when that element is
    present, or always when ``present`` is None.

    Returns:
        list: ``(label, m/z, element or 'plasma', kind)``.
    """
    try:
        from widget.interference_database import get_interferences_for_mass
    except Exception:
        _itk_log.exception("Could not read the interference database")
        return []
    out = []
    for entry in get_interferences_for_mass(int(nominal)):
        mz = entry.get("exact_mass")
        if mz is None or entry.get("type") == "doubly_charged":
            continue
        metals = [c for c in entry.get("components", []) if c not in PLASMA_SPECIES]
        if entry.get("plasma_based") or not metals:
            out.append((entry["species"], float(mz), "plasma", entry.get("type", "polyatomic")))
        elif present is None or all(m in present for m in metals):
            out.append((entry["species"], float(mz), metals[0], entry.get("type", "polyatomic")))
    return out


def candidate_species(nominal: int, table: Dict[str, List[Tuple[int, float, float]]],
                      present: Optional[Sequence[str]],
                      include_database: bool = True) -> List[Tuple[str, float, str, str]]:
    """List every ion that can sit at a nominal mass, with its exact m/z.

    Atomic ions are listed for every element. Oxides and doubly charged ions
    are built from the isotope table for the elements present (all elements
    when ``present`` is None); polyatomic ions come from the interference
    database (see ``database_species``). The same list serves the Spectrum
    view and the Insights cards.

    Returns:
        list: ``(label, m/z, element, kind)`` with kind 'atom', 'oxide',
        'doubly charged' or a database type; each label appears once.
    """
    everyone = present is None
    out = []
    for s, isos in table.items():
        if s in NOBLE_GASES:
            continue
        here = everyone or s in present
        for n, mass, frac in isos:
            if n == nominal and frac >= 0.001:
                out.append((f"{sup(n)}{s}⁺", mass, s, "atom"))
            if here and s not in NOT_ANALYTES and n + 16 == nominal:
                out.append((f"{sup(n)}{s}¹⁶O⁺", mass + OXYGEN, s, "oxide"))
            if here and s not in NOT_ANALYTES and n % 2 == 0 and n // 2 == nominal:
                out.append((f"{sup(n)}{s}²⁺", mass / 2.0, s, "doubly charged"))
    if include_database:
        out.extend(database_species(nominal, present))
    seen, unique = set(), []
    for item in out:
        if item[0] not in seen:
            seen.add(item[0])
            unique.append(item)
    return unique


BLANK_NAME = re.compile(r"blan[kc]|mqw|milli[\s_-]?q", re.IGNORECASE)


def is_blank_name(name: str) -> bool:
    """Whether a sample name says it is a blank (Blank, Blanc, MQW, Milli-Q)."""
    return bool(BLANK_NAME.search(str(name or "")))


def analysis_time(run_info: Optional[dict]) -> Optional[float]:
    """Return the run's analysis time from ``run.info`` as a timestamp, or None."""
    text = str((run_info or {}).get("AnalysisDateTime") or "")
    text = re.sub(r"(\.\d{6})\d+", r"\1", text).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def pick_blank(sample: str, run_infos: Dict[str, dict]) -> Optional[str]:
    """Choose the blank to compare a sample with: the blank run closest in time.

    Args:
        sample: Sample name.
        run_infos: ``{name: run.info}`` of the runs that can serve as blank
            (only names that look like blanks are considered).

    Returns:
        str | None: The blank's name; None for a blank itself or without one.
    """
    if is_blank_name(sample):
        return None
    names = [n for n in run_infos if n != sample and is_blank_name(n)]
    if not names:
        return None
    t0 = analysis_time(run_infos.get(sample))
    if t0 is None:
        return names[0]
    return min(names, key=lambda n: abs((analysis_time(run_infos[n]) or 0.0) - t0))


def default_elements() -> List[dict]:
    """Element data of the app's periodic table, read once."""
    global _ELEMENTS
    if _ELEMENTS is None:
        from widget.periodic_table_widget import PeriodicTableWidget
        _ELEMENTS = PeriodicTableWidget.create_elements_data()
    return _ELEMENTS


def identify_run(entry: Optional[dict], run_info: dict, elements: Optional[Sequence[dict]] = None,
                 reference: Optional[dict] = None, blank_entry: Optional[dict] = None,
                 blank_run_info: Optional[dict] = None) -> Optional[Identification]:
    """Identify the elements of one Nu run from its summed raw snapshots.

    Used by the Spectrum view and the Insights spectrum cards, so both give
    the same answer.

    Args:
        entry: ``{'spectrum', 'n_snapshots'}`` of the run.
        run_info: The run's ``run.info``.
        elements: Element dicts; the app's periodic table when None.
        reference: Molecular ion rates; the bundled file when None.
        blank_entry: Spectrum of a blank run, or None.
        blank_run_info: ``run.info`` of that blank.

    Returns:
        Identification | None: None without a usable spectrum.
    """
    from loading.nu_raw_spectrum import integration_windows, spectrum_masses
    if not entry or "MassCalCoefficients" not in (run_info or {}):
        return None
    elements = elements if elements is not None else default_elements()
    spectrum = np.asarray(entry["spectrum"], dtype=np.float64)
    measured = nominal_spectrum_from_raw(spectrum_masses(run_info, len(spectrum)), spectrum,
                                         integration_windows(run_info),
                                         run_info.get("AverageSingleIonArea"))
    blank, scale = None, 1.0
    if blank_entry and "MassCalCoefficients" in (blank_run_info or {}):
        blank_spec = np.asarray(blank_entry["spectrum"], dtype=np.float64)
        blank = nominal_spectrum_from_raw(spectrum_masses(blank_run_info, len(blank_spec)),
                                          blank_spec, integration_windows(blank_run_info),
                                          blank_run_info.get("AverageSingleIonArea"))
        if entry.get("n_snapshots") and blank_entry.get("n_snapshots"):
            scale = entry["n_snapshots"] / float(blank_entry["n_snapshots"])
    return identify_elements(measured, elements, reference or load_reference(),
                             blank=blank, blank_scale=scale)


def peak_centre(masses, spectrum, target, half_width=0.4, single_ion_area=None):
    """Return ``(centre, ions)`` of the strongest peak near a mass, or None."""
    sel = np.abs(masses - target) <= half_width
    if not sel.any():
        return None
    y = np.clip(spectrum[sel], 0, None)
    if y.max() <= 0:
        return None
    i = int(np.argmax(y))
    lo, hi = max(i - 3, 0), min(i + 4, len(y))
    centre = float(np.sum(masses[sel][lo:hi] * y[lo:hi]) / max(np.sum(y[lo:hi]), 1e-12))
    scale = float(single_ion_area) if single_ion_area and single_ion_area > 0 else 1.0
    return centre, float(y.sum() / scale)


def mass_offset(masses, spectrum, ident: Identification, table, single_ion_area=None,
                min_ions: float = MIN_IONS) -> Optional[float]:
    """Measure the calibration offset of the resolved spectrum on clean peaks.

    A clean peak is an atomic isotope of an identified element that makes at
    least 95 % of its nominal mass.
    """
    masses = np.asarray(masses, dtype=float)
    spectrum = np.asarray(spectrum, dtype=float)
    shifts = []
    for s in ident.amounts:
        for n, mass, _f in table.get(s, []):
            parts = contributions(ident, n)
            own = sum(sh for el, _l, kind, sh in parts if el == s and kind == "atom")
            if own < 0.95:
                continue
            found = peak_centre(masses, spectrum, mass, single_ion_area=single_ion_area)
            if found and found[1] >= min_ions:
                shifts.append(found[0] - mass)
    if len(shifts) < 3:
        return None
    return float(np.median(shifts))


def position_match(centre: float, offset: float, candidates) -> List[Tuple[str, float, str, str]]:
    """Rank candidate ions by distance between their m/z and the corrected centre.

    Returns:
        list: ``(label, delta in Da, element, kind)``, closest first.
    """
    corrected = centre - offset
    return sorted(((label, corrected - mass, s, kind) for label, mass, s, kind in candidates),
                  key=lambda t: abs(t[1]))


def check_isotope(symbol: str, isotope_mass: float, ident: Optional[Identification],
                  elements: Sequence[dict], raw=None) -> dict:
    """Build the interference check of one isotope.

    Args:
        symbol: Element of the selected isotope.
        isotope_mass: Exact mass of the selected isotope.
        ident: Result of ``identify_elements`` for the sample.
        elements: Element dicts with ``isotopes``.
        raw: ``(masses, spectrum, single_ion_area)`` of the resolved spectrum.

    Returns:
        dict: ``rows`` as ``(name, value, alert)`` with alert False, True or
        'warn', ``verdict`` text,
        ``severity`` ('clean', 'minor', 'major', 'unknown') and ``markers``
        as ``(m/z, label, kind)`` with kind 'expected' or 'interferer'.
    """
    nominal = int(round(isotope_mass))
    label = f"{sup(nominal)}{symbol}"
    rows: List[Tuple[str, str, object]] = []
    markers: List[Tuple[float, str, str]] = []
    if ident is None:
        return {"rows": [("Interference check", "no spectrum to analyse", True)],
                "verdict": "", "severity": "unknown", "markers": []}
    table = isotope_table(elements)
    present = sorted(ident.amounts, key=lambda s: -ident.amounts[s])
    shown = ", ".join(present[:8]) + (f" +{len(present) - 8}" if len(present) > 8 else "")
    if not present:
        rows.append(("Elements found", "none above detection limit", "warn"))
        if ident.background:
            rows.append(("Background (as blank)", ", ".join(ident.background[:8]), False))
        return {"rows": rows, "verdict": "No element above detection limit",
                "severity": "unknown", "markers": []}
    rows.append(("Elements found", shown, False))
    if ident.background:
        rows.append(("Background (as blank)", ", ".join(ident.background[:8]), False))
    level = ident.oxide_scales.get(symbol, ident.oxide_scale)
    rows.append(("Oxide level", f"{level:.2g} × reference", False))

    parts = contributions(ident, nominal)
    own = sum(sh for el, _l, kind, sh in parts if el == symbol and kind == "atom")
    others = [(lab, sh) for el, lab, kind, sh in parts if not (el == symbol and kind == "atom")]
    others.sort(key=lambda t: -t[1])
    no_signal = "none above blank" if ident.blank_used else "none at this mass"
    if symbol in ident.background:
        rows.append((f"{symbol} in sample", "same level as blank", "warn"))
    elif ident.measured.get(nominal, 0.0) <= 0:
        rows.append(("Signal", no_signal, "warn"))
    elif symbol not in ident.amounts:
        rows.append((f"{symbol} in sample", "not detected", True))
    else:
        rows.append((f"Share of {label}", f"{own * 100:.0f} %", own < 0.95))
    for lab, sh in others[:3]:
        if sh >= 0.005:
            rows.append(("from " + (lab + "⁺" if lab != "unexplained" else "unexplained signal"),
                         f"{sh * 100:.1f} %", sh >= 0.05))

    offset = None
    best = None
    if raw is not None:
        masses, spectrum, sia = raw
        masses = np.asarray(masses, dtype=float)
        spectrum = np.asarray(spectrum, dtype=float)
        offset = mass_offset(masses, spectrum, ident, table, sia)
        if offset is None:
            rows.append(("Mass offset", "too few clean peaks", False))
        else:
            rows.append(("Mass offset (clean peaks)", f"{offset * 1000:+.0f} mDa", False))
            found = peak_centre(masses, spectrum, isotope_mass + offset, single_ion_area=sia)
            if found is not None and found[1] >= MIN_IONS:
                centre, _ions = found
                delta_own = (centre - offset) - isotope_mass
                rows.append((f"Centre vs {label}", f"{delta_own * 1000:+.0f} mDa",
                             abs(delta_own) > 0.008))
                ranked = position_match(centre, offset, candidate_species(nominal, table, present))
                if ranked:
                    ties = [c for c in ranked if abs(c[1] - ranked[0][1]) <= TIE_DA]
                    own_hit = next((c for c in ties if c[2] == symbol and c[3] == "atom"), None)
                    best = own_hit or ranked[0]
                    names = " / ".join(c[0] for c in ties[:3])
                    text = (f"{best[0]} ({best[1] * 1000:+.0f} mDa)" if len(ties) == 1
                            else f"{names} (same mass)")
                    rows.append(("Best match", text, best[2] != symbol or best[3] != "atom"))
            elif found is not None:
                rows.append(("Peak position", "too few ions to judge", False))
            markers.append((isotope_mass + offset, f"{label}⁺ expected", "expected"))
            for lab, sh in others[:2]:
                if sh < 0.05 or lab == "unexplained":
                    continue
                cand = [c for c in candidate_species(nominal, table, present) if c[0] == lab + "⁺"]
                if cand and abs(cand[0][1] - isotope_mass) > TIE_DA:
                    markers.append((cand[0][1] + offset, lab + "⁺", "interferer"))

    real_others = [(lab, sh) for lab, sh in others if lab != "unexplained"]
    if symbol in ident.background:
        verdict, severity = f"{symbol}: background level, same as blank", "unknown"
    elif ident.measured.get(nominal, 0.0) <= 0:
        verdict, severity = f"No signal {no_signal.split(' ', 1)[1]}", "unknown"
    elif symbol not in ident.amounts and not (real_others and real_others[0][1] >= 0.5):
        verdict, severity = f"{symbol} below detection limit", "unknown"
    elif symbol not in ident.amounts or own < 0.5:
        top = (others[0][0] + ("⁺" if others[0][0] != "unexplained" else "")) if others else "?"
        if symbol in ident.amounts:
            verdict = f"Mostly {top}: only {own * 100:.0f} % is {label}"
        else:
            verdict = f"Not {symbol}: mostly {top}"
        severity = "major"
    elif own < 0.95:
        verdict, severity = f"Interfered: {(1 - own) * 100:.0f} % from other species", "minor"
    else:
        verdict, severity = f"Clean: {label}", "clean"
    if best is not None and severity == "clean" and (best[2] != symbol or best[3] != "atom"):
        verdict, severity = f"Check: peak position fits {best[0]}", "minor"
    return {"rows": rows, "verdict": verdict, "severity": severity, "markers": markers}
