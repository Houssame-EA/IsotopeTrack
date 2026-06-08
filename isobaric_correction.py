"""
Isobaric correction engine for spICP-ToF-MS.

This module is pure logic. It does NOT own any element/abundance data and does
NOT import the GUI. All element data is read through accessors that are passed
in (the same ones MainWindow already uses), so abundances live in exactly one
place: PeriodicTableWidget.

Design decisions (agreed in discussion):
  - Correction is applied UPSTREAM, on the raw signal trace, before particle
    detection. Everything downstream (detection, counts, mass, size) then reads
    already-clean data.
  - The correction factor R is the natural-abundance ratio of the interfering
    element:  R = abundance(interferent @ overlap mass) / abundance(interferent @ monitor mass).
  - Corrected signal is clamped at zero.
  - A correction is only *applicable* when a clean monitor isotope of the
    interfering element is actually measured (present as a data channel).

The arithmetic:
    corrected_analyte(t) = max( raw_analyte(t) - R * monitor(t), 0 )

Example (Pb measured at 204, Hg interfering, 202Hg as monitor):
    R = abundance(204Hg) / abundance(202Hg) = 6.87 / 29.86 = 0.2301
    corrected_204(t) = max( raw_204(t) - 0.2301 * signal_202Hg(t), 0 )

Reused from the rest of the app (passed in, never duplicated here):
    get_element_by_symbol(symbol) -> element dict with 'isotopes':
        [{'mass': float, 'abundance': float (percent), 'label': str}, ...]
    get_elements()                -> list of those element dicts
    find_closest_isotope(mass)    -> nearest available data-channel mass (float)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

DEFAULT_MIN_OVERLAP_ABUNDANCE = 0.1

def _nominal(mass: float) -> int:
    """Return the nominal (integer) mass by rounding to the nearest integer."""
    return int(round(mass))


@dataclass
class IsobaricCorrection:
    """A single, fully-specified isobaric correction.

    Masses are exact isotope masses (matching the periodic-table data and the
    mass-keyed signal channels). Symbols are element symbols.
    """
    analyte_symbol: str
    analyte_mass: float         
    interferent_symbol: str
    interferent_overlap_mass: float   
    monitor_mass: float          
    factor: float              
    enabled: bool = True

    analyte_label: str = ""
    interferent_overlap_label: str = ""
    monitor_label: str = ""
    note: str = ""

    def equation_text(self) -> str:
        """Human-readable equation with the real numbers filled in."""
        a = self.analyte_label or f"{_nominal(self.analyte_mass)}{self.analyte_symbol}"
        ov = self.interferent_overlap_label or f"{_nominal(self.interferent_overlap_mass)}{self.interferent_symbol}"
        mon = self.monitor_label or f"{_nominal(self.monitor_mass)}{self.interferent_symbol}"
        return (f"corrected({a}) = max( raw({_nominal(self.analyte_mass)}) "
                f"- {self.factor:.4f} \u00d7 signal({mon}), 0 )"
                f"   [R = ab({ov}) / ab({mon})]")


def _isotopes(element_data: dict) -> List[dict]:
    """Return the list of isotope dicts for an element, or an empty list if unavailable."""
    if not element_data:
        return []
    return [iso for iso in element_data.get('isotopes', []) if isinstance(iso, dict)]


def _abundance_at(element_data: dict, mass: float, tol: float = 0.3) -> float:
    """Abundance (percent) of the isotope nearest `mass`, by nominal mass."""
    target = _nominal(mass)
    for iso in _isotopes(element_data):
        if _nominal(iso.get('mass', 0.0)) == target:
            return float(iso.get('abundance', 0.0) or 0.0)
    return 0.0


def _isotope_dict_at(element_data: dict, mass: float) -> Optional[dict]:
    """Return the isotope dict whose nominal mass matches *mass*, or None if not found."""
    target = _nominal(mass)
    for iso in _isotopes(element_data):
        if _nominal(iso.get('mass', 0.0)) == target:
            return iso
    return None



def find_isobaric_overlaps(analyte_symbol: str,
                           analyte_mass: float,
                           get_element_by_symbol: Callable[[str], Optional[dict]],
                           get_elements: Callable[[], List[dict]],
                           min_abundance: float = DEFAULT_MIN_OVERLAP_ABUNDANCE
                           ) -> List[dict]:
    """Find every *other element* that has an isotope on the analyte's mass.

    Returns a list (usually 0 or 1) of dicts:
        {'symbol', 'overlap_mass', 'overlap_label', 'overlap_abundance'}
    sorted by abundance (largest interferent first).

    Pure abundance scan of the data already in the periodic table — this is the
    source of truth for element-element isobars, which the interference DB does
    not enumerate.
    """
    target = _nominal(analyte_mass)
    overlaps = []

    for element_data in get_elements():
        symbol = element_data.get('symbol', '')
        if symbol == analyte_symbol:
            continue
        for iso in _isotopes(element_data):
            mass = float(iso.get('mass', 0.0))
            abundance = float(iso.get('abundance', 0.0) or 0.0)
            if _nominal(mass) == target and abundance >= min_abundance:
                overlaps.append({
                    'symbol': symbol,
                    'overlap_mass': mass,
                    'overlap_label': iso.get('label', f"{target}{symbol}"),
                    'overlap_abundance': abundance,
                })

    overlaps.sort(key=lambda o: o['overlap_abundance'], reverse=True)
    return overlaps


def choose_monitor_isotope(interferent_symbol: str,
                           overlap_mass: float,
                           get_element_by_symbol: Callable[[str], Optional[dict]],
                           get_elements: Callable[[], List[dict]],
                           available_masses: Optional[List[float]] = None,
                           min_abundance: float = DEFAULT_MIN_OVERLAP_ABUNDANCE
                           ) -> Optional[dict]:
    """Pick a clean monitor isotope of the interfering element.

    "Clean" = not the overlap mass itself, and (preferably) not itself
    isobarically overlapped by another element. Among the candidates we choose
    the most abundant one. If `available_masses` is given, only isotopes that
    are actually measured (a channel exists within 0.5 Da) are considered, so a
    monitor is never selected that has no data behind it.

    Returns {'mass', 'label', 'abundance', 'available'} or None.
    """
    element_data = get_element_by_symbol(interferent_symbol)
    if not element_data:
        return None

    overlap_nominal = _nominal(overlap_mass)
    candidates = []

    for iso in _isotopes(element_data):
        mass = float(iso.get('mass', 0.0))
        abundance = float(iso.get('abundance', 0.0) or 0.0)
        if abundance < min_abundance:
            continue
        if _nominal(mass) == overlap_nominal:
            continue  

        others = find_isobaric_overlaps(
            interferent_symbol, mass, get_element_by_symbol, get_elements,
            min_abundance=min_abundance)
        is_clean = len(others) == 0

        available = True
        if available_masses is not None:
            available = any(abs(m - mass) < 0.5 for m in available_masses)

        candidates.append({
            'mass': mass,
            'label': iso.get('label', f"{_nominal(mass)}{interferent_symbol}"),
            'abundance': abundance,
            'is_clean': is_clean,
            'available': available,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c['available'], c['is_clean'], c['abundance']),
                    reverse=True)
    best = candidates[0]
    return {
        'mass': best['mass'],
        'label': best['label'],
        'abundance': best['abundance'],
        'available': best['available'],
    }


def correction_factor(interferent_symbol: str,
                      overlap_mass: float,
                      monitor_mass: float,
                      get_element_by_symbol: Callable[[str], Optional[dict]]
                      ) -> float:
    """R = abundance(interferent @ overlap) / abundance(interferent @ monitor).

    Both abundances read from the periodic table. Returns 0.0 if the monitor
    abundance is unavailable (correction then has no effect, fail-safe).
    """
    element_data = get_element_by_symbol(interferent_symbol)
    ab_overlap = _abundance_at(element_data, overlap_mass)
    ab_monitor = _abundance_at(element_data, monitor_mass)
    if ab_monitor <= 0.0:
        return 0.0
    return ab_overlap / ab_monitor


def build_correction(analyte_symbol: str,
                     analyte_mass: float,
                     get_element_by_symbol: Callable[[str], Optional[dict]],
                     get_elements: Callable[[], List[dict]],
                     available_masses: Optional[List[float]] = None,
                     min_abundance: float = DEFAULT_MIN_OVERLAP_ABUNDANCE
                     ) -> Optional[IsobaricCorrection]:
    """Assemble a ready-to-use correction for an analyte isotope, or None.

    Picks the dominant interferent on the analyte mass, chooses a monitor for
    it, computes R, and marks the correction enabled only if the monitor is
    actually measured. The periodic-table UX can call this when an isotope is
    selected to decide whether to flag + offer the correction.
    """
    overlaps = find_isobaric_overlaps(
        analyte_symbol, analyte_mass, get_element_by_symbol, get_elements,
        min_abundance=min_abundance)
    if not overlaps:
        return None

    interferent = overlaps[0]
    monitor = choose_monitor_isotope(
        interferent['symbol'], interferent['overlap_mass'],
        get_element_by_symbol, get_elements,
        available_masses=available_masses, min_abundance=min_abundance)
    if monitor is None:
        return None

    R = correction_factor(
        interferent['symbol'], interferent['overlap_mass'], monitor['mass'],
        get_element_by_symbol)

    analyte_iso = _isotope_dict_at(get_element_by_symbol(analyte_symbol), analyte_mass)
    analyte_label = (analyte_iso or {}).get(
        'label', f"{_nominal(analyte_mass)}{analyte_symbol}")

    return IsobaricCorrection(
        analyte_symbol=analyte_symbol,
        analyte_mass=analyte_mass,
        interferent_symbol=interferent['symbol'],
        interferent_overlap_mass=interferent['overlap_mass'],
        monitor_mass=monitor['mass'],
        factor=R,
        enabled=bool(monitor['available']) and R > 0.0,
        analyte_label=analyte_label,
        interferent_overlap_label=interferent['overlap_label'],
        monitor_label=monitor['label'],
        note=("monitor not measured \u2014 select "
              f"{monitor['label']} to enable" if not monitor['available'] else ""),
    )


def build_corrections_for_isotope(analyte_symbol: str,
                                  analyte_mass: float,
                                  get_element_by_symbol: Callable[[str], Optional[dict]],
                                  get_elements: Callable[[], List[dict]],
                                  available_masses: Optional[List[float]] = None,
                                  min_abundance: float = DEFAULT_MIN_OVERLAP_ABUNDANCE
                                  ) -> List[IsobaricCorrection]:
    """All isobaric corrections for one analyte isotope (multi-interferent).

    A mass like 176 is overlapped by both Yb and Lu (and Hf is the analyte),
    so several interferents may need subtracting from the same channel. This
    returns one IsobaricCorrection per qualifying interferent; they all target
    the same analyte channel and are accumulated before clamping in
    correct_sample_channels.
    """
    overlaps = find_isobaric_overlaps(
        analyte_symbol, analyte_mass, get_element_by_symbol, get_elements,
        min_abundance=min_abundance)
    if not overlaps:
        return []

    analyte_iso = _isotope_dict_at(get_element_by_symbol(analyte_symbol), analyte_mass)
    analyte_label = (analyte_iso or {}).get(
        'label', f"{_nominal(analyte_mass)}{analyte_symbol}")

    corrections: List[IsobaricCorrection] = []
    for interferent in overlaps:
        monitor = choose_monitor_isotope(
            interferent['symbol'], interferent['overlap_mass'],
            get_element_by_symbol, get_elements,
            available_masses=available_masses, min_abundance=min_abundance)
        if monitor is None:
            continue
        R = correction_factor(
            interferent['symbol'], interferent['overlap_mass'], monitor['mass'],
            get_element_by_symbol)
        corrections.append(IsobaricCorrection(
            analyte_symbol=analyte_symbol,
            analyte_mass=analyte_mass,
            interferent_symbol=interferent['symbol'],
            interferent_overlap_mass=interferent['overlap_mass'],
            monitor_mass=monitor['mass'],
            factor=R,
            enabled=bool(monitor['available']) and R > 0.0,
            analyte_label=analyte_label,
            interferent_overlap_label=interferent['overlap_label'],
            monitor_label=monitor['label'],
            note=(f"\u26a0 Monitor not in selection \u2014 "
                  f"add {monitor['label']} to your isotope selection to enable this correction."
                  if not monitor['available'] else ""),
        ))
    return corrections


def build_all_corrections(selected_isotopes: Dict[str, List[float]],
                          get_element_by_symbol: Callable[[str], Optional[dict]],
                          get_elements: Callable[[], List[dict]],
                          min_abundance: float = DEFAULT_MIN_OVERLAP_ABUNDANCE,
                          monitor_pool: Optional[List[float]] = None,
                          ) -> List[IsobaricCorrection]:
    """Build every applicable correction from the app's selected_isotopes.

    `selected_isotopes` maps element symbol -> list of selected isotope masses
    (exactly MainWindow.selected_isotopes). The measured masses double as the
    pool of candidate monitors, so a correction is only enabled when a clean
    monitor of the interferent is among the selected isotopes.

    `monitor_pool`, if given, overrides the candidate-monitor search space.
    Pass all measured data-channel masses here so that monitor isotopes the
    user did not explicitly select are still usable for correction (they are
    already in memory — no extra loading required).
    """
    available = monitor_pool if monitor_pool is not None else \
        sorted({m for masses in selected_isotopes.values() for m in masses})
    out: List[IsobaricCorrection] = []
    for symbol, masses in selected_isotopes.items():
        for mass in masses:
            out.extend(build_corrections_for_isotope(
                symbol, mass, get_element_by_symbol, get_elements,
                available_masses=available, min_abundance=min_abundance))
    return out


def apply_to_signal(analyte_signal: np.ndarray,
                    monitor_signal: np.ndarray,
                    factor: float,
                    clamp: bool = True) -> np.ndarray:
    """corrected = analyte - factor * monitor, clamped at 0.

    Returns a new array; inputs are not modified. Shapes must match (both
    channels are acquired on the same ToF time base).
    """
    analyte = np.asarray(analyte_signal, dtype=float)
    monitor = np.asarray(monitor_signal, dtype=float)
    if analyte.shape != monitor.shape:
        raise ValueError(
            f"analyte/monitor length mismatch: {analyte.shape} vs {monitor.shape}")
    corrected = analyte - factor * monitor
    if clamp:
        np.clip(corrected, 0.0, None, out=corrected)
    return corrected


def correct_sample_channels(sample_data: Dict[float, np.ndarray],
                            corrections: List[IsobaricCorrection],
                            find_closest_isotope: Callable[[float], float],
                            clamp: bool = True
                            ) -> Dict[float, np.ndarray]:
    """Return corrected copies of the analyte channels for one sample.

    `sample_data` is the mass-keyed channel dict (like data_by_sample[sample]).
    Only enabled corrections whose monitor channel exists are applied.

    When several interferents land on the same analyte channel (e.g. mass 176
    overlapped by Yb and Lu), all of them are subtracted first and the result
    is clamped once at the end:
        corrected = max( raw - R1*mon1 - R2*mon2 - ... , 0 )

    The returned dict contains ONLY the analyte channels that changed, so the
    caller can show in/out and apply on commit while keeping the raw aside.
    """
    by_analyte: Dict[float, list] = {}
    for corr in corrections:
        if not corr.enabled or corr.factor <= 0.0:
            continue
        analyte_key = find_closest_isotope(corr.analyte_mass)
        monitor_key = find_closest_isotope(corr.monitor_mass)
        if analyte_key not in sample_data or monitor_key not in sample_data:
            continue
        if _nominal(monitor_key) == _nominal(analyte_key):
            continue
        by_analyte.setdefault(analyte_key, []).append((monitor_key, corr.factor))

    out: Dict[float, np.ndarray] = {}
    for analyte_key, subtractions in by_analyte.items():
        corrected = np.asarray(sample_data[analyte_key], dtype=float).copy()
        for monitor_key, factor in subtractions:
            monitor = np.asarray(sample_data[monitor_key], dtype=float)
            if monitor.shape != corrected.shape:
                raise ValueError(
                    f"channel length mismatch at analyte {analyte_key}: "
                    f"{corrected.shape} vs monitor {monitor_key} {monitor.shape}")
            corrected -= factor * monitor
        if clamp:
            np.clip(corrected, 0.0, None, out=corrected)
        out[analyte_key] = corrected

    return out