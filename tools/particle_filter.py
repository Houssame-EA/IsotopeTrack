"""Particle Filter node for the Workflow Canvas.

A composable filter that sits between sample selector nodes (Single Sample,
Multi-Sample, or Batch) and any figure node. Several sample nodes can be
connected to the filter at once: every incoming sample — including each
summed group inside a Multi-Sample stream — appears in a sample list on the
left side of the configuration dialog. Each sample carries its own filter
settings: click a sample, tune its criteria in the right pane, then move to
the next one.

Per sample, up to four independent criteria axes are available (AND logic
between active axes): isotopic composition (AND / OR / EXACT / NOT(AND) /
NOT(OR) / NOT(EXACT) match), detected-isotope count, per-isotope signal
thresholds, and particle data (mass / diameter range filters).

The output is regrouped so figures can read it: one chosen sample is
re-emitted as single-sample data, several chosen samples are regrouped into
multi-sample data with their ``source_sample`` tags, so every downstream
figure node consumes the result transparently.
"""

import math

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QDialogButtonBox, QApplication, QGraphicsItem, QListWidget,
    QListWidgetItem, QSplitter, QScrollArea, QFrame, QLineEdit,
)
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QPointF, QRectF
from PySide6.QtGui import QPen, QColor

from tools.theme import theme as _app_theme
from results.results_periodic import IsotopeChipSelector
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.particle_filter")

_FILTERABLE_TYPES = ('sample_data', 'single_sample_data',
                     'multiple_sample_data')


def _ual():
    """Return the UserActionLogger, or None if logging isn't ready.

    Returns:
        object: The user action logger instance, or None.
    """
    try:
        from tools.logging_utils import logging_manager
        return logging_manager.get_user_action_logger()
    except Exception:
        _itk_log.exception("Handled exception in _ual")
        return None


def _num_text(v):
    """Format a numeric filter value for a QLineEdit without trailing zeros.

    Args:
        v (float): Value to format.

    Returns:
        str: Compact numeric text, e.g. "2.5" not "2.500000".
    """
    if v == int(v):
        return str(int(v))
    return f"{v:g}"


def _empty_conc_meta():
    """Build an empty concentration metadata entry.

    Returns:
        dict: Default volume / dilution / transport-efficiency mapping.
    """
    return {'volume_ml': 0.0, 'dilution_factor': 1.0, 'te_available': False}


def _default_particle_data_field():
    """Build one (mass or diameter) sub-filter's default (inactive) state.

    Returns:
        dict: Disabled sub-filter with an empty "at least" expression.
    """
    return {'enabled': False, 'expr': 'at_least', 'min': None, 'max': None}


def default_filter_config():
    """Build the default (inactive) per-sample filter configuration.

    Returns:
        dict: Configuration with all four filter axes disabled.
    """
    return {
        'composition': {'enabled': False, 'isotopes': [], 'mode': 'AND'},
        'count':       {'enabled': False, 'op': 'min', 'value': 2},
        'threshold':   {'enabled': False, 'unit': 'elements', 'values': {}},
        'particle_data': {
            'enabled': False,
            'mass': _default_particle_data_field(),
            'diameter': _default_particle_data_field(),
            'counts': _default_particle_data_field(),
        },
    }


_NOT_MODES = {'NOT(AND)': 'AND', 'NOT(OR)': 'OR', 'NOT(EXACT)': 'EXACT'}


def _particle_data_field_valid(field):
    """Check whether one Particle Data sub-filter (mass/counts) is valid.

    Args:
        field (dict): {'enabled', 'expr', 'min', 'max'}.

    Returns:
        bool: True when disabled, or enabled with well-formed bounds.
    """
    if not field or not field.get('enabled'):
        return True
    expr = field.get('expr', 'at_least')
    mn, mx = field.get('min'), field.get('max')
    if expr == 'at_least':
        return isinstance(mn, (int, float)) and mn >= 0
    if expr == 'at_most':
        return isinstance(mx, (int, float)) and mx >= 0
    if expr == 'between':
        return (isinstance(mn, (int, float)) and isinstance(mx, (int, float))
                and mn >= 0 and mx >= 0 and mn < mx)
    return False


def particle_data_valid(pd_cfg):
    """Check whether an enabled Particle Data box's sub-filters are valid.

    A blocking policy is used (matching this dialog's existing convention
    of ignoring an axis entirely rather than half-applying it): if the box
    is enabled but any enabled sub-filter is invalid, the whole box must be
    treated as inactive by the caller until fixed.

    Args:
        pd_cfg (dict): The 'particle_data' config dict.

    Returns:
        bool: True when the box is off, or on with every enabled sub-filter
            valid.
    """
    if not pd_cfg or not pd_cfg.get('enabled'):
        return True
    return (_particle_data_field_valid(pd_cfg.get('mass') or {})
            and _particle_data_field_valid(pd_cfg.get('counts') or {}))


def active_axes(config):
    """List the filter axes that are enabled and meaningfully configured.

    A Particle Data box with invalid input is deliberately excluded here —
    per this dialog's blocking convention, an invalid sub-filter makes the
    whole box inactive until corrected (see :func:`particle_data_valid`).

    Args:
        config (dict): A per-sample filter configuration dict.

    Returns:
        list: Subset of ['composition', 'count', 'threshold',
            'particle_data'].
    """
    if not config:
        return []
    axes = []
    comp = config.get('composition') or {}
    if comp.get('enabled') and comp.get('isotopes'):
        axes.append('composition')
    cnt = config.get('count') or {}
    if cnt.get('enabled'):
        axes.append('count')
    thr = config.get('threshold') or {}
    if comp.get('enabled') and thr.get('enabled') and any(
            v and v > 0 for v in (thr.get('values') or {}).values()):
        axes.append('threshold')
    pd = config.get('particle_data') or {}
    if pd.get('enabled') and particle_data_valid(pd) and (
            (pd.get('mass') or {}).get('enabled')
            or (pd.get('counts') or {}).get('enabled')):
        axes.append('particle_data')
    return axes


def summarize_config(config):
    """Build a short human-readable summary of one filter configuration.

    Args:
        config (dict): A per-sample filter configuration dict.

    Returns:
        str: e.g. "Fe·Cr·Co | AND + ≥2 iso", or "No filter" when inactive.
    """
    if not config:
        return "No filter"
    parts = []
    comp = config.get('composition') or {}
    if comp.get('enabled') and comp.get('isotopes'):
        syms = list(dict.fromkeys(
            i.get('symbol') or i.get('label', '?')
            for i in comp['isotopes']))
        txt = '·'.join(syms)
        if len(txt) > 14:
            txt = txt[:13] + '…'
        parts.append(f"{txt} | {comp.get('mode', 'AND')}")
    cnt = config.get('count') or {}
    if cnt.get('enabled'):
        sym = {'exact': '=', 'min': '≥', 'max': '≤'}.get(cnt.get('op'), '=')
        parts.append(f"{sym}{cnt.get('value', 1)} iso")
    thr = config.get('threshold') or {}
    if comp.get('enabled') and thr.get('enabled') and any(
            v and v > 0 for v in (thr.get('values') or {}).values()):
        parts.append("thr")
    pd = config.get('particle_data') or {}
    if pd.get('enabled') and particle_data_valid(pd):
        bits = []
        for key, unit in (('mass', 'fg'), ('diameter', 'nm'),
                          ('counts', 'cts')):
            if key in _PD_DISABLED_KEYS:
                continue
            f = pd.get(key) or {}
            if not f.get('enabled'):
                continue
            expr = f.get('expr', 'at_least')
            if expr == 'at_least':
                bits.append(f"{key[0].upper()}≥{f.get('min')}{unit}")
            elif expr == 'at_most':
                bits.append(f"{key[0].upper()}≤{f.get('max')}{unit}")
            else:
                bits.append(f"{key[0].upper()}∈[{f.get('min')},{f.get('max')}]{unit}")
        if bits:
            parts.append(' & '.join(bits))
    return ' + '.join(parts) if parts else "No filter"


def referenced_labels(config):
    """Collect the isotope labels referenced by enabled filter axes.

    Args:
        config (dict): A per-sample filter configuration dict.

    Returns:
        set: Referenced isotope label strings.
    """
    refs = set()
    if not config:
        return refs
    comp = config.get('composition') or {}
    if comp.get('enabled'):
        for iso in comp.get('isotopes') or []:
            if isinstance(iso, dict) and iso.get('label'):
                refs.add(iso['label'])
    thr = config.get('threshold') or {}
    if thr.get('enabled'):
        for lbl, v in (thr.get('values') or {}).items():
            if v and v > 0:
                refs.add(lbl)
    return refs


