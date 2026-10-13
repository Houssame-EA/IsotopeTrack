"""The particle data the assistant works on, as one pandas table.

A canvas stream is a list of particle dictionaries. Small models make many
mistakes walking those nested dictionaries, so :class:`Dataset` turns the
stream into one row per particle with flat columns such as ``mass_fg_56Fe``,
and gathers what the main window knows about it: the samples, each run's
acquisition time and the calibrated detection limits.

Nothing here touches Qt, so it is cheap to test.
"""
from __future__ import annotations

import logging
import re
import threading

import numpy as np
import pandas as pd

_itk_log = logging.getLogger("IsotopeTrack.results.ai.data")

QUANTITIES = {
    'counts': 'elements',
    'mass_fg': 'element_mass_fg',
    'moles_fmol': 'element_moles_fmol',
    'diameter_nm': 'element_diameter_nm',
    'particle_mass_fg': 'particle_mass_fg',
    'particle_diameter_nm': 'particle_diameter_nm',
    'mass_pct': 'mass_percentages',
    'mole_pct': 'mole_percentages',
}

QUANTITY_UNITS = {
    'counts': 'counts', 'mass_fg': 'fg', 'moles_fmol': 'fmol', 'diameter_nm': 'nm',
    'particle_mass_fg': 'fg', 'particle_diameter_nm': 'nm',
    'mass_pct': '%', 'mole_pct': '%',
}

QUANTITY_ALIASES = {
    'count': 'counts', 'signal': 'counts', 'intensity': 'counts', 'cts': 'counts',
    'mass': 'mass_fg', 'fg': 'mass_fg', 'element_mass_fg': 'mass_fg',
    'moles': 'moles_fmol', 'mol': 'moles_fmol', 'fmol': 'moles_fmol',
    'element_moles_fmol': 'moles_fmol',
    'diameter': 'diameter_nm', 'size': 'diameter_nm', 'd': 'diameter_nm',
    'nm': 'diameter_nm', 'element_diameter_nm': 'diameter_nm',
    'mass%': 'mass_pct', 'mass_percent': 'mass_pct', 'mass_percentages': 'mass_pct',
    'mole%': 'mole_pct', 'mole_percent': 'mole_pct', 'mole_percentages': 'mole_pct',
    'compound_mass': 'particle_mass_fg', 'compound_diameter': 'particle_diameter_nm',
}

LIMIT_KEYS = {'counts': 'counts', 'mass_fg': 'mass', 'diameter_nm': 'd'}

_HIDDEN_CONTEXT_KEYS = ('parent_window', 'particle_data')


def resolve_quantity(name):
    """Map a loosely written quantity name to its canonical form.

    Args:
        name (str): Something like ``"mass"``, ``"size"`` or ``"diameter_nm"``.

    Returns:
        str: One of :data:`QUANTITIES`.

    Raises:
        KeyError: When the name matches no quantity.
    """
    key = str(name or '').strip().lower().replace(' ', '_')
    if key in QUANTITIES:
        return key
    if key in QUANTITY_ALIASES:
        return QUANTITY_ALIASES[key]
    raise KeyError(f"Unknown quantity '{name}'. Use one of: {', '.join(QUANTITIES)}")


def _float(v):
    """Return *v* as a float, or NaN when it is missing or not a number."""
    try:
        out = float(v)
    except (TypeError, ValueError):
        return float('nan')
    return out if out == out else float('nan')


def _class_lookup():
    """Return the classifier's particle-to-class function, or ``None``."""
    try:
        from results.classifier_view import bucket_of
        return bucket_of
    except Exception:
        return None


