"""Raw signals and per-sample results for the assistant.

The particle table only holds what was detected. Many questions need what
the main window measured around it: the raw trace of a run, the ionic
background, the detection limits, particles per mL and the mass
concentration. This module reads those stores without changing them and
hands them over as plain arrays and one pandas table, computed with the same
formulas as the summary export, so the assistant and the exported files give
the same numbers.

Two sources share one interface: :class:`WindowAcquisition` reads a live main
window and :class:`StaticAcquisition` holds prepared arrays and rows, for the
tests, the benchmark and training data. Nothing here touches Qt.
"""
from __future__ import annotations

import logging
import re
import threading

import numpy as np
import pandas as pd

_itk_log = logging.getLogger("IsotopeTrack.results.ai.acquisition")

METHOD_KEYS = {
    'Force through zero': 'zero',
    'Simple linear': 'simple',
    'Weighted': 'weighted',
    'Manual': 'manual',
}

SUMMARY_COLUMNS = [
    'sample', 'run', 'element',
    'particles', 'particles_per_ml', 'particles_per_ml_corrected',
    'mean_mass_fg', 'median_mass_fg', 'total_mass_fg', 'mean_diameter_nm',
    'mass_conc_ug_l',
    'mean_signal_counts', 'signal_sd_counts', 'signal_rsd_pct', 'mean_signal_ppb',
    'background_counts', 'background_ppt', 'background_sd_ppt',
    'threshold_counts', 'lod_net_counts', 'mdl_fg', 'mql_fg', 'sdl_nm', 'sql_nm',
    'slope_cps_per_ppb', 'calibration_method', 'transport_rate_ul_s',
    'dwell_ms', 'acquisition_s', 'volume_ml', 'dilution',
]


def match_label(name, labels):
    """Find the isotope label a user or model meant among *labels*.

    Accepts the exact label (``"56Fe"``), the symbol (``"Fe"``, any case) or
    the label written backwards (``"Fe56"``, ``"Fe-56"``).

    Args:
        name (str): Element name as written.
        labels (list): Labels to choose from.

    Returns:
        str: The matching label.

    Raises:
        KeyError: When nothing matches, listing the labels available.
    """
    text = str(name).strip()
    if text in labels:
        return text
    squashed = re.sub(r'[\s\-_]', '', text)
    flipped = re.match(r'^([A-Za-z]+)(\d+)$', squashed)
    if flipped:
        squashed = flipped.group(2) + flipped.group(1)
    for lab in labels:
        if lab.lower() == squashed.lower():
            return lab
    for lab in labels:
        m = re.match(r'^\s*\d*\s*([A-Za-z]+)', str(lab))
        if m and m.group(1).lower() == squashed.lower():
            return lab
    raise KeyError(f"No element '{name}' in the raw data. Available: {', '.join(labels)}")


def _num(v):
    """Return *v* as a float, or NaN when it is missing or not a number."""
    try:
        out = float(v)
    except (TypeError, ValueError):
        return float('nan')
    return out if np.isfinite(out) else float('nan')