def stale_from_available(avail, config):
    """Find referenced labels that are missing from the available set.

    Stale criteria are ignored at evaluation time but deliberately kept in
    the configuration so the user's setup survives upstream changes.

    Args:
        avail (set): Available isotope labels in the sample's data.
        config (dict): A per-sample filter configuration dict.

    Returns:
        set: Stale isotope label strings.
    """
    return {lbl for lbl in referenced_labels(config) if lbl not in avail}


def detected_labels(particle, thr_unit, thr_values):
    """Build the set of isotope labels detected in a particle.

    Detection means signal > 0 in ``elements``; if a per-isotope threshold
    is configured, the value in the threshold unit dict must also reach it,
    so near-zero detections don't count as "present".

    Args:
        particle (dict): One particle dict.
        thr_unit (str): 'elements' or 'element_mass_fg' (data schema keys).
        thr_values (dict): Mapping label -> minimum value, already pruned of
            stale and zero entries; empty when the threshold axis is off.

    Returns:
        set: Detected isotope labels.
    """
    els = particle.get('elements') or {}
    detected = set()
    for lbl, v in els.items():
        try:
            if not (v is not None and v > 0):
                continue
        except TypeError:
            _itk_log.exception("Handled exception in detected_labels")
            continue
        t = thr_values.get(lbl)
        if t:
            if thr_unit == 'elements':
                ref = v
            else:
                ref = (particle.get(thr_unit) or {}).get(lbl, 0)
            try:
                ref = float(ref)
            except (TypeError, ValueError):
                _itk_log.exception("Handled exception in detected_labels")
                continue
            if math.isnan(ref) or ref < t:
                continue
        detected.add(lbl)
    return detected


def _composition_passes(comp_labels, mode, detected):
    """Evaluate the isotopic composition axis for one particle.

    Each NOT(...) variant is computed by negating the corresponding base
    (AND / OR / EXACT) boolean, never by re-deriving it from negated
    per-isotope flags — that avoids accidentally flipping a quantifier.

    Args:
        comp_labels (set): Effective (non-stale) composition labels.
        mode (str): 'AND', 'OR', 'EXACT', 'NOT(AND)', 'NOT(OR)' or
            'NOT(EXACT)'.
        detected (set): Isotope labels detected in the particle.

    Returns:
        bool: True if the particle satisfies this axis.
    """
    base_mode = _NOT_MODES.get(mode, mode)
    if base_mode == 'AND':
        result = comp_labels <= detected
    elif base_mode == 'OR':
        result = bool(comp_labels & detected)
    elif base_mode == 'EXACT':
        result = detected == comp_labels
    else:
        result = True
    if mode in _NOT_MODES:
        result = not result
    return result


# Sub-filter keys with no usable whole-particle value in the data model —
# disabled/greyed out in the UI (see _build_particle_data_field) and always
# treated as inactive in validity/evaluation, regardless of stored config
# (protects against a stale config saved before this restriction existed).
_PD_DISABLED_KEYS = {'diameter'}


def _particle_scalar_mass_fg(particle):
    """Read a particle's whole-particle mass total (fg), if computed.

    ``particle['particle_mass_fg']`` is a dict keyed by element/isotope
    label (individual elements' contributions), not a usable whole-particle
    value — the real per-particle total lives in
    ``particle['totals']['total_particle_mass_fg']`` (summed across
    elements in ``mainwindow.py``'s mass-conversion pass; mass is additive,
    so this sum is physically valid). Returns None when not yet computed
    (e.g. before that conversion pass has run).

    Args:
        particle (dict): One particle dict.

    Returns:
        float or None.
    """
    return (particle.get('totals') or {}).get('total_particle_mass_fg')


# 'diameter' deliberately has no entry: there is no whole-particle diameter
# anywhere in this codebase. ``particle['particle_diameter_nm']`` is a dict
# keyed by element (one element's contribution can't represent the whole
# particle's physical size, and diameters aren't additive across elements
# the way mass is) — see the Diameter sub-box's disabled state in the UI.
_PD_SCALAR_GETTERS = {
    'mass': _particle_scalar_mass_fg,
    'counts': lambda particle: particle.get('total_counts'),
}


def _particle_data_field_passes(particle, key, field):
    """Evaluate one Particle Data sub-filter (mass or counts; diameter is
    disabled in the UI — see :data:`_PD_SCALAR_GETTERS`).

    Bounds are inclusive on both ends (a particle exactly at "min" or
    "max" passes), consistent for both "at least"/"at most" and "between".

    Args:
        particle (dict): One particle dict.
        key (str): 'mass' or 'counts'.
        field (dict): {'enabled', 'expr', 'min', 'max'}.

    Returns:
        bool: True if the sub-filter is inactive, or the particle's value
            satisfies it.
    """
    if not field or not field.get('enabled'):
        return True
    getter = _PD_SCALAR_GETTERS.get(key)
    if getter is None:
        return True
    try:
        val = float(getter(particle))
    except (TypeError, ValueError):
        return False
    if val != val:  # NaN
        return False
    expr = field.get('expr', 'at_least')
    if expr == 'at_least':
        return val >= field.get('min')
    if expr == 'at_most':
        return val <= field.get('max')
    if expr == 'between':
        return field.get('min') <= val <= field.get('max')
    return True


def particle_passes(particle, comp_labels, mode, count_cfg,
                    thr_unit, thr_values, particle_data=None):
    """Evaluate every active filter axis against one particle (AND logic).

    Args:
        particle (dict): One particle dict.
        comp_labels (set): Effective (non-stale) composition labels, empty
            when the composition axis is inactive.
        mode (str): 'AND', 'OR', 'EXACT', 'NOT(AND)', 'NOT(OR)' or
            'NOT(EXACT)'.
        count_cfg (dict): {'op': 'exact'|'min'|'max', 'value': int} or None.
        thr_unit (str): Threshold unit key.
        thr_values (dict): Effective per-isotope thresholds.
        particle_data (dict): Effective {'mass': field, 'diameter': field,
            'counts': field} sub-filters, or None when the Particle Data
            axis is inactive.

    Returns:
        bool: True if the particle passes every active filter.
    """
    detected = detected_labels(particle, thr_unit, thr_values)
    if comp_labels:
        if not _composition_passes(comp_labels, mode, detected):
            return False
    if count_cfg:
        n = len(detected)
        op = count_cfg.get('op', 'min')
        val = count_cfg.get('value', 1)
        if op == 'exact' and n != val:
            return False
        if op == 'min' and n < val:
            return False
        if op == 'max' and n > val:
            return False
    if particle_data:
        for key in ('mass', 'diameter', 'counts'):
            if not _particle_data_field_passes(
                    particle, key, particle_data.get(key)):
                return False
    return True


def effective_criteria(config, stale):
    """Resolve a filter configuration into evaluation-ready criteria.

    Stale labels are stripped here, so the evaluation simply ignores them
    while the stored configuration stays untouched.

    Args:
        config (dict): A per-sample filter configuration dict.
        stale (set): Stale isotope labels to ignore.

    Returns:
        tuple: (comp_labels, mode, count_cfg, thr_unit, thr_values,
            particle_data) ready for :func:`particle_passes`.
    """
    comp = config.get('composition') or {}
    comp_labels = set()
    mode = comp.get('mode', 'AND')
    if comp.get('enabled'):
        comp_labels = {iso['label'] for iso in comp.get('isotopes') or []
                       if isinstance(iso, dict) and iso.get('label')
                       and iso['label'] not in stale}
    cnt = config.get('count') or {}
    count_cfg = ({'op': cnt.get('op', 'min'), 'value': cnt.get('value', 1)}
                 if cnt.get('enabled') else None)
    thr = config.get('threshold') or {}
    thr_unit, thr_values = 'elements', {}
    if comp.get('enabled') and thr.get('enabled'):
        thr_unit = thr.get('unit', 'elements')
        thr_values = {lbl: v for lbl, v in (thr.get('values') or {}).items()
                      if v and v > 0 and lbl not in stale}
    pd = config.get('particle_data') or {}
    particle_data = None
    if pd.get('enabled') and particle_data_valid(pd):
        particle_data = {
            'mass': pd.get('mass') or _default_particle_data_field(),
            'diameter': pd.get('diameter') or _default_particle_data_field(),
            'counts': pd.get('counts') or _default_particle_data_field(),
        }
    return comp_labels, mode, count_cfg, thr_unit, thr_values, particle_data