def particle_frame(particles, default_sample='Sample'):
    """Build one row per particle with flat per-element columns.

    Columns:
        ``sample``, ``run`` (the original acquisition when samples were
        pooled), ``t_start``/``t_end`` in s, ``duration_ms``, ``n_elements``,
        ``combo`` (detected elements joined with ``" + "``), totals, an
        optional ``class`` from the Particle Classifier, and one column per
        quantity and element, e.g. ``mass_fg_56Fe``. An element that was not
        detected in a particle is NaN, never zero.

    Args:
        particles (list): Particle dictionaries from the canvas.
        default_sample (str): Sample name for particles that carry none.

    Returns:
        pandas.DataFrame: The particle table, elements ordered by how often
        they are detected.
    """
    n = len(particles)
    base = {
        'sample': np.empty(n, dtype=object),
        'run': np.empty(n, dtype=object),
        't_start': np.full(n, np.nan),
        't_end': np.full(n, np.nan),
        'total_mass_fg': np.full(n, np.nan),
        'total_moles_fmol': np.full(n, np.nan),
        'total_particle_mass_fg': np.full(n, np.nan),
    }
    per_q = {q: {} for q in QUANTITIES}
    detect = {}
    combos = np.empty(n, dtype=object)
    n_el = np.zeros(n, dtype=int)
    bucket_of = _class_lookup()
    classes = np.empty(n, dtype=object) if bucket_of else None
    any_class = False
    for i, p in enumerate(particles):
        sample = p.get('source_sample') or p.get('_source_sample') or default_sample
        base['sample'][i] = sample
        base['run'][i] = p.get('original_sample') or sample
        base['t_start'][i] = _float(p.get('start_time'))
        base['t_end'][i] = _float(p.get('end_time'))
        totals = p.get('totals') or {}
        if isinstance(totals, dict):
            base['total_mass_fg'][i] = _float(totals.get('total_element_mass_fg'))
            base['total_moles_fmol'][i] = _float(totals.get('total_element_moles_fmol'))
            base['total_particle_mass_fg'][i] = _float(totals.get('total_particle_mass_fg'))
        found = []
        for q, field in QUANTITIES.items():
            d = p.get(field)
            if not isinstance(d, dict):
                continue
            store = per_q[q]
            for el, v in d.items():
                v = _float(v)
                if not (v > 0):
                    continue
                arr = store.get(el)
                if arr is None:
                    arr = np.full(n, np.nan)
                    store[el] = arr
                arr[i] = v
                if q == 'counts':
                    found.append(el)
        for el in found:
            detect[el] = detect.get(el, 0) + 1
        found.sort()
        combos[i] = ' + '.join(found)
        n_el[i] = len(found)
        if classes is not None:
            try:
                c = bucket_of(p)
            except Exception:
                c = None
            classes[i] = c
            any_class = any_class or bool(c)
    order = sorted(detect, key=lambda e: (-detect[e], e))
    cols = dict(base)
    cols['duration_ms'] = (base['t_end'] - base['t_start']) * 1000.0
    cols['n_elements'] = n_el
    cols['combo'] = combos
    if any_class:
        cols['class'] = np.where(pd.isna(classes), 'Unclassified', classes)
    for q in QUANTITIES:
        store = per_q[q]
        for el in order:
            if el in store:
                cols[f'{q}_{el}'] = store[el]
    df = pd.DataFrame(cols)
    df.attrs['elements'] = order
    return df


def _symbol(label):
    """Return the element symbol of an isotope label such as ``56Fe``."""
    m = re.match(r'^\s*(\d*)\s*([A-Za-z]+)', str(label))
    return m.group(2) if m else str(label)