class Acquisition:
    """Raw traces and per-run results, the interface the sandbox uses.

    Subclasses provide :meth:`run_names`, :meth:`labels`, :meth:`trace` and
    :meth:`_rows`; grouping, element lookup and caching live here.

    Attributes:
        groups (dict): ``{run: sample}`` when runs were pooled into samples
            before reaching the assistant; runs absent map to themselves.
    """

    def __init__(self, groups=None):
        """Create the source.

        Args:
            groups (dict): ``{run: sample}`` of pooled runs, or ``None``.
        """
        self.groups = dict(groups or {})
        self._summary = None
        self._lock = threading.Lock()

    def run_names(self):
        """Return the runs whose raw signal is available."""
        raise NotImplementedError

    def labels(self, run):
        """Return the isotope labels recorded for *run*."""
        raise NotImplementedError

    def trace(self, run, label):
        """Return ``(time_s, counts)`` arrays of one channel, or ``None``."""
        raise NotImplementedError

    def _rows(self):
        """Return the per-run, per-element result dictionaries."""
        raise NotImplementedError

    def sample_of(self, run):
        """Return the sample a run belongs to."""
        return self.groups.get(run, run)

    def resolve_run(self, name):
        """Map a run or sample name to one run.

        Args:
            name (str): A run name, or a sample made of exactly one run.

        Returns:
            str: The run.

        Raises:
            KeyError: When the name matches no run, or a sample pools several
                runs, listing what can be passed instead.
        """
        runs = self.run_names()
        text = str(name).strip()
        if text in runs:
            return text
        lowered = {r.lower(): r for r in runs}
        if text.lower() in lowered:
            return lowered[text.lower()]
        members = [r for r in runs if str(self.sample_of(r)).lower() == text.lower()]
        if len(members) == 1:
            return members[0]
        if members:
            raise KeyError(f"'{name}' pools {len(members)} runs; pass one of them: {', '.join(members)}")
        raise KeyError(f"No run '{name}' with raw signal. Available: {', '.join(runs)}")

    def signal(self, sample, element, t0=None, t1=None):
        """Raw trace of one element in one run.

        Args:
            sample (str): Run name, or a sample holding a single run.
            element (str): Element name, symbol allowed.
            t0 (float): Start time in s, or ``None`` for the beginning.
            t1 (float): End time in s, or ``None`` for the end.

        Returns:
            pandas.DataFrame: ``time_s`` and ``counts``, one row per dwell
            time; ``attrs`` hold the run, the label and the dwell time.
        """
        run = self.resolve_run(sample)
        label = match_label(element, self.labels(run))
        found = self.trace(run, label)
        if found is None:
            raise KeyError(f"No raw signal for {label} in {run}")
        t, y = found
        t = np.asarray(t, dtype=float)
        y = np.asarray(y, dtype=float)
        n = min(len(t), len(y))
        t, y = t[:n], y[:n]
        keep = np.ones(n, dtype=bool)
        if t0 is not None:
            keep &= t >= float(t0)
        if t1 is not None:
            keep &= t <= float(t1)
        out = pd.DataFrame({'time_s': np.array(t[keep], copy=True),
                            'counts': np.array(y[keep], copy=True)})
        out.attrs.update({'run': run, 'element': label, 'sample': self.sample_of(run)})
        return out

    def summary(self):
        """Per-run, per-element results, built once.

        Returns:
            pandas.DataFrame: Columns in :data:`SUMMARY_COLUMNS` order.
        """
        if self._summary is None:
            with self._lock:
                if self._summary is None:
                    try:
                        rows = list(self._rows())
                    except Exception:
                        _itk_log.exception("Could not build the per-sample summary")
                        rows = []
                    frame = pd.DataFrame(rows)
                    for c in SUMMARY_COLUMNS:
                        if c not in frame.columns:
                            frame[c] = np.nan
                    self._summary = frame[SUMMARY_COLUMNS + [c for c in frame.columns
                                                             if c not in SUMMARY_COLUMNS]]
        return self._summary.copy()


class StaticAcquisition(Acquisition):
    """Prepared traces and rows, for the tests, the benchmark and training.

    Args:
        signals (dict): ``{run: {label: (time_s, counts)}}``.
        rows (list): Summary rows; ``sample`` is filled from *groups* when absent.
        groups (dict): ``{run: sample}`` of pooled runs.
    """

    def __init__(self, signals=None, rows=None, groups=None):
        """Store the prepared data."""
        super().__init__(groups)
        self._signals = {str(k): dict(v) for k, v in (signals or {}).items()}
        self._given_rows = [dict(r) for r in (rows or [])]

    def run_names(self):
        """Return the runs that carry a trace."""
        return list(self._signals)

    def labels(self, run):
        """Return the labels of one run."""
        return list(self._signals.get(run, {}))

    def trace(self, run, label):
        """Return the stored arrays of one channel."""
        return self._signals.get(run, {}).get(label)

    def _rows(self):
        """Return the given rows with the sample column filled in."""
        for r in self._given_rows:
            r.setdefault('sample', self.sample_of(r.get('run')))
            yield r