def normalize_sources(upstreams):
    """Flatten the connected upstream dicts into one simple sample list.

    Every incoming sample — whether it arrives from a Single Sample node or
    as one of the samples / summed groups inside a Multi-Sample stream —
    becomes one entry, so the dialog can show a single easy-to-read list.
    Duplicate sample names are listed once (first occurrence wins).

    Args:
        upstreams (list): Upstream data dicts from every input link.

    Returns:
        list: Source entries with keys 'name', 'particles', 'total',
            'sample_data', 'conc', 'isotopes' and 'parent_window'.
    """
    sources, seen = [], set()
    for u in upstreams or []:
        if not u or u.get('type') not in _FILTERABLE_TYPES:
            continue
        if u.get('type') == 'multiple_sample_data':
            by_name, order = {}, []
            for p in u.get('particle_data') or []:
                s = p.get('source_sample', '')
                if s not in by_name:
                    by_name[s] = []
                    order.append(s)
                by_name[s].append(p)
            names = list(u.get('sample_names') or order)
            for name in names:
                if not name or name in seen:
                    continue
                seen.add(name)
                particles = by_name.get(name, [])
                sources.append({
                    'name': name,
                    'origin': 'multi',
                    'particles': particles,
                    'total': len(particles),
                    'sample_data': (u.get('data') or {}).get(name),
                    'conc': (u.get('concentration_meta') or {}).get(name),
                    'isotopes': u.get('selected_isotopes') or [],
                    'parent_window': u.get('parent_window'),
                })
        else:
            name = u.get('sample_name') or 'Sample'
            if name in seen:
                continue
            seen.add(name)
            particles = u.get('particle_data') or []
            sources.append({
                'name': name,
                'origin': 'single',
                'particles': particles,
                'total': u.get('total_particles', len(particles)),
                'sample_data': u.get('data'),
                'conc': (u.get('concentration_meta') or {}).get(name),
                'isotopes': u.get('selected_isotopes') or [],
                'parent_window': u.get('parent_window'),
            })
    return sources


def source_labels(source):
    """Collect the isotope labels available in one source entry.

    Args:
        source (dict): Source entry from :func:`normalize_sources`.

    Returns:
        set: Available isotope label strings.
    """
    labels = set()
    for iso in source.get('isotopes') or []:
        if isinstance(iso, dict) and iso.get('label'):
            labels.add(iso['label'])
    for p in source.get('particles') or []:
        els = p.get('elements')
        if isinstance(els, dict):
            labels.update(els.keys())
    return labels


def apply_sample_filter(source, config, retag=True):
    """Filter one source's particles with that sample's own configuration.

    Kept particles are shallow copies, so upstream data is never mutated.
    With ``retag`` enabled the copies are regrouped under the source's name:
    ``source_sample`` is rewritten to the sample name shown in the output's
    ``sample_names`` (e.g. a summed single sample whose particles still
    carry their replicate names), so every downstream figure can match
    particles to samples. The previous tag is preserved in
    ``original_sample`` and ``sum_group`` / ``is_summed`` keys pass through
    untouched; a summed group is filtered as a unit under its group name.

    Args:
        source (dict): Source entry from :func:`normalize_sources`.
        config (dict): That sample's filter configuration (or None).
        retag (bool): Rewrite ``source_sample`` to the source name.

    Returns:
        tuple: (kept_particles, stale) where ``stale`` is the set of
            criteria labels ignored because they are missing in this sample.
    """
    def tag(p):
        """Copy one particle and regroup it under the source's name.

        Args:
            p (dict): One particle dict.

        Returns:
            dict: Tagged shallow copy.
        """
        c = p.copy()
        if retag and c.get('source_sample') != source['name']:
            if c.get('source_sample'):
                c.setdefault('original_sample', c['source_sample'])
            c['source_sample'] = source['name']
        return c

    if not active_axes(config):
        return [tag(p) for p in source.get('particles') or []], set()
    stale = stale_from_available(source_labels(source), config)
    crit = effective_criteria(config, stale)
    kept = [tag(p) for p in source.get('particles') or []
            if particle_passes(p, *crit)]
    return kept, stale


def retag_particles(particles, name):
    """Regroup already-copied particles under a new sample name.

    The previous ``source_sample`` is preserved in ``original_sample`` so
    traceability is never lost. Used when several Single Sample inputs are
    merged into one output sample at the filter's exit.

    Args:
        particles (list): Particle copies owned by the caller.
        name (str): The new sample name.

    Returns:
        list: The same particles, regrouped under ``name``.
    """
    for p in particles:
        if p.get('source_sample') != name:
            if p.get('source_sample'):
                p.setdefault('original_sample', p['source_sample'])
            p['source_sample'] = name
    return particles


def merge_single_sources(sources, name):
    """Combine several single-sample source entries into one synthetic one.

    Totals add up, volumes add up, the dilution factor comes from the first
    member, transport availability requires every member to provide it, and
    the isotope list is the de-duplicated union.

    Args:
        sources (list): Single-origin source entries to merge.
        name (str): The merged sample name.

    Returns:
        dict: A synthetic source entry representing the merged sample.
    """
    isotopes, seen = [], set()
    for s in sources:
        for iso in s.get('isotopes') or []:
            lbl = iso.get('label') if isinstance(iso, dict) else str(iso)
            if lbl and lbl not in seen:
                seen.add(lbl)
                isotopes.append(iso)
    metas = [s.get('conc') for s in sources if s.get('conc')]
    if metas:
        conc = {
            'volume_ml': sum(m.get('volume_ml', 0.0) for m in metas),
            'dilution_factor': metas[0].get('dilution_factor', 1.0),
            'te_available': all(m.get('te_available', False) for m in metas),
        }
    else:
        conc = _empty_conc_meta()
    return {
        'name': name,
        'origin': 'single',
        'particles': [p for s in sources for p in s.get('particles') or []],
        'total': sum(s.get('total', 0) for s in sources),
        'sample_data': next((s.get('sample_data') for s in sources
                             if s.get('sample_data')), None),
        'conc': conc,
        'isotopes': isotopes,
        'parent_window': next((s.get('parent_window') for s in sources
                               if s.get('parent_window')), None),
    }


def prune_config_to_labels(config, labels):
    """Copy a filter configuration keeping only criteria for given labels.

    Used by "Apply to all samples" so a copied filter never starts out
    stale on samples that lack some isotopes.

    Args:
        config (dict): A per-sample filter configuration dict.
        labels (set): Isotope labels available in the target sample.

    Returns:
        dict: Deep copy of the configuration restricted to ``labels``.
    """
    import copy as _copy
    cfg = _copy.deepcopy(config)
    comp = cfg.get('composition') or {}
    comp['isotopes'] = [i for i in comp.get('isotopes') or []
                        if i.get('label') in labels]
    thr = cfg.get('threshold') or {}
    thr['values'] = {l: v for l, v in (thr.get('values') or {}).items()
                     if l in labels}
    return cfg