class Dataset:
    """Everything the assistant knows about the connected particle stream.

    The particle table and the summaries are built once and cached, so every
    question in a conversation reuses them.

    Attributes:
        particles (list): Raw particle dictionaries.
        kind (str): ``sample_data`` or ``multiple_sample_data``.
        sample_names (list): Samples in canvas order.
    """

    def __init__(self, data_context=None, parent_window=None):
        """Wrap a canvas data context.

        Args:
            data_context (dict): The node's input data.
            parent_window: The main window, used only to read detection limits.
        """
        self.data_context = data_context or {}
        self.particles = list(self.data_context.get('particle_data') or [])
        self.kind = self.data_context.get('type', '')
        self._parent_window = parent_window or self.data_context.get('parent_window')
        self._df = None
        self._limits = None
        self._runs = None
        self._lock = threading.Lock()
        names = list(self.data_context.get('sample_names') or [])
        if not names and self.data_context.get('sample_name'):
            names = [self.data_context.get('sample_name')]
        self._declared_samples = [str(n) for n in names]

    def __len__(self):
        """Return the number of particles."""
        return len(self.particles)

    @property
    def default_sample(self):
        """Name used for particles that do not carry a sample."""
        return str(self.data_context.get('sample_name') or 'Sample')

    @property
    def df(self):
        """The particle table (see :func:`particle_frame`), built on first use."""
        if self._df is None:
            with self._lock:
                if self._df is None:
                    self._df = particle_frame(self.particles, self.default_sample)
        return self._df

    @property
    def elements(self):
        """Detected isotope labels, most frequent first."""
        return list(self.df.attrs.get('elements', []))

    @property
    def samples(self):
        """Sample names, in canvas order first, then any others found."""
        seen = list(dict.fromkeys(self.df['sample'].tolist())) if len(self) else []
        ordered = [s for s in self._declared_samples if s in seen]
        return ordered + [s for s in seen if s not in ordered]

    def safe_context(self):
        """Return the data context without the main window or the raw particles.

        Generated code sees this copy. Handing it the main window would let it
        reach the whole application.

        Returns:
            dict: Shallow copy holding only plain metadata.
        """
        return {k: v for k, v in self.data_context.items() if k not in _HIDDEN_CONTEXT_KEYS}

    def resolve_element(self, name):
        """Find the isotope label a user or model meant.

        Accepts the exact label (``"56Fe"``), the symbol (``"Fe"``, any case)
        or the label written backwards (``"Fe56"``, ``"Fe-56"``).

        Args:
            name (str): Element name as written.

        Returns:
            str: The matching label.

        Raises:
            KeyError: When nothing matches, listing the labels available.
        """
        labels = self.elements
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
        hits = [lab for lab in labels if _symbol(lab).lower() == squashed.lower()]
        if hits:
            return hits[0]
        raise KeyError(f"No element '{name}' in this data. Available: {', '.join(labels)}")

    def column(self, quantity, element):
        """Return the column name for a quantity of an element.

        Args:
            quantity (str): Quantity name, aliases allowed.
            element (str): Element name, symbol allowed.

        Returns:
            str: Column name such as ``diameter_nm_48Ti``.

        Raises:
            KeyError: When that column does not exist.
        """
        q = resolve_quantity(quantity)
        el = self.resolve_element(element)
        name = f'{q}_{el}'
        if name not in self.df.columns:
            raise KeyError(f"No {q} values for {el} in this data")
        return name

    def runs(self):
        """Acquisition span of each run, the base of the coincidence estimates.

        A run's span is taken from its first particle start to its last
        particle end, which is a lower bound of the real acquisition time.

        Returns:
            pandas.DataFrame: One row per run with ``n``, ``t0``, ``t1``,
            ``span_s`` and ``median_duration_ms``.
        """
        if self._runs is None:
            df = self.df
            if not len(df):
                self._runs = pd.DataFrame(columns=['run', 'n', 't0', 't1', 'span_s',
                                                   'median_duration_ms'])
            else:
                g = df.groupby('run', sort=False)
                out = pd.DataFrame({
                    'n': g.size(),
                    't0': g['t_start'].min(),
                    't1': g['t_end'].max(),
                    'median_duration_ms': g['duration_ms'].median(),
                })
                out['span_s'] = (out['t1'] - out['t0']).clip(lower=0)
                self._runs = out.reset_index()
        return self._runs

    def limits(self):
        """Calibrated detection limits, per element, quantity and sample.

        Read through the Figure Builder's limit helper, so they are the same
        numbers the calibration table and the plots show.

        Returns:
            dict: ``{label: {"counts" | "mass_fg" | "diameter_nm": {sample: value}}}``,
            empty when no main window is connected.
        """
        if self._limits is not None:
            return self._limits
        self._limits = {}
        if self._parent_window is None or not len(self):
            return self._limits
        try:
            from results.figure_builder.core.limits import detection_limits
            runs = sorted(set(self.df['run'].tolist()))
            raw = detection_limits(self._parent_window, runs, self.elements) or {}
        except Exception:
            _itk_log.exception("Could not read detection limits")
            raw = {}
        rename = {v: k for k, v in LIMIT_KEYS.items()}
        run_to_sample = self.df.groupby('run')['sample'].first().to_dict()
        for label, per in raw.items():
            entry = {}
            for key, by_run in (per or {}).items():
                q = rename.get(key)
                if not q:
                    continue
                by_sample = {}
                for run, value in by_run.items():
                    sample = run_to_sample.get(run, run)
                    by_sample[sample] = max(by_sample.get(sample, 0.0), float(value))
                entry[q] = by_sample
            if entry:
                self._limits[label] = entry
        return self._limits

    def set_limits(self, limits):
        """Replace the detection limits, mainly for tests and the benchmark.

        Args:
            limits (dict): Same shape as :meth:`limits` returns.
        """
        self._limits = dict(limits or {})

    def lod(self, element, quantity='mass_fg', sample=None):
        """Detection limit of one element.

        Args:
            element (str): Element name.
            quantity (str): ``counts``, ``mass_fg`` or ``diameter_nm``.
            sample (str): A sample, or ``None`` for the highest limit of all
                samples, the level above which every sample detects it.

        Returns:
            float | None: The limit, or ``None`` when it is not known.
        """
        q = resolve_quantity(quantity)
        el = self.resolve_element(element)
        per = (self.limits().get(el) or {}).get(q) or {}
        if not per:
            return None
        if sample is not None:
            v = per.get(sample)
            return float(v) if v else None
        return float(max(per.values()))

    def concentrations_available(self):
        """Whether particle number concentrations can be computed."""
        meta = self.data_context.get('concentration_meta')
        if not isinstance(meta, dict) or not meta:
            return False
        for entry in meta.values():
            if isinstance(entry, dict) and entry.get('volume_ml'):
                return True
        return False

    def per_ml_factor(self):
        """Particles-per-mL factor of each sample, from the concentration metadata.

        Returns:
            dict: ``{sample: dilution / volume_ml}``, empty when unavailable.
        """
        meta = self.data_context.get('concentration_meta')
        out = {}
        if not isinstance(meta, dict):
            return out
        for sample, entry in meta.items():
            if not isinstance(entry, dict):
                continue
            vol = _float(entry.get('volume_ml'))
            dil = _float(entry.get('dilution_factor', 1.0))
            if vol > 0 and dil == dil:
                out[str(sample)] = dil / vol
        return out