class WindowAcquisition(Acquisition):
    """Reads the main window's stores, read-only.

    Args:
        window: The main window.
        runs (list): Runs to expose, or ``None`` for every loaded sample.
        groups (dict): ``{run: sample}`` of pooled runs.
    """

    def __init__(self, window, runs=None, groups=None):
        """Bind to the window."""
        super().__init__(groups)
        self._w = window
        loaded = list((getattr(window, 'data_by_sample', None) or {}).keys())
        if runs:
            wanted = [str(r) for r in runs]
            self._runs = [r for r in wanted if r in loaded]
        else:
            self._runs = loaded

    @staticmethod
    def available(window):
        """Whether *window* holds raw signals at all."""
        return bool(getattr(window, 'data_by_sample', None))

    def run_names(self):
        """Return the runs with raw data."""
        return list(self._runs)

    def _elements(self):
        """Return ``(element_key, label, symbol, mass)`` of the selected isotopes, by mass."""
        out = []
        for symbol, masses in (getattr(self._w, 'selected_isotopes', None) or {}).items():
            for mass in masses or []:
                try:
                    mass = float(mass)
                except (TypeError, ValueError):
                    continue
                key = f"{symbol}-{mass:.4f}"
                try:
                    label = self._w.get_formatted_label(key)
                except Exception:
                    label = f"{round(mass)}{symbol}"
                out.append((key, label, symbol, mass))
        out.sort(key=lambda e: e[3])
        return out

    def _channels(self, run):
        """Return the ``{mass: array}`` channels of a run."""
        return (getattr(self._w, 'data_by_sample', None) or {}).get(run) or {}

    def _channel(self, run, mass):
        """Return the signal array of the channel nearest *mass*, or ``None``."""
        channels = self._channels(run)
        if not channels:
            return None
        finder = getattr(self._w, 'find_closest_isotope', None)
        key = None
        if finder is not None:
            try:
                key = finder(mass, data=channels)
            except Exception:
                _itk_log.exception("Channel lookup failed")
        elif mass in channels:
            key = mass
        return None if key is None else channels.get(key)

    def _time(self, run):
        """Return the time axis of a run in s, or ``None``."""
        t = (getattr(self._w, 'time_array_by_sample', None) or {}).get(run)
        return None if t is None else np.asarray(t, dtype=float)

    def labels(self, run):
        """Return the labels of the selected isotopes present in *run*."""
        return [label for _, label, _, mass in self._elements()
                if self._channel(run, mass) is not None]

    def trace(self, run, label):
        """Return the time axis and the signal of one channel."""
        for _, lab, _, mass in self._elements():
            if lab != label:
                continue
            y = self._channel(run, mass)
            if y is None:
                return None
            t = self._time(run)
            if t is None or len(t) != len(y):
                dwell_s = _num((getattr(self._w, 'sample_dwell_times', None) or {}).get(run)) / 1000.0
                step = dwell_s if dwell_s > 0 else 1.0
                t = np.arange(len(y)) * step
            return t, y
        return None

    def _slope(self, key):
        """Return ``(slope cps/ppb, method name)`` of the ionic calibration."""
        cal = ((getattr(self._w, 'calibration_results', None) or {}).get('Ionic Calibration') or {}).get(key)
        if not cal:
            return float('nan'), ''
        preferred = (getattr(self._w, 'isotope_method_preferences', None) or {}).get(key, 'Force through zero')
        method = METHOD_KEYS.get(preferred, 'zero')
        data = cal.get(method)
        if data is None:
            for alt in ('weighted', 'simple', 'zero', 'manual'):
                if cal.get(alt):
                    data, method = cal[alt], alt
                    break
        slope = _num((data or {}).get('slope'))
        name = next((k for k, v in METHOD_KEYS.items() if v == method), method)
        return (slope if slope > 0 else float('nan')), (name if slope > 0 else '')

    def _density(self, symbol):
        """Return the element density in g/cm3, or NaN."""
        table = getattr(self._w, 'periodic_table_info', None)
        try:
            return _num(table.get_density_by_element(symbol)) if table is not None else float('nan')
        except Exception:
            return float('nan')

    def _acquisition_s(self, run, key):
        """Analyzed acquisition time of a run, exclusions removed."""
        try:
            from utils.dilution import effective_acquisition_time
            return float(effective_acquisition_time(self._w, run, key))
        except Exception:
            t = self._time(run)
            return float(t[-1] - t[0]) if t is not None and len(t) > 1 else float('nan')

    def _analyzed(self, run, key, y):
        """Signal with excluded regions and non-finite points removed."""
        try:
            from utils.signal_stats import analyzed_signal
            return np.asarray(analyzed_signal(self._w, run, key, y), dtype=float)
        except Exception:
            arr = np.asarray(y, dtype=float)
            return arr[np.isfinite(arr)]

    def _rows(self):
        """Compute one row per run and selected isotope, as the summary export does."""
        w = self._w
        rate = _num(getattr(w, 'average_transport_rate', 0))
        rate = rate if rate > 0 else float('nan')
        dwell = getattr(w, 'sample_dwell_times', None) or {}
        dilutions = getattr(w, 'sample_dilutions', None) or {}
        thresholds = getattr(w, 'element_thresholds', None) or {}
        limits = getattr(w, 'element_limits', None) or {}
        peaks = getattr(w, 'sample_detected_peaks', None) or {}
        to_diameter = getattr(w, 'mass_to_diameter', None)
        elements = self._elements()
        for run in self._runs:
            dwell_ms = _num(dwell.get(run))
            dwell_s = dwell_ms / 1000.0 if dwell_ms > 0 else float('nan')
            dilution = _num(dilutions.get(run, 1.0))
            dilution = dilution if dilution > 0 else 1.0
            for key, label, symbol, mass in elements:
                y = self._channel(run, mass)
                if y is None:
                    continue
                acq_s = self._acquisition_s(run, key)
                volume = rate * acq_s / 1000.0 if acq_s == acq_s and acq_s > 0 else float('nan')
                found = (peaks.get(run) or {}).get((symbol, mass))
                if found is None:
                    found = next((v for (s, m), v in (peaks.get(run) or {}).items()
                                  if s == symbol and abs(float(m) - mass) < 1e-3), None)
                found = [p for p in (found or []) if p is not None]
                n = len(found)
                per_ml = n / volume if volume > 0 else float('nan')
                slope, method = self._slope(key)
                factor = slope / (rate * 1000.0) if slope > 0 and rate > 0 else float('nan')
                masses = np.array([_num(p.get('total_counts')) / factor for p in found], dtype=float) \
                    if factor > 0 else np.array([], dtype=float)
                masses = masses[np.isfinite(masses) & (masses > 0)]
                rho = self._density(symbol)
                diam = float('nan')
                if masses.size and rho > 0 and to_diameter is not None:
                    d = np.array([to_diameter(m, rho) for m in masses], dtype=float)
                    d = d[np.isfinite(d)]
                    diam = float(np.mean(d)) if d.size else float('nan')
                total = float(masses.sum()) if masses.size else (0.0 if factor > 0 else float('nan'))
                kept = self._analyzed(run, key, y)
                mean = float(np.mean(kept)) if kept.size else float('nan')
                sd = float(np.std(kept, ddof=1)) if kept.size > 1 else float('nan')
                cps = mean / dwell_s if dwell_s > 0 else float('nan')
                th = (thresholds.get(run) or {}).get(key) or {}
                lim = (limits.get(run) or {}).get(key) or {}
                yield {
                    'sample': self.sample_of(run), 'run': run, 'element': label,
                    'particles': n,
                    'particles_per_ml': per_ml,
                    'particles_per_ml_corrected': per_ml * dilution,
                    'mean_mass_fg': float(np.mean(masses)) if masses.size else float('nan'),
                    'median_mass_fg': float(np.median(masses)) if masses.size else float('nan'),
                    'total_mass_fg': total,
                    'mean_diameter_nm': diam,
                    'mass_conc_ug_l': total / volume * dilution * 1e-6 if volume > 0 else float('nan'),
                    'mean_signal_counts': mean,
                    'signal_sd_counts': sd,
                    'signal_rsd_pct': 100.0 * sd / mean if mean > 0 else float('nan'),
                    'mean_signal_ppb': cps / slope if slope > 0 else float('nan'),
                    'background_counts': _num(th.get('background')),
                    'background_ppt': _num(lim.get('background_ppt')),
                    'background_sd_ppt': _num(lim.get('background_sd_ppt')),
                    'threshold_counts': _num(th.get('LOD_counts')),
                    'lod_net_counts': _num(th.get('LOD_MDL')),
                    'mdl_fg': _num(lim.get('MDL')),
                    'mql_fg': _num(lim.get('MQL')),
                    'sdl_nm': _num(lim.get('SDL')),
                    'sql_nm': _num(lim.get('SQL')),
                    'slope_cps_per_ppb': slope,
                    'calibration_method': method,
                    'transport_rate_ul_s': rate,
                    'dwell_ms': dwell_ms,
                    'acquisition_s': acq_s,
                    'volume_ml': volume,
                    'dilution': dilution,
                }


def from_dataset(data_context, parent_window, run_to_sample=None):
    """Pick the acquisition source for a dataset.

    Args:
        data_context (dict): The node's input data; an ``acquisition`` entry
            holding an :class:`Acquisition` is used as is.
        parent_window: The main window, or ``None``.
        run_to_sample (dict): ``{run: sample}`` from the particle table.

    Returns:
        Acquisition | None: The source, or ``None`` when no raw data exists.
    """
    given = (data_context or {}).get('acquisition')
    if isinstance(given, Acquisition):
        return given
    if parent_window is None or not WindowAcquisition.available(parent_window):
        return None
    mapping = dict(run_to_sample or {})
    runs = list(mapping)
    for name in (data_context or {}).get('sample_names') or []:
        if name not in mapping:
            runs.append(str(name))
    if not runs and (data_context or {}).get('sample_name'):
        runs = [str(data_context['sample_name'])]
    groups = {r: s for r, s in mapping.items() if r != s}
    source = WindowAcquisition(parent_window, runs or None, groups)
    return source if source.run_names() else None