class ParticleFilterDialog(QDialog):
    """Two-pane configurator for the Particle Filter node.

    Left pane: every incoming sample with a check (include / exclude) and a
    short tag showing its filter. Right pane: the filter settings of the
    sample currently clicked — isotopic composition (chips + AND/OR/EXACT/
    NOT variants), isotopic count, per-isotope thresholds, and particle
    data (mass / diameter / counts). Each sample keeps its own settings; "Apply to
    all samples" copies the current one everywhere.
    The live preview runs on the upstream snapshot fetched once at dialog
    open and is debounced (~250 ms) after the last user change.
    """

    _PREVIEW_DEBOUNCE_MS = 250

    def __init__(self, parent, upstreams, sample_filters=None,
                 selected_sources=None, merged_name="Combined"):
        super().__init__(parent)
        self.setWindowTitle("Particle Filter Configuration")
        self.setModal(True)
        self.resize(980, 680)
        self.setMinimumSize(820, 560)
        self.setStyleSheet(self._style())
        _app_theme.themeChanged.connect(
            lambda _: self.setStyleSheet(self._style()))

        import copy as _copy
        self.parent_window = parent
        if isinstance(upstreams, dict):
            upstreams = [upstreams]
        self._upstreams = [u for u in (upstreams or []) if u]
        self._sources = normalize_sources(self._upstreams)
        self._src_by_name = {s['name']: s for s in self._sources}
        self._filters = _copy.deepcopy(sample_filters) if sample_filters else {}
        self._selected_sources = (list(selected_sources)
                                  if selected_sources is not None else None)
        self._merged_name = merged_name or "Combined"
        self._n_singles = sum(1 for s in self._sources
                              if s.get('origin') == 'single')

        self._elem_data = self._load_elem_data()
        self._current = None
        self._loading = False
        self._label_by_pair = {}
        self._stale_comp = []
        self._stale_thr = {}
        self._thr_values = {}
        self._thr_spins = {}

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(self._PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._update_preview)

        self._build()

        if self._sources:
            self._list.setCurrentRow(0)
        else:
            self._load_pane(None)
        self._update_preview()

    @staticmethod
    def _load_elem_data():
        """Load the periodic-table element metadata used by the chips.

        Returns:
            list: Element dicts, or an empty list when unavailable.
        """
        try:
            from results.results_periodic import CompactPeriodicTableWidget
            _tmp = CompactPeriodicTableWidget()
            elem_data = _tmp.get_elements()
            _tmp.deleteLater()
            return elem_data
        except Exception:
            _itk_log.exception("Handled exception in _load_elem_data")
            return []

    @staticmethod
    def _style():
        """Build the dialog stylesheet for the current app theme.

        Returns:
            str: ``_dialog_base_style()`` plus the group-box, list and
                spin/combo styling this dialog needs.
        """
        from widget.canvas_widgets import _dialog_base_style
        p = _app_theme.palette
        return _dialog_base_style() + f"""
        QGroupBox {{
            border: 1px solid {p.border};
            border-radius: 8px;
            margin-top: 12px;
            padding: 14px 10px 10px 10px;
            font-weight: 600;
            color: {p.text_primary};
            background: {p.bg_secondary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }}
        QGroupBox::indicator {{
            width: 16px; height: 16px;
            border-radius: 3px;
            border: 2px solid {p.border};
            background: {p.bg_secondary};
        }}
        QGroupBox::indicator:checked {{
            background: {p.accent};
            border-color: {p.accent};
        }}
        QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 4px 8px;
        }}
        QComboBox QAbstractItemView {{
            background: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QListWidget {{
            background: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 6px;
            font-size: 12px;
        }}
        QListWidget::item {{
            padding: 8px 6px;
            border-radius: 5px;
        }}
        QListWidget::item:selected {{
            background: {p.accent_soft};
            color: {p.text_primary};
        }}
        """

    def _build(self):
        """Assemble the two-pane layout: sample list on the left, the
        clicked sample's filter settings on the right, preview and OK/Cancel
        at the bottom."""
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        p = _app_theme.palette
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)
        lv.addWidget(self._section_label("Samples"))
        hint = QLabel("Check = include in output  ·  Click = edit its filter")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{p.text_muted}; font-size:11px; font-weight:400;")
        lv.addWidget(hint)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_checked)
        if self._sources:
            for s in self._sources:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, s['name'])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                checked = (self._selected_sources is None
                           or s['name'] in self._selected_sources)
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                self._list.addItem(item)
                self._refresh_row(item)
        else:
            ph = QListWidgetItem("No samples connected yet")
            ph.setFlags(Qt.NoItemFlags)
            self._list.addItem(ph)
        lv.addWidget(self._list, 1)

        self._merge_edit = None
        if self._n_singles >= 2:
            merge_lbl = QLabel(
                "Single-sample inputs exit as ONE sample, named:")
            merge_lbl.setWordWrap(True)
            merge_lbl.setStyleSheet(
                f"color:{p.text_muted}; font-size:11px; font-weight:400;")
            lv.addWidget(merge_lbl)
            self._merge_edit = QLineEdit(self._merged_name)
            self._merge_edit.setPlaceholderText("Combined")
            self._merge_edit.textChanged.connect(self._schedule_preview)
            lv.addWidget(self._merge_edit)
        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 0, 0, 0)
        rv.setSpacing(6)

        head = QHBoxLayout()
        self._pane_title = QLabel("Filter")
        self._pane_title.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{p.text_primary};")
        head.addWidget(self._pane_title, 1)
        self._btn_all = QPushButton("Apply to all samples")
        self._btn_all.setFixedHeight(28)
        self._btn_all.clicked.connect(self._apply_to_all)
        head.addWidget(self._btn_all)
        rv.addLayout(head)

        self._pane_scroll = QScrollArea()
        self._pane_scroll.setWidgetResizable(True)
        self._pane_scroll.setFrameShape(QFrame.NoFrame)
        self._pane = QWidget()
        pv = QVBoxLayout(self._pane)
        pv.setContentsMargins(0, 0, 6, 0)
        pv.setSpacing(8)
        self._build_pane(pv)
        pv.addStretch()
        self._pane_scroll.setWidget(self._pane)
        rv.addWidget(self._pane_scroll, 1)

        splitter.addWidget(right)
        splitter.setSizes([300, 660])
        root.addWidget(splitter, 1)

        self._preview = QLabel()
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet(
            f"padding:10px; background:{p.accent_soft}; border:1px solid "
            f"{p.border_strong}; border-radius:6px; color:{p.text_primary};"
            f" font-size:12px; font-weight:600;")
        root.addWidget(self._preview)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._try_accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _build_pane(self, pv):
        """Build the four filter-axis sections of the right pane.

        Args:
            pv (QVBoxLayout): Layout of the right pane.
        """
        p = _app_theme.palette

        self.grp_comp = QGroupBox("Isotopic Composition")
        self.grp_comp.setCheckable(True)
        cv = QVBoxLayout(self.grp_comp)
        cv.setSpacing(8)
        self._chip_selector = IsotopeChipSelector()
        self._chip_selector.setMinimumHeight(120)
        self._chip_selector.selection_changed.connect(self._on_chips_changed)
        cv.addWidget(self._chip_selector)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Match mode:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("AND: contains at least all selected isotopes", "AND")
        self.cmb_mode.addItem(
            "OR: contains at least one selected isotope", "OR")
        self.cmb_mode.addItem(
            "EXACT: only the selected isotopes, no others", "EXACT")
        self.cmb_mode.addItem(
            "NOT(AND) : missing at least one selected isotope", "NOT(AND)")
        self.cmb_mode.addItem(
            "NOT(OR): contains none of the selected isotopes", "NOT(OR)")
        self.cmb_mode.addItem(
            "NOT(EXACT):any set other than exactly the selected isotopes",
            "NOT(EXACT)")
        self.cmb_mode.currentIndexChanged.connect(self._schedule_preview)
        mode_row.addWidget(self.cmb_mode, 1)
        cv.addLayout(mode_row)
        self._stale_lbl = QLabel()
        self._stale_lbl.setWordWrap(True)
        self._stale_lbl.setStyleSheet(
            f"color:{p.text_muted}; font-style:italic; font-size:11px;"
            f" border:1px dashed #F59E0B; border-radius:6px;"
            f" padding:6px 8px;")
        self._btn_rm_stale = QPushButton("Remove stale")
        self._btn_rm_stale.setFixedHeight(26)
        self._btn_rm_stale.clicked.connect(self._remove_stale)
        stale_row = QHBoxLayout()
        stale_row.addWidget(self._stale_lbl, 1)
        stale_row.addWidget(self._btn_rm_stale, 0, Qt.AlignTop)
        cv.addLayout(stale_row)

        # Per-isotope signal threshold lives INSIDE Isotopic Composition,
        # not as a sibling box — it only modulates which isotopes count as
        # "present" for composition/count matching, so it's meaningless
        # without composition enabled (previously it was a fully
        # independent box, which let a user configure it while composition
        # was off; it looked "enabled" but had zero effect on filtering
        # until composition was also turned on — a confusing silent
        # no-op). Nesting it here plus disabling it when grp_comp is
        # unchecked (see below) makes the dependency structural instead of
        # just documented.
        self.grp_thr = QGroupBox("Per-isotope signal threshold")
        self.grp_thr.setCheckable(True)
        tv = QVBoxLayout(self.grp_thr)
        tv.setSpacing(8)
        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel("Threshold unit:"))
        self.cmb_unit = QComboBox()
        self.cmb_unit.addItem("Counts  (elements)", "elements")
        self.cmb_unit.addItem("Mass, fg  (element_mass_fg)", "element_mass_fg")
        self.cmb_unit.currentIndexChanged.connect(self._on_unit_changed)
        unit_row.addWidget(self.cmb_unit, 1)
        tv.addLayout(unit_row)
        thr_hint = QLabel(
            "Minimum value for an isotope to count as \"present\" — so "
            "near-zero detections are ignored. Leave at 0 for no threshold.")
        thr_hint.setWordWrap(True)
        thr_hint.setStyleSheet(
            f"color:{p.text_muted}; font-size:11px; font-weight:400;")
        tv.addWidget(thr_hint)
        self._thr_container = QWidget()
        self._thr_form = QFormLayout(self._thr_container)
        self._thr_form.setContentsMargins(0, 0, 0, 0)
        self._thr_form.setSpacing(6)
        tv.addWidget(self._thr_container)
        self.grp_thr.toggled.connect(self._schedule_preview)
        cv.addWidget(self.grp_thr)

        self.grp_comp.toggled.connect(self.grp_thr.setEnabled)
        self.grp_thr.setEnabled(self.grp_comp.isChecked())
        pv.addWidget(self.grp_comp)

        self.grp_count = QGroupBox("Isotopic Count")
        self.grp_count.setCheckable(True)
        cr = QHBoxLayout(self.grp_count)
        cr.addWidget(QLabel("Keep particles with"))
        self.cmb_op = QComboBox()
        self.cmb_op.addItem("exactly", "exact")
        self.cmb_op.addItem("at least", "min")
        self.cmb_op.addItem("at most", "max")
        self.cmb_op.currentIndexChanged.connect(self._schedule_preview)
        cr.addWidget(self.cmb_op)
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 99)
        self.spin_count.valueChanged.connect(self._schedule_preview)
        cr.addWidget(self.spin_count)
        cr.addWidget(QLabel("Detected Isotope(s)"))
        cr.addStretch()
        self.grp_count.toggled.connect(self._schedule_preview)
        pv.addWidget(self.grp_count)

        self.grp_pd = QGroupBox("Particle Data")
        self.grp_pd.setCheckable(True)
        pdv = QVBoxLayout(self.grp_pd)
        pdv.setSpacing(8)
        self._pd_fields = {}
        for key, title, unit in (('mass', 'Mass', 'fg'),
                                 ('diameter', 'Diameter', 'nm'),
                                 ('counts', 'Counts', 'cts')):
            self._pd_fields[key] = self._build_particle_data_field(
                pdv, key, title, unit, disabled=(key in _PD_DISABLED_KEYS))
        self.grp_pd.toggled.connect(self._schedule_preview)
        pv.addWidget(self.grp_pd)

    def _build_particle_data_field(self, parent_layout, key, title, unit,
                                    disabled=False):
        """Build one Particle Data sub-filter row (Mass, Diameter, Counts).

        Args:
            parent_layout (QVBoxLayout): The Particle Data box's layout.
            key (str): 'mass', 'diameter', or 'counts'.
            title (str): Checkbox label, e.g. "Mass".
            unit (str): Fixed unit label shown next to the inputs.
            disabled (bool): When True, the whole sub-box is greyed out and
                un-checkable — used for 'diameter', which has no
                whole-particle value anywhere in the data model (see
                :data:`_PD_SCALAR_GETTERS`). A tooltip explains why.

        Returns:
            dict: Widget handles for this field, used by
                :meth:`_pane_config` / :meth:`_load_pane`.
        """
        p = _app_theme.palette
        box = QGroupBox(title)
        box.setCheckable(True)
        v = QVBoxLayout(box)
        v.setSpacing(6)
        if disabled:
            box.setEnabled(False)
            box.setChecked(False)
            box.setToolTip(
                "No whole-particle diameter is currently computed — only "
                "a per-element breakdown exists, which can't represent "
                "the whole particle's size. Contact the dev team if "
                "particle-level diameter filtering is needed.")

        expr_row = QHBoxLayout()
        expr_row.addWidget(QLabel("Expression:"))
        cmb_expr = QComboBox()
        cmb_expr.addItem("at least", "at_least")
        cmb_expr.addItem("at most", "at_most")
        cmb_expr.addItem("between", "between")
        expr_row.addWidget(cmb_expr, 1)
        v.addLayout(expr_row)

        inputs_row = QHBoxLayout()
        lbl_min = QLabel("Minimum:")
        edit_min = QLineEdit()
        edit_min.setPlaceholderText(f"value in {unit}")
        lbl_max = QLabel("Maximum:")
        edit_max = QLineEdit()
        edit_max.setPlaceholderText(f"value in {unit}")
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color:{p.text_muted};")
        inputs_row.addWidget(lbl_min)
        inputs_row.addWidget(edit_min)
        inputs_row.addWidget(lbl_max)
        inputs_row.addWidget(edit_max)
        inputs_row.addWidget(unit_lbl)
        v.addLayout(inputs_row)

        err_lbl = QLabel()
        err_lbl.setWordWrap(True)
        err_lbl.setStyleSheet(
            "color:#DC2626; font-size:11px; font-weight:600;")
        err_lbl.setVisible(False)
        v.addWidget(err_lbl)

        parent_layout.addWidget(box)

        fields = {'box': box, 'cmb_expr': cmb_expr, 'lbl_min': lbl_min,
                  'edit_min': edit_min, 'lbl_max': lbl_max,
                  'edit_max': edit_max, 'err_lbl': err_lbl}

        def sync_visibility():
            expr = cmb_expr.currentData() or 'at_least'
            lbl_min.setVisible(expr in ('at_least', 'between'))
            edit_min.setVisible(expr in ('at_least', 'between'))
            lbl_max.setVisible(expr in ('at_most', 'between'))
            edit_max.setVisible(expr in ('at_most', 'between'))
            self._validate_particle_data_field(key, fields)
            self._schedule_preview()

        cmb_expr.currentIndexChanged.connect(sync_visibility)
        edit_min.textChanged.connect(
            lambda: (self._validate_particle_data_field(key, fields),
                     self._schedule_preview()))
        edit_max.textChanged.connect(
            lambda: (self._validate_particle_data_field(key, fields),
                     self._schedule_preview()))
        box.toggled.connect(sync_visibility)
        sync_visibility()
        return fields

    def _validate_particle_data_field(self, key, fields=None):
        """Validate one Particle Data sub-filter's inputs and show/hide its
        inline error message.

        Args:
            key (str): 'mass', 'diameter', or 'counts'.
            fields (dict): Widget handles for this field; looked up from
                ``self._pd_fields`` when omitted (that dict isn't
                populated yet during the field's own initial construction,
                so the builder passes its local ``fields`` directly).

        Returns:
            bool: True when the field is off, or on and valid.
        """
        f = fields if fields is not None else self._pd_fields[key]
        err_lbl = f['err_lbl']
        if not f['box'].isChecked():
            err_lbl.setVisible(False)
            return True
        expr = f['cmb_expr'].currentData() or 'at_least'

        def parse(edit):
            txt = edit.text().strip()
            if not txt:
                return None, "required"
            try:
                v = float(txt)
            except ValueError:
                return None, "must be numeric"
            if v < 0:
                return None, "must be >= 0"
            return v, None

        msg = None
        if expr == 'at_least':
            _v, msg = parse(f['edit_min'])
        elif expr == 'at_most':
            _v, msg = parse(f['edit_max'])
        else:
            mn, msg_mn = parse(f['edit_min'])
            mx, msg_mx = parse(f['edit_max'])
            msg = msg_mn or msg_mx
            if not msg and mn >= mx:
                msg = "minimum must be strictly less than maximum"
        err_lbl.setText(f"⚠ {msg}" if msg else "")
        err_lbl.setVisible(bool(msg))
        return msg is None

    @staticmethod
    def _section_label(text):
        """Build a small uppercase section label.

        Args:
            text (str): Label text.

        Returns:
            QLabel: Styled label widget.
        """
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size:10px; font-weight:700; letter-spacing:1px;"
            f" color:{_app_theme.palette.text_muted}; padding-bottom:2px;")
        return lbl

    def _refresh_row(self, item):
        """Refresh one sample row: name, particle count and filter tag."""
        name = item.data(Qt.UserRole)
        if not name:
            return
        s = self._src_by_name.get(name)
        cfg = self._filters.get(name)
        if name == self._current and not self._loading:
            cfg = self._pane_config()
        text = f"{name}   ({s['total'] if s else 0})"
        if active_axes(cfg):
            text += f"\n      ⚙ {summarize_config(cfg)}"
        item.setText(text)

    def _on_row_changed(self, current, previous):
        """Switch the right pane to the newly clicked sample.

        Args:
            current (QListWidgetItem): Newly selected row.
            previous (QListWidgetItem): Previously selected row.
        """
        if previous is not None and previous.data(Qt.UserRole):
            self._save_pane(previous.data(Qt.UserRole))
            self._refresh_row(previous)
        name = current.data(Qt.UserRole) if current else None
        self._load_pane(name)
        self._schedule_preview()

    def _on_item_checked(self, item):
        """React to an include/exclude checkbox toggle."""
        if not self._loading:
            self._schedule_preview()

    def _save_pane(self, name):
        """Store the right pane's state as the given sample's filter.

        Args:
            name (str): Sample name to store the configuration under.
        """
        if name and not self._loading:
            self._filters[name] = self._pane_config()

    def _load_pane(self, name):
        """Load one sample's filter configuration into the right pane.

        Args:
            name (str): Sample name, or None to disable the pane.
        """
        import copy as _copy
        self._loading = True
        self._current = name
        src = self._src_by_name.get(name)
        enabled = src is not None
        self._pane.setEnabled(enabled)
        self._btn_all.setEnabled(enabled and len(self._sources) > 1)
        self._pane_title.setText(
            f"Filter — {name}" if name else "Filter — no sample")

        cfg = default_filter_config()
        stored = self._filters.get(name)
        if stored:
            stored = _copy.deepcopy(stored)
            for key in cfg:
                if isinstance(stored.get(key), dict):
                    cfg[key].update(stored[key])

        avail = source_labels(src) if src else set()
        self._label_by_pair = {}
        pairs = []
        for iso in (src.get('isotopes') if src else None) or []:
            if not (isinstance(iso, dict) and iso.get('label')):
                continue
            try:
                key = (iso.get('symbol'), round(float(iso.get('mass', 0)), 4))
            except (TypeError, ValueError):
                _itk_log.exception("Handled exception in _load_pane")
                continue
            if key not in self._label_by_pair:
                self._label_by_pair[key] = iso['label']
                pairs.append((iso.get('symbol'), iso.get('mass')))

        comp_iso = cfg['composition'].get('isotopes') or []
        fresh = [i for i in comp_iso if i.get('label') in avail]
        self._stale_comp = [i for i in comp_iso if i.get('label') not in avail]
        thr_vals = cfg['threshold'].get('values') or {}
        self._thr_values = {l: v for l, v in thr_vals.items() if l in avail}
        self._stale_thr = {l: v for l, v in thr_vals.items()
                           if l not in avail}

        self._chip_selector.set_available_isotopes(self._elem_data, pairs)
        self._chip_selector.set_selected(fresh)
        self.grp_comp.setChecked(cfg['composition'].get('enabled', False))
        self.cmb_mode.setCurrentIndex(max(0, self.cmb_mode.findData(
            cfg['composition'].get('mode', 'AND'))))
        self.grp_count.setChecked(cfg['count'].get('enabled', False))
        self.cmb_op.setCurrentIndex(max(0, self.cmb_op.findData(
            cfg['count'].get('op', 'min'))))
        self.spin_count.setValue(int(cfg['count'].get('value', 2)))
        self.grp_thr.setChecked(cfg['threshold'].get('enabled', False))
        self.cmb_unit.setCurrentIndex(max(0, self.cmb_unit.findData(
            cfg['threshold'].get('unit', 'elements'))))
        self._rebuild_thr_rows()
        self._refresh_stale_area()

        pd = cfg.get('particle_data') or {}
        self.grp_pd.setChecked(pd.get('enabled', False))
        for key in ('mass', 'diameter', 'counts'):
            f = self._pd_fields[key]
            field_cfg = pd.get(key) or _default_particle_data_field()
            f['box'].setChecked(
                field_cfg.get('enabled', False)
                and key not in _PD_DISABLED_KEYS)
            f['cmb_expr'].setCurrentIndex(max(0, f['cmb_expr'].findData(
                field_cfg.get('expr', 'at_least'))))
            mn, mx = field_cfg.get('min'), field_cfg.get('max')
            f['edit_min'].setText('' if mn is None else _num_text(mn))
            f['edit_max'].setText('' if mx is None else _num_text(mx))
            self._validate_particle_data_field(key)
        self._loading = False

    def _read_particle_data_field(self, key):
        """Read one Particle Data sub-filter's widgets into a config dict.

        Args:
            key (str): 'mass', 'diameter', or 'counts'.

        Returns:
            dict: {'enabled', 'expr', 'min', 'max'}; 'min'/'max' are None
                when blank or unparsable — validity is checked separately
                by :func:`particle_data_valid`, this just reads raw state.
        """
        f = self._pd_fields[key]

        def parse(edit):
            txt = edit.text().strip()
            if not txt:
                return None
            try:
                return float(txt)
            except ValueError:
                return None

        return {
            'enabled': f['box'].isChecked(),
            'expr': f['cmb_expr'].currentData() or 'at_least',
            'min': parse(f['edit_min']),
            'max': parse(f['edit_max']),
        }

    def _pane_config(self):
        """Read the right pane into a filter configuration dict.

        Stale criteria are preserved unless removed by the user.

        Returns:
            dict: The current sample's filter configuration.
        """
        import copy as _copy
        self._sync_thr_values()
        isotopes = self._selected_isotopes() + _copy.deepcopy(self._stale_comp)
        values = {lbl: v for lbl, v in self._thr_values.items()
                  if v and v > 0 and lbl in self._thr_spins}
        values.update(self._stale_thr)
        return {
            'composition': {
                'enabled': self.grp_comp.isChecked(),
                'isotopes': isotopes,
                'mode': self.cmb_mode.currentData() or 'AND',
            },
            'count': {
                'enabled': self.grp_count.isChecked(),
                'op': self.cmb_op.currentData() or 'min',
                'value': self.spin_count.value(),
            },
            'threshold': {
                'enabled': self.grp_thr.isChecked(),
                'unit': self.cmb_unit.currentData() or 'elements',
                'values': values,
            },
            'particle_data': {
                'enabled': self.grp_pd.isChecked(),
                'mass': self._read_particle_data_field('mass'),
                'diameter': self._read_particle_data_field('diameter'),
                'counts': self._read_particle_data_field('counts'),
            },
        }

    def _apply_to_all(self):
        """Copy the current sample's filter to every other sample, pruned to
        each sample's available isotopes so nothing starts out stale."""
        if not self._current:
            return
        cfg = self._pane_config()
        self._filters[self._current] = cfg
        for s in self._sources:
            if s['name'] == self._current:
                continue
            self._filters[s['name']] = prune_config_to_labels(
                cfg, source_labels(s))
        for i in range(self._list.count()):
            self._refresh_row(self._list.item(i))
        self._schedule_preview()

    def _on_chips_changed(self):
        """React to a chip toggle: refresh threshold rows and the preview."""
        if self._loading:
            return
        self._sync_thr_values()
        self._rebuild_thr_rows()
        self._schedule_preview()

    def _on_unit_changed(self):
        """Relabel the threshold spinboxes for the newly selected unit."""
        suffix = "  cts" if self.cmb_unit.currentData() == 'elements' else "  fg"
        for spin in self._thr_spins.values():
            spin.setSuffix(suffix)
        self._schedule_preview()

    def _schedule_preview(self, *_):
        """Restart the debounce timer for the live preview."""
        if not self._loading:
            self._preview_timer.start()

    def _selected_isotopes(self):
        """Map the chip selection back to isotope dicts.

        Returns:
            list: Selected (non-stale) {'symbol', 'mass', 'label'} dicts.
        """
        out = []
        for sym, mass in sorted(self._chip_selector.get_selected()):
            try:
                lbl = self._label_by_pair.get((sym, round(float(mass), 4)))
            except (TypeError, ValueError):
                _itk_log.exception("Handled exception in _selected_isotopes")
                lbl = None
            if lbl:
                out.append({'symbol': sym, 'mass': mass, 'label': lbl})
        return out

    def _sync_thr_values(self):
        """Persist the current spinbox values into the working dict."""
        for lbl, spin in self._thr_spins.items():
            self._thr_values[lbl] = spin.value()

    def _rebuild_thr_rows(self):
        """Rebuild the threshold form: one spinbox per isotope selected in
        the composition section, plus greyed rows for stale entries."""
        while self._thr_form.count():
            item = self._thr_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._thr_spins = {}
        p = _app_theme.palette
        suffix = "  cts" if self.cmb_unit.currentData() == 'elements' else "  fg"

        labels = [iso['label'] for iso in self._selected_isotopes()]
        if not labels and not self._stale_thr:
            ph = QLabel("Select isotopes in the composition section above "
                        "to set per-isotope thresholds.")
            ph.setWordWrap(True)
            ph.setStyleSheet(
                f"color:{p.text_muted}; font-style:italic;"
                f" font-size:11px; font-weight:400;")
            self._thr_form.addRow(ph)
            return

        for lbl in labels:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1e12)
            spin.setDecimals(3)
            spin.setSuffix(suffix)
            spin.setValue(float(self._thr_values.get(lbl, 0.0)))
            spin.valueChanged.connect(self._schedule_preview)
            self._thr_spins[lbl] = spin
            self._thr_form.addRow(f"{lbl}  ≥", spin)

        for lbl, v in self._stale_thr.items():
            ghost = QLabel(f"{lbl}  ≥ {v:g} — no longer in this sample")
            ghost.setStyleSheet(
                f"color:{p.text_muted}; font-style:italic;"
                f" font-size:11px; font-weight:400;")
            self._thr_form.addRow(ghost)

    def _refresh_stale_area(self):
        """Show or hide the stale-criteria hint and Remove-stale button."""
        stale = [i.get('label', '?') for i in self._stale_comp]
        stale += [l for l in self._stale_thr if l not in stale]
        has = bool(stale)
        self._stale_lbl.setVisible(has)
        self._btn_rm_stale.setVisible(has)
        if has:
            self._stale_lbl.setText(
                "⚠ No longer in this sample's data (ignored while "
                "filtering): " + ", ".join(stale))

    def _remove_stale(self):
        """Remove every stale criterion of the current sample in one click."""
        self._stale_comp = []
        self._stale_thr = {}
        self._refresh_stale_area()
        self._rebuild_thr_rows()
        self._schedule_preview()

    def _checked_names(self):
        """List the sample names currently checked in the left list.

        Returns:
            list: Checked sample names.
        """
        names = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            name = item.data(Qt.UserRole)
            if name and item.checkState() == Qt.Checked:
                names.append(name)
        return names

    def _update_preview(self):
        """Recompute the pass counts on the upstream snapshot (debounced)."""
        if not self._sources:
            self._preview.setText(
                "No upstream data — connect and configure a sample node "
                "first.")
            return
        if self._current:
            self._save_pane(self._current)
            row = self._list.currentItem()
            if row is not None:
                self._refresh_row(row)
        chosen = [self._src_by_name[n] for n in self._checked_names()
                  if n in self._src_by_name]
        if not chosen:
            self._preview.setText(
                "No samples checked — the filter output is empty.")
            return
        total = sum(len(s['particles']) for s in chosen)
        kept_total, stale_all = 0, set()
        single_kept, single_total, parts = 0, 0, []
        chosen_singles = [s for s in chosen if s.get('origin') == 'single']
        merging = len(chosen_singles) >= 2
        for s in chosen:
            kept, stale = apply_sample_filter(s, self._filters.get(s['name']))
            kept_total += len(kept)
            stale_all |= stale
            if merging and s.get('origin') == 'single':
                single_kept += len(kept)
                single_total += len(s['particles'])
            else:
                parts.append(f"{s['name']}: {len(kept)}/{len(s['particles'])}")
        if merging:
            parts.insert(0, f"{self.get_merged_name()}: "
                            f"{single_kept}/{single_total}")
        lines = [f"{kept_total} / {total} particles pass"]
        if len(parts) > 1 or merging:
            lines.append(" · ".join(parts))
        if merging:
            lines.append(f"{len(chosen_singles)} single-sample inputs exit "
                         f"as one sample \"{self.get_merged_name()}\"")
        if stale_all:
            lines.append("⚠ Ignored stale criteria: "
                         + ", ".join(sorted(stale_all)))
        self._preview.setText("\n".join(lines))

    def get_merged_name(self):
        """Read the exit name for merged Single Sample inputs.

        Returns:
            str: The user-given name, falling back to "Combined".
        """
        if self._merge_edit is not None:
            return self._merge_edit.text().strip() or "Combined"
        return self._merged_name or "Combined"

    def _try_accept(self):
        """Block accept while the current sample's Particle Data box is
        checked but has invalid input, so a broken filter is never applied
        silently; otherwise close the dialog normally."""
        if self.grp_pd.isChecked():
            bad = [title for key, title in (('mass', 'Mass'),
                                            ('counts', 'Counts'))
                   if not self._validate_particle_data_field(key)]
            if bad:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Invalid Particle Data filter",
                    "Fix the highlighted Particle Data field(s) before "
                    "continuing: " + ", ".join(bad))
                return
        self.accept()

    def get_selected_sources(self):
        """Read the include/exclude check states.

        Returns:
            list: Checked sample names, or None when every sample is checked
                (so newly connected samples pass automatically).
        """
        if not self._sources:
            return None
        chosen = self._checked_names()
        if len(chosen) == len(self._sources):
            return None
        return chosen

    def get_sample_filters(self):
        """Assemble the per-sample filter configurations.

        Samples whose configuration has no active axis are dropped, so they
        behave as a plain passthrough.

        Returns:
            dict: Mapping sample name -> filter configuration.
        """
        if self._current:
            self._save_pane(self._current)
        return {name: cfg for name, cfg in self._filters.items()
                if active_axes(cfg)}


class ParticleFilterNode(QObject):
    """Composable particle filter node with per-sample settings.

    Any number of sample selector nodes can feed this node. Every incoming
    sample — including summed groups inside a Multi-Sample stream — appears
    in the configuration dialog, where each one carries its own filter
    settings. The output is regrouped so figures can read it: one chosen
    sample is emitted as single-sample data, several chosen samples are
    regrouped into multi-sample data. Filtering always operates on copies;
    upstream data is never mutated.
    """

    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Particle Filter"
        self.node_type = "particle_filter"
        self.parent_window = parent_window
        self.position = QPointF(0, 0)
        self._has_input = True
        self._has_output = True
        self.input_channels = ["input"]
        self.output_channels = ["output"]
        self.input_data = None
        self.scene_ref = None
        self.sample_filters = {}
        self.selected_sources = None
        self.merged_name = "Combined"
        self._stale = []
        self._incoming_names = []

    def set_position(self, pos):
        """Update the node position and notify the canvas item."""
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def process_data(self, input_data):
        """Receive pushed upstream data, refresh stale state and propagate."""
        self.input_data = input_data
        self._recompute_stale(normalize_sources([input_data]))
        self.configuration_changed.emit()

    def _pull_upstream_all(self):
        """Fetch the upstream dict from every input link.

        Falls back to the last pushed data when the node is not (yet) part
        of a scene.

        Returns:
            list: Non-None upstream data dicts.
        """
        out = []
        scene = self.scene_ref
        if scene is not None:
            try:
                for lk in getattr(scene, 'workflow_links', []):
                    if lk.sink_node is self:
                        out.append(lk.get_data())
            except Exception:
                _itk_log.exception("Handled exception in _pull_upstream_all")
        if not out and self.input_data is not None:
            out = [self.input_data]
        return [u for u in out if u]

    def get_output_data(self):
        """Gather every upstream stream, filter each chosen sample with its
        own settings, and regroup the result for downstream figures.

        Returns:
            dict: Single-sample data when one sample is chosen, multi-sample
                data when several are (regrouped with ``source_sample``
                tags); the unmodified upstream dict in the single-link
                no-filter case; None when upstream is unconfigured or no
                sample is selected.
        """
        upstreams = self._pull_upstream_all()
        if not upstreams:
            return None
        filterable = [u for u in upstreams
                      if u.get('type') in _FILTERABLE_TYPES]
        if not filterable:
            return upstreams[0]
        sources = normalize_sources(filterable)
        self._incoming_names = [s['name'] for s in sources]
        self._recompute_stale(sources)
        if self.selected_sources is None:
            chosen = sources
        else:
            chosen = [s for s in sources
                      if s['name'] in self.selected_sources]
        if not chosen:
            return None
        any_active = any(active_axes(self.sample_filters.get(s['name']))
                         for s in chosen)
        if len(filterable) == 1 and len(chosen) == len(sources):
            data = filterable[0]
            if not any_active:
                return data
            combined = []
            for s in sources:
                kept, _stale = apply_sample_filter(
                    s, self.sample_filters.get(s['name']), retag=False)
                combined.extend(kept)
            out = dict(data)
            out['particle_data'] = combined
            out['filtered_particles'] = len(combined)
            return out
        filtered = []
        for s in chosen:
            kept, _stale = apply_sample_filter(
                s, self.sample_filters.get(s['name']))
            filtered.append((s, kept))
        singles = [(s, k) for s, k in filtered
                   if s.get('origin') == 'single']
        others = [(s, k) for s, k in filtered
                  if s.get('origin') != 'single']
        final = []
        if len(singles) >= 2:
            name = (self.merged_name or '').strip() or 'Combined'
            merged_kept = []
            for _s, kept in singles:
                merged_kept.extend(retag_particles(kept, name))
            final.append((merge_single_sources(
                [s for s, _k in singles], name), merged_kept))
        else:
            final.extend(singles)
        final.extend(others)
        if len(final) == 1:
            return self._build_single_output(final[0][0], final[0][1])
        sources_f = [s for s, _k in final]
        results_f = [(s['name'], k, s['total']) for s, k in final]
        return self._build_multi_output(sources_f, results_f)

    def _build_single_output(self, source, kept):
        """Emit one chosen sample using the single-sample data schema.

        Args:
            source (dict): The chosen source entry.
            kept (list): Filtered particle copies.

        Returns:
            dict: Single-sample data dict.
        """
        sd = source['sample_data']
        return {
            'type': 'sample_data',
            'sample_name': source['name'],
            'data_types': {k: v for k, v in (sd or {}).items()
                           if isinstance(v, dict)},
            'data': sd,
            'particle_data': kept,
            'selected_isotopes': source['isotopes'],
            'total_particles': source['total'],
            'filtered_particles': len(kept),
            'sum_replicates': False,
            'replicate_samples': [],
            'concentration_meta': {
                source['name']: source['conc'] or _empty_conc_meta()},
            'parent_window': source['parent_window'] or self.parent_window,
        }

    def _build_multi_output(self, sources, results):
        """Regroup several chosen samples into the multi-sample data schema.

        Args:
            sources (list): The chosen source entries.
            results (list): (name, kept_particles, total) tuples.

        Returns:
            dict: Multi-sample data dict readable by every figure node.
        """
        names = [s['name'] for s in sources]
        combined = []
        for _name, kept, _total in results:
            combined.extend(kept)
        adt, csd = {}, {}
        for s in sources:
            sd = s['sample_data']
            if not sd:
                continue
            csd[s['name']] = sd
            for dt, dv in sd.items():
                if isinstance(dv, dict):
                    adt.setdefault(dt, {})
                    for el, val in dv.items():
                        adt[dt].setdefault(el, []).append(val)
        isotopes, seen = [], set()
        for s in sources:
            for iso in s['isotopes']:
                lbl = iso.get('label') if isinstance(iso, dict) else str(iso)
                if lbl and lbl not in seen:
                    seen.add(lbl)
                    isotopes.append(iso)
        pw = next((s['parent_window'] for s in sources
                   if s['parent_window']), self.parent_window)
        return {
            'type': 'multiple_sample_data',
            'sample_names': names,
            'original_sample_names': list(names),
            'sample_config': None,
            'data_types': adt,
            'data': csd,
            'particle_data': combined,
            'selected_isotopes': isotopes,
            'total_particles': sum(s['total'] for s in sources),
            'filtered_particles': len(combined),
            'sum_replicates': False,
            'concentration_meta': {
                s['name']: s['conc'] or _empty_conc_meta() for s in sources},
            'parent_window': pw,
        }

    def _recompute_stale(self, sources):
        """Refresh the cached stale-label list against the incoming samples.

        Args:
            sources (list): Source entries from :func:`normalize_sources`.
        """
        stale = set()
        for s in sources or []:
            cfg = self.sample_filters.get(s['name'])
            if cfg:
                stale |= stale_from_available(source_labels(s), cfg)
        self._stale = sorted(stale)

    def stale_labels(self):
        """List labels referenced by filters but missing in their samples.

        Returns:
            list: Stale isotope label strings.
        """
        return list(self._stale)

    def is_active(self):
        """Report whether the node is doing anything beyond passthrough.

        Returns:
            bool: True when any sample has an active filter or a sample
                subset is selected.
        """
        return any(active_axes(c) for c in self.sample_filters.values()) or (
            self.selected_sources is not None)

    def summary_text(self):
        """Build the live summary shown under the node icon.

        Returns:
            str: e.g. "2 samples + 1 filtered", a single sample's criteria
                when only one filter is set, "No filter" when inactive,
                "⚠ stale" when stale criteria are detected.
        """
        if self._stale:
            return "⚠ stale"
        parts = []
        if self.selected_sources is not None:
            n = len(self.selected_sources)
            parts.append(f"{n} sample" + ("s" if n != 1 else ""))
        filtered = {n: c for n, c in self.sample_filters.items()
                    if active_axes(c)}
        if len(filtered) == 1:
            parts.append(summarize_config(next(iter(filtered.values()))))
        elif len(filtered) > 1:
            parts.append(f"{len(filtered)} filtered")
        return ' + '.join(parts) if parts else "No filter"

    def configure(self, parent_window):
        """Open the configuration dialog (double-click).

        Returns:
            bool: True when the dialog was accepted.
        """
        snapshots = self._pull_upstream_all()
        dlg = ParticleFilterDialog(parent_window, snapshots,
                                   self.sample_filters, self.selected_sources,
                                   self.merged_name)
        if dlg.exec() == QDialog.Accepted:
            self.sample_filters = dlg.get_sample_filters()
            self.selected_sources = dlg.get_selected_sources()
            self.merged_name = dlg.get_merged_name()
            self._recompute_stale(normalize_sources(snapshots))
            self.configuration_changed.emit()
            ual = _ual()
            if ual:
                ual.log_action('DATA_OP',
                               f'Canvas node configured: {self.summary_text()}',
                               {'node': 'ParticleFilter',
                                'filtered_samples': list(self.sample_filters),
                                'selected_sources': self.selected_sources,
                                'stale_labels': self._stale})
            return True
        return False


def build_particle_filter_node_item():
    """Create the ParticleFilterNodeItem class bound to the canvas widgets.

    Imported lazily so this module never imports ``widget.canvas_widgets``
    at module level, avoiding a circular import. Call this from
    ``canvas_widgets`` after its base classes are defined.

    Returns:
        type: The ParticleFilterNodeItem class.
    """
    from widget.canvas_widgets import (
        NodeItem, _StatusNodeMixin, ModernNodeTooltip, DS)

    class ParticleFilterNodeItem(NodeItem, _StatusNodeMixin):
        """Funnel icon node item for the Particle Filter."""

        def __init__(self, wf, pw=None):
            super().__init__(wf)
            self.parent_window = pw
            wf.configuration_changed.connect(self.update)
            wf.configuration_changed.connect(self._trigger)
            self.setAcceptHoverEvents(True)
            self._tooltip_widget = ModernNodeTooltip()
            self._tooltip_widget.hide()
            self.hover_timer = QTimer()
            self.hover_timer.setSingleShot(True)
            self.hover_timer.timeout.connect(self._show_tooltip)
            self.hover_pos = None

        def itemChange(self, change, value):
            """Track scene membership so the node can pull via its links.

            Returns:
                object: Result of the base implementation.
            """
            if change == QGraphicsItem.ItemSceneHasChanged:
                self.workflow_node.scene_ref = value
            return super().itemChange(change, value)

        def paint(self, painter, option, widget=None):
            """Draw the teal funnel icon, status badge, stale warning ring
            and the live summary line.
            """
            wf = self.workflow_node
            stale = bool(wf.stale_labels())
            if stale:
                badge, bc = "⚠", DS.WARNING
            elif wf.is_active():
                badge, bc = "✓", DS.SUCCESS
            elif wf.input_data:
                badge, bc = "⟳", DS.PURPLE
            else:
                badge, bc = "", None
            if self._is_calc_busy():
                badge, bc = "⏳", DS.WARNING
            self.paint_icon_node(
                painter, (DS.TEAL, "#0D9488"),
                "fa6s.filter", "Filter",
                badge, bc,
            )
            cx = self.width / 2
            cy = self.icon_d / 2 + 4
            r = self.icon_d / 2
            if stale:
                painter.setPen(QPen(QColor(DS.WARNING), 2.5))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r + 5, r + 5)
            summary = wf.summary_text()
            painter.setFont(DS.font(DS.FONT_TINY))
            color = DS.WARNING if stale else _app_theme.palette.text_muted
            painter.setPen(QPen(QColor(color)))
            painter.drawText(
                QRectF(-20, cy + r + 24, self.width + 40, 14),
                Qt.AlignHCenter | Qt.AlignTop, summary)

        def _trigger(self):
            """Run the node calculation in a background thread on change."""
            self._run_calculation_async()

        def configure_node(self):
            """Open the filter configuration dialog (double-click)."""
            if self.parent_window:
                self.workflow_node.configure(self.parent_window)

        def _build_tooltip_lines(self):
            """Compose the tooltip content.

            Returns:
                list: Lines describing the per-sample filter configuration.
            """
            wf = self.workflow_node
            lines = ["Particle Filter"]
            incoming = getattr(wf, '_incoming_names', []) or []
            if wf.selected_sources is not None:
                sel = ", ".join(wf.selected_sources) or "none"
                lines.append(f"Samples: {sel}"
                             + (f" (of {len(incoming)})" if incoming else ""))
            elif len(incoming) > 1:
                lines.append(f"Samples: all ({len(incoming)})")
            shown = 0
            for name, cfg in wf.sample_filters.items():
                if not active_axes(cfg):
                    continue
                if shown >= 4:
                    rest = sum(1 for c in wf.sample_filters.values()
                               if active_axes(c)) - shown
                    lines.append(f"… and {rest} more filtered sample(s)")
                    break
                lines.append(f"{name}: {summarize_config(cfg)}")
                shown += 1
            if len(lines) == 1:
                lines.append("No filter — transparent passthrough")
            if wf.stale_labels():
                lines.append("⚠ Stale (not in upstream data): "
                             + ", ".join(wf.stale_labels()))
            return lines

        def _show_tooltip(self):
            """Show the floating tooltip next to the cursor."""
            if not self.isUnderMouse() or self.hover_pos is None:
                return
            lines = self._build_tooltip_lines()
            self._tooltip_widget.set_content(lines, accent_color=DS.TEAL)
            pos = self.hover_pos
            tw = self._tooltip_widget
            x = pos.x() + 14
            y = pos.y() - tw.height() - 8
            screen = QApplication.primaryScreen().availableGeometry()
            if x + tw.width() > screen.right():
                x = pos.x() - tw.width() - 14
            if y < screen.top():
                y = pos.y() + 20
            tw.move(int(x), int(y))
            tw.show()
            tw.raise_()

        def hoverEnterEvent(self, event):
            super().hoverEnterEvent(event)
            self.hover_pos = event.screenPos()
            self.hover_timer.start(400)

        def hoverMoveEvent(self, event):
            super().hoverMoveEvent(event)
            self.hover_pos = event.screenPos()
            if not self._tooltip_widget.isVisible():
                self.hover_timer.start(400)

        def hoverLeaveEvent(self, event):
            self.hover_timer.stop()
            self._tooltip_widget.hide()
            super().hoverLeaveEvent(event)
            self.hover_pos = None

    return ParticleFilterNodeItem
