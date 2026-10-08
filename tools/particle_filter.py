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
thresholds, and particle data (mass / counts range filters).

The output is regrouped so figures can read it: one chosen sample is
re-emitted as single-sample data, several chosen samples are regrouped into
multi-sample data with their ``source_sample`` tags, so every downstream
figure node consumes the result transparently.
"""

import math
import re

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QDialogButtonBox, QApplication, QGraphicsItem, QListWidget,
    QListWidgetItem, QSplitter, QScrollArea, QFrame, QLineEdit, QCheckBox,
    QRadioButton, QButtonGroup,
)
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QPointF, QRectF
from PySide6.QtGui import QPen, QColor

from tools.theme import theme as _app_theme
from results.results_periodic import IsotopeChipSelector
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.particle_filter")

_FILTERABLE_TYPES = ('sample_data', 'single_sample_data',
                     'multiple_sample_data')

# Process-wide cache of the static periodic-table element metadata used by
# the filter dialog's isotope chips (see ParticleFilterDialog._load_elem_data).
_ELEM_DATA_CACHE = None


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
    """Build one (mass or counts) sub-filter's default (inactive) state.

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
        for key, unit in (('mass', 'fg'), ('counts', 'cts')):
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


def _particle_scalar_counts(particle):
    """Read a particle's whole-particle raw signal count (machine
    response, dimensionless — same unit/source as the "Counts (elements)"
    Per-isotope signal threshold option, NOT a count of isotopes/elements).

    There is no top-level ``particle['total_counts']`` on the particle
    dicts that actually reach this filter — peak detection computes a
    ``total_counts`` value per isotope internally
    (``processing/peak_detection.py:1309/1361``), but only its per-isotope
    breakdown survives into the final particle dict, as
    ``particle['elements']`` (``processing/peak_detection.py:2129-2141``).
    That's the exact same dict ``detected_labels()`` already sums/reads
    for the (working) Per-isotope signal threshold feature. Summing it
    here is the whole-particle total in the same unit — physically valid
    since raw counts are additive across isotopes.

    Args:
        particle (dict): One particle dict.

    Returns:
        float: Sum of raw per-isotope counts; 0.0 if ``elements`` is empty
            or absent.
    """
    els = particle.get('elements') or {}
    total = 0.0
    for v in els.values():
        try:
            if v is not None and v > 0:
                total += v
        except TypeError:
            continue
    return total


_PD_SCALAR_GETTERS = {
    'mass': _particle_scalar_mass_fg,
    'counts': _particle_scalar_counts,
}


def _particle_data_field_passes(particle, key, field):
    """Evaluate one Particle Data sub-filter (mass or counts).

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
    try:
        val = float(_PD_SCALAR_GETTERS[key](particle))
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
        particle_data (dict): Effective {'mass': field, 'counts': field}
            sub-filters, or None when the Particle Data axis is inactive.

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
        for key in ('mass', 'counts'):
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
            'counts': pd.get('counts') or _default_particle_data_field(),
        }
    return comp_labels, mode, count_cfg, thr_unit, thr_values, particle_data


def _expand_upstream_entries(u):
    """Flatten ONE upstream dict into source entries, with no cross-stream
    dedup — every named sample inside it becomes its own entry, even if
    another upstream dict (or another name in this same one) repeats the
    name. This is the shared expansion step behind both
    :func:`normalize_sources` (which dedups on top of this) and duplicate-
    sample detection (which needs to see the un-deduped list to notice a
    collision before it gets silently collapsed).

    Args:
        u (dict): One upstream data dict.

    Returns:
        list: Source entries with keys 'name', 'origin', 'particles',
            'total', 'sample_data', 'conc', 'isotopes' and 'parent_window'.
    """
    if not u or u.get('type') not in _FILTERABLE_TYPES:
        return []
    out = []
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
            if not name:
                continue
            particles = by_name.get(name, [])
            out.append({
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
        particles = u.get('particle_data') or []
        out.append({
            'name': name,
            'origin': 'single',
            'particles': particles,
            # Not u.get('total_particles', ...): that field is the
            # sample node's pre-isotope-selection raw count, which
            # doesn't match what actually enters the filter once the
            # sample node's isotope selection has narrowed 'particles'.
            'total': len(particles),
            'sample_data': u.get('data'),
            'conc': (u.get('concentration_meta') or {}).get(name),
            'isotopes': u.get('selected_isotopes') or [],
            'parent_window': u.get('parent_window'),
        })
    return out


def _disambiguate_name(name, seen):
    """Return a unique sample name, appending ``" (N)"`` on collision.

    When ``name`` is already taken (present in ``seen``), the smallest free
    ``"name (2)"``, ``"name (3)"``, … is returned instead of dropping the
    entry. This is deliberately naive: a name that already ends in a literal
    ``" (2)"`` simply gets another suffix appended (``"S1 (2) (2)"``) rather
    than trying to parse and increment the existing number — same lightweight
    rule the classifier relies on so two identically-named input samples both
    stay visible and independently configurable instead of one silently
    winning (see :func:`normalize_sources`).

    Args:
        name (str): The desired sample name.
        seen (set): Names already assigned in this pass.

    Returns:
        str: ``name`` if free, else the first free ``"name (N)"``.
    """
    if name not in seen:
        return name
    k = 2
    while f"{name} ({k})" in seen:
        k += 1
    return f"{name} ({k})"


def normalize_sources(upstreams):
    """Flatten the connected upstream dicts into one simple sample list.

    Every incoming sample — whether it arrives from a Single Sample node or
    as one of the samples / summed groups inside a Multi-Sample stream —
    becomes one entry, so the dialog can show a single easy-to-read list.
    Same-named samples are NOT dropped: the second and later occurrences are
    disambiguated with a ``" (N)"`` suffix (see :func:`_disambiguate_name`)
    so every distinct input sample stays visible and independently
    addressable — the user may deliberately wire two instances of the same
    sample in to configure them differently. The particle payloads keep their
    original ``source_sample`` tag; each consumer retags to the (possibly
    renamed) entry name itself when it needs the grouping to follow the new
    name.

    Args:
        upstreams (list): Upstream data dicts from every input link.

    Returns:
        list: Source entries with keys 'name', 'particles', 'total',
            'sample_data', 'conc', 'isotopes' and 'parent_window'.
    """
    sources, seen = [], set()
    for u in upstreams or []:
        for entry in _expand_upstream_entries(u):
            if not entry['name']:
                continue
            name = _disambiguate_name(entry['name'], seen)
            seen.add(name)
            if name != entry['name']:
                entry = dict(entry, name=name)
            sources.append(entry)
    return sources


def _duplicate_signature(entry_a, entry_b):
    """Stable, content-based key identifying a suspected-duplicate pair.

    Based on names and particle counts (not node/link identity, which isn't
    stable across a project save/load) so a remembered resolution
    (:attr:`ParticleFilterNode._duplicate_resolutions`) still applies after
    reconnecting or reopening the project, as long as the same two sample
    "shapes" recur.

    Args:
        entry_a (dict): A source entry (see :func:`_expand_upstream_entries`).
        entry_b (dict): Another source entry being compared against it.

    Returns:
        str: Order-independent signature string.
    """
    pair = sorted([(entry_a['name'], entry_a['total']),
                   (entry_b['name'], entry_b['total'])])
    return f"{pair[0][0]}|{pair[0][1]}|{pair[1][0]}|{pair[1][1]}"


def _apply_duplicate_resolutions(entries, resolutions):
    """Apply previously-decided duplicate-sample resolutions to a raw
    (un-deduped) entry list, before the final same-name dedup in
    :func:`resolve_and_normalize_sources`.

    Args:
        entries (list): Un-deduped source entries from
            :func:`_expand_upstream_entries`.
        resolutions (dict): Signature -> resolution dict, as recorded by
            ``ParticleFilterNode._warn_duplicate_source``. Each resolution
            has an 'action' of 'keep_separate', 'combine', or 'ignore'.

    Returns:
        list: Transformed entries (still possibly containing same-name
            pairs the dedup step downstream will then collapse normally).
    """
    if not resolutions or not entries:
        return entries
    by_sig = {}
    for i, e in enumerate(entries):
        for j, o in enumerate(entries):
            if i >= j:
                continue
            if e['name'] != o['name'] and e['total'] != o['total']:
                continue
            sig = _duplicate_signature(e, o)
            res = resolutions.get(sig)
            if res:
                by_sig.setdefault(sig, []).append((i, j, res))

    drop = set()
    renames = {}
    combine_groups = []
    for sig, pairs in by_sig.items():
        i, j, res = pairs[0]
        action = res.get('action')
        if action == 'keep_separate':
            # Only the entry matching what was originally flagged as "new"
            # gets renamed — identified by matching name+total against the
            # stored original signature half tagged 'target'.
            target_name, target_total = res.get('target', (None, None))
            for idx in (i, j):
                e = entries[idx]
                if e['name'] == target_name and e['total'] == target_total:
                    renames[idx] = res.get('rename_to') or e['name']
        elif action == 'combine':
            combine_groups.append((i, j, res.get('combined_name') or 'Combined'))
        elif action == 'ignore':
            target_name, target_total = res.get('target', (None, None))
            for idx in (i, j):
                e = entries[idx]
                if e['name'] == target_name and e['total'] == target_total:
                    drop.add(idx)
                    # Drop only ONE of the pair. When the two duplicates are
                    # identical in both name AND count, the target matches
                    # both entries — without this break we'd drop the pair
                    # entirely and emit nothing, instead of ignoring one.
                    break

    out = []
    combined_idx = {}
    for i, j, cname in combine_groups:
        combined_idx[i] = cname
        combined_idx[j] = cname
    used_combine = set()
    for idx, e in enumerate(entries):
        if idx in drop:
            continue
        if idx in combined_idx:
            if idx in used_combine:
                continue
            cname = combined_idx[idx]
            group_indices = [k for k, v in combined_idx.items() if v == cname]
            used_combine.update(group_indices)
            members = [entries[k] for k in group_indices]
            merged_particles = []
            for m in members:
                merged_particles.extend(m['particles'])
            base = members[0]
            out.append(dict(base, name=cname, particles=merged_particles,
                            total=len(merged_particles)))
            continue
        if idx in renames:
            out.append(dict(e, name=renames[idx]))
        else:
            out.append(e)
    return out


def resolve_and_normalize_sources(upstreams, resolutions=None):
    """Like :func:`normalize_sources`, but first applies any remembered
    duplicate-sample resolutions so a decision the user already made
    (rename, combine, or ignore) is honored on every subsequent recompute
    instead of only at the moment it was detected.

    Args:
        upstreams (list): Upstream data dicts from every input link.
        resolutions (dict): ``ParticleFilterNode._duplicate_resolutions``,
            or None (behaves exactly like :func:`normalize_sources`).

    Returns:
        list: Source entries, same shape as :func:`normalize_sources`.
    """
    raw = []
    for u in upstreams or []:
        raw.extend(_expand_upstream_entries(u))
    raw = _apply_duplicate_resolutions(raw, resolutions or {})
    out, seen = [], set()
    for e in raw:
        if not e['name']:
            continue
        name = _disambiguate_name(e['name'], seen)
        seen.add(name)
        if name != e['name']:
            e = dict(e, name=name)
        out.append(e)
    return out



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


#: Relative tolerance for treating two dilution factors as "the same" (see
#: july22.md issue #7 design) -- tight enough to catch genuinely different
#: values including small decimals, loose enough to absorb float noise
#: regardless of magnitude (a fixed absolute epsilon would be wrong at both
#: ends: too tight for a factor of 5000, too loose for one of 0.001).
DILUTION_REL_TOL = 1e-5


def dilution_factors_conflict(members):
    """Whether members' dilution factors differ beyond floating-point tolerance.

    Per-particle representations (counts, mass, moles) are never affected by
    a dilution mismatch -- dilution factor only ever feeds particles/mL (see
    per_ml_factor in results/shared_plot_utils.py). This only decides
    whether that one derived number needs a resolution before merging.

    Args:
        members (list): ``[(name, meta_dict_or_None), ...]`` concentration-
            meta entries for the samples about to be merged/summed together.

    Returns:
        bool: True when 2+ genuinely different dilution factors are present.
    """
    factors = [(m or {}).get('dilution_factor', 1.0) for _n, m in members]
    if len(factors) < 2:
        return False
    first = factors[0]
    return not all(math.isclose(f, first, rel_tol=DILUTION_REL_TOL)
                   for f in factors)


class DilutionConflictDialog(QDialog):
    """Ask how to resolve a dilution-factor mismatch among merging samples.

    Every particle-level representation stays valid regardless of this
    choice; this only decides what, if anything, the ONE derived
    particles/mL number should be for the merged/summed sample.
    """

    def __init__(self, parent, group_label, members):
        """
        Args:
            parent: Dialog parent.
            group_label (str): Name of the merged/summed sample being created.
            members (list): ``[(name, meta_dict_or_None), ...]`` the
                conflicting sources.
        """
        super().__init__(parent)
        self.setWindowTitle("Dilution factor mismatch")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._groups = self._group_by_factor(members)

        lay = QVBoxLayout(self)
        rows = "\n".join(
            f"  • {', '.join(names)}: {factor:g}×"
            for factor, names in self._groups)
        lbl = QLabel(
            f"\"{group_label}\" combines samples that don't all share the "
            f"same dilution factor:\n\n{rows}\n\nEvery other representation "
            f"(counts, mass, moles) stays fully valid regardless of this "
            f"choice — only particles/mL for the combined sample is "
            f"affected. How should it be handled?")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        self._button_group = QButtonGroup(self)
        self._radio_factor = {}
        for factor, names in self._groups:
            rb = QRadioButton(
                f"Use {factor:g}× (from {', '.join(names)})")
            self._button_group.addButton(rb)
            lay.addWidget(rb)
            self._radio_factor[id(rb)] = factor

        custom_row = QHBoxLayout()
        self._custom_radio = QRadioButton("Enter a custom factor:")
        self._button_group.addButton(self._custom_radio)
        custom_row.addWidget(self._custom_radio)
        self._custom_spin = QDoubleSpinBox()
        self._custom_spin.setRange(0.0001, 1_000_000.0)
        self._custom_spin.setDecimals(4)
        self._custom_spin.setValue(self._groups[0][0] if self._groups else 1.0)
        self._custom_spin.setEnabled(False)
        custom_row.addWidget(self._custom_spin)
        custom_row.addStretch()
        lay.addLayout(custom_row)
        self._custom_radio.toggled.connect(self._custom_spin.setEnabled)

        self._unavailable_radio = QRadioButton(
            "Don't compute particles/mL for this merge")
        self._button_group.addButton(self._unavailable_radio)
        lay.addWidget(self._unavailable_radio)

        first_btn = self._button_group.buttons()[0] \
            if self._button_group.buttons() else None
        if first_btn:
            first_btn.setChecked(True)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    @staticmethod
    def _group_by_factor(members):
        """Group member names by (tolerance-equal) dilution factor value.

        Returns:
            list: ``[(factor, [names...]), ...]`` in first-seen order.
        """
        groups = []
        for name, meta in members:
            f = (meta or {}).get('dilution_factor', 1.0)
            for rep, names in groups:
                if math.isclose(f, rep, rel_tol=DILUTION_REL_TOL):
                    names.append(name)
                    break
            else:
                groups.append((f, [name]))
        return groups

    def resolution(self):
        """Build the resolution dict for the checked option.

        Returns:
            dict: ``{'choice': 'sample'|'manual'|'unavailable',
                'dilution_factor': float, 'source_label': str,
                'conflict_values': [(name, factor), ...]}``.
        """
        conflict_values = [(n, f) for f, names in self._groups for n in names]
        if self._unavailable_radio.isChecked():
            return {'choice': 'unavailable', 'dilution_factor': 0.0,
                    'source_label': 'unavailable (dilution mismatch)',
                    'conflict_values': conflict_values}
        if self._custom_radio.isChecked():
            v = self._custom_spin.value()
            return {'choice': 'manual', 'dilution_factor': v,
                    'source_label': f'manually entered ({v:g}×)',
                    'conflict_values': conflict_values}
        checked = self._button_group.checkedButton()
        factor = self._radio_factor.get(id(checked), self._groups[0][0])
        names = next((names for f, names in self._groups
                     if math.isclose(f, factor, rel_tol=DILUTION_REL_TOL)), [])
        return {'choice': 'sample', 'dilution_factor': factor,
                'source_label': f'{", ".join(names)} ({factor:g}×)',
                'conflict_values': conflict_values}


def resolve_dilution_conflict(parent_window, group_label, members):
    """Detect and, if needed, ask the user to resolve a dilution-factor
    mismatch among samples about to be merged/summed into one.

    Must only be called from a dialog's Accept/OK handler (never from a
    recompute/get_output_data path) -- the resolution it returns is meant to
    be stored once and reused on every subsequent recompute, not re-prompted.

    Args:
        parent_window: Dialog parent.
        group_label (str): Name of the merged/summed sample being created.
        members (list): ``[(name, meta_dict_or_None), ...]`` the sources
            being combined.

    Returns:
        dict | None | False: The resolution dict (see
            ``DilutionConflictDialog.resolution``) when a conflict existed
            and the user resolved it; ``None`` when there was no conflict at
            all (caller should combine normally, no resolution needed);
            ``False`` when the user cancelled -- caller must abort the merge
            entirely.
    """
    if not dilution_factors_conflict(members):
        return None
    dlg = DilutionConflictDialog(parent_window, group_label, members)
    if dlg.exec() != QDialog.Accepted:
        return False
    return dlg.resolution()


def merge_single_sources(sources, name, dilution_resolution=None):
    """Combine several single-sample source entries into one synthetic one.

    Totals add up, volumes add up, transport availability requires every
    member to provide it, and the isotope list is the de-duplicated union.

    The dilution factor comes from the first member UNLESS
    ``dilution_resolution`` is given (see :func:`resolve_dilution_conflict`),
    in which case that already-made decision is used instead -- this
    function never itself detects a conflict or prompts; that must already
    have happened at Accept/OK time, once, with the result passed in here on
    every subsequent recompute.

    Args:
        sources (list): Single-origin source entries to merge.
        name (str): The merged sample name.
        dilution_resolution (dict | None): A resolution dict from
            :func:`resolve_dilution_conflict`, or None when no mismatch
            resolution applies (normal first-member behavior).

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
        dilution_factor = (dilution_resolution['dilution_factor']
                           if dilution_resolution is not None
                           else metas[0].get('dilution_factor', 1.0))
        conc = {
            'volume_ml': sum(m.get('volume_ml', 0.0) for m in metas),
            'dilution_factor': dilution_factor,
            'te_available': all(m.get('te_available', False) for m in metas),
        }
        if dilution_resolution is not None:
            conc['dilution_mismatch'] = True
            conc['dilution_choice'] = dilution_resolution['choice']
            conc['dilution_source_label'] = dilution_resolution['source_label']
            conc['dilution_conflict_values'] = \
                dilution_resolution['conflict_values']
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


_FILT_SUFFIX_RE = re.compile(r'^(?P<base>.*?)\s*\(filt x(?P<n>\d+)\)\s*$')


def _bump_filt_suffix(name):
    """Append or increment a ``"(filt xN)"`` provenance suffix on a sample name.

    Every pass through a Particle Filter stamps its output samples with this
    suffix so a downstream node (and the user) can tell a filtered sample from
    an unfiltered one, and see how many filter hops it has been through. The
    count reflects filter hops only — it is bumped unconditionally, even by a
    filter with no active criteria (an inert pass-through still counts as a
    hop), so the number is stable regardless of the filter's configuration.

    A name that already carries the suffix has its number incremented
    (``"S1 (filt x1)"`` → ``"S1 (filt x2)"``); a fresh name gains
    ``"(filt x1)"``. A merged/grouped output (e.g. ``"Combined"`` or a custom
    group name) is a fresh name and therefore starts back at ``x1`` — the
    prior per-member hop counts are genuinely ambiguous once merged, so this
    just records "filtered by this node" rather than fabricating a combined
    count.

    Args:
        name (str): The sample name to stamp.

    Returns:
        str: The name with its filter-provenance suffix added/incremented.
    """
    m = _FILT_SUFFIX_RE.match(name or '')
    if m:
        return f"{m.group('base')} (filt x{int(m.group('n')) + 1})"
    return f"{name} (filt x1)"


def _retag_copy(p, name):
    """Shallow-copy a particle and regroup the copy under ``name``.

    Unlike :func:`retag_particles` (which mutates in place, for particles the
    caller already owns), this never touches the input dict — used when the
    particles are still shared references to upstream data that must not be
    mutated. The previous ``source_sample`` is preserved in ``original_sample``.

    Args:
        p (dict): One particle dict (possibly an upstream reference).
        name (str): The new sample name.

    Returns:
        dict: A retagged shallow copy.
    """
    c = p.copy()
    if c.get('source_sample') != name:
        if c.get('source_sample'):
            c.setdefault('original_sample', c['source_sample'])
        c['source_sample'] = name
    return c


def _apply_filt_provenance(out):
    """Stamp a filter output dict's sample names with ``"(filt xN)"``.

    Renames every sample-facing name in ``out`` (``sample_name`` /
    ``sample_names`` plus the matching ``data`` / ``concentration_meta`` keys
    and each particle's ``source_sample``) via :func:`_bump_filt_suffix`.
    Particles are copied, never mutated, so this is safe on the fast-path
    returns where ``particle_data`` may still reference upstream particles.
    Non-sample dict types (which a filter can't meaningfully stamp) pass
    through unchanged.

    Args:
        out (dict): A filter output data dict.

    Returns:
        dict: A new dict with stamped names, or ``out`` unchanged when it is
            not a sample/multiple-sample payload.
    """
    if not isinstance(out, dict):
        return out
    t = out.get('type')
    if t == 'sample_data':
        old = out.get('sample_name') or 'Sample'
        new = _bump_filt_suffix(old)
        out = dict(out)
        out['sample_name'] = new
        cm = out.get('concentration_meta')
        if isinstance(cm, dict) and old in cm:
            cm = dict(cm)
            cm[new] = cm.pop(old)
            out['concentration_meta'] = cm
        pd = out.get('particle_data')
        if isinstance(pd, list):
            out['particle_data'] = [_retag_copy(p, new) for p in pd]
        return out
    if t == 'multiple_sample_data':
        names = list(out.get('sample_names') or [])
        rename = {n: _bump_filt_suffix(n) for n in names}
        out = dict(out)
        out['sample_names'] = [rename[n] for n in names]
        data = out.get('data')
        if isinstance(data, dict):
            out['data'] = {rename.get(k, k): v for k, v in data.items()}
        cm = out.get('concentration_meta')
        if isinstance(cm, dict):
            out['concentration_meta'] = {
                rename.get(k, k): v for k, v in cm.items()}
        pd = out.get('particle_data')
        if isinstance(pd, list):
            out['particle_data'] = [
                _retag_copy(p, rename.get(p.get('source_sample'),
                                          p.get('source_sample')))
                for p in pd]
        return out
    return out


def build_multi_sample_dict(sources, parent_window=None):
    """Assemble a ``multiple_sample_data`` dict from normalized source entries.

    Used to combine several input links into one multi-sample stream while
    keeping every sample DISTINCT (the classifier's multi-input path): each
    entry in ``sources`` becomes its own sample, so two links carrying the
    same-named sample stay separate under their disambiguated names (see
    :func:`normalize_sources`) rather than collapsing into one pooled bucket.
    Per-sample ``data`` and ``concentration_meta`` are preserved. Particles
    are only copied when their ``source_sample`` tag needs to change to match a
    disambiguated name; otherwise the upstream references are reused, so a
    caller that mutates the result's particles must copy first (the classifier
    relabel step already copies every particle).

    Args:
        sources (list): Source entries from :func:`normalize_sources`.
        parent_window: Fallback parent window for the assembled dict.

    Returns:
        dict | None: A ``multiple_sample_data`` dict, or None if empty.
    """
    if not sources:
        return None
    combined = []
    for s in sources:
        name = s['name']
        for p in s.get('particles') or []:
            if p.get('source_sample') == name:
                combined.append(p)
            else:
                combined.append(_retag_copy(p, name))
    adt, csd = {}, {}
    for s in sources:
        sd = s.get('sample_data')
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
        for iso in s.get('isotopes') or []:
            lbl = iso.get('label') if isinstance(iso, dict) else str(iso)
            if lbl and lbl not in seen:
                seen.add(lbl)
                isotopes.append(iso)
    pw = next((s.get('parent_window') for s in sources
               if s.get('parent_window')), parent_window)
    names = [s['name'] for s in sources]
    return {
        'type': 'multiple_sample_data',
        'sample_names': names,
        'original_sample_names': list(names),
        'sample_config': None,
        'data_types': adt,
        'data': csd,
        'particle_data': combined,
        'selected_isotopes': isotopes,
        'total_particles': sum(s.get('total', 0) for s in sources),
        'filtered_particles': len(combined),
        'sum_replicates': False,
        'concentration_meta': {
            s['name']: s.get('conc') or _empty_conc_meta() for s in sources},
        'parent_window': pw,
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
    data (mass / counts). Each sample keeps its own settings; "Apply to
    selected samples" copies the current one to every checked sample.
    The live preview runs on the upstream snapshot fetched once at dialog
    open and is debounced (~250 ms) after the last user change.
    """

    _PREVIEW_DEBOUNCE_MS = 250

    def __init__(self, parent, upstreams, sample_filters=None,
                 selected_sources=None, merged_name="Combined",
                 owner_node=None, suppress_stale_warning=False,
                 merge_singles=True, sample_groups=None,
                 duplicate_resolutions=None, dilution_resolutions=None):
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
        self._owner_node = owner_node
        self._suppress_stale_warning = bool(suppress_stale_warning)
        if isinstance(upstreams, dict):
            upstreams = [upstreams]
        self._upstreams = [u for u in (upstreams or []) if u]
        # Resolution-aware, not plain normalize_sources: a duplicate the
        # user chose to "keep as two separate samples" must show up here as
        # two distinctly-named, independently-configurable rows, or the
        # whole point of that choice (setting different filters on each)
        # would be unreachable from this dialog.
        self._duplicate_resolutions = duplicate_resolutions or {}
        self._sources = resolve_and_normalize_sources(
            self._upstreams, self._duplicate_resolutions)
        self._src_by_name = {s['name']: s for s in self._sources}
        # {merged_group_name: resolution_dict}; a working copy the accept
        # handler updates in place, read back via get_dilution_resolutions().
        self._dilution_resolutions = dict(dilution_resolutions or {})
        self._filters = _copy.deepcopy(sample_filters) if sample_filters else {}
        self._groups = _copy.deepcopy(sample_groups) if sample_groups else {}
        self._selected_sources = (list(selected_sources)
                                  if selected_sources is not None else None)
        self._merged_name = merged_name or "Combined"
        self._merge_singles_init = bool(merge_singles)
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
        self._update_select_all_label()
        self._update_preview()

    @staticmethod
    def _load_elem_data():
        """Load the periodic-table element metadata used by the chips.

        Cached process-wide: this is static reference data, but fetching it
        meant building and destroying a whole CompactPeriodicTableWidget —
        ~0.5s of pure overhead on EVERY dialog open (the dominant cost of
        double-clicking a filter). Built once, reused thereafter.

        Returns:
            list: Element dicts, or an empty list when unavailable.
        """
        global _ELEM_DATA_CACHE
        if _ELEM_DATA_CACHE is not None:
            return _ELEM_DATA_CACHE
        try:
            from results.results_periodic import CompactPeriodicTableWidget
            _tmp = CompactPeriodicTableWidget()
            _ELEM_DATA_CACHE = _tmp.get_elements()
            _tmp.deleteLater()
        except Exception:
            _itk_log.exception("Handled exception in _load_elem_data")
            _ELEM_DATA_CACHE = []
        return _ELEM_DATA_CACHE

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

        self._merge_chk = None
        self._merge_edit = None
        if self._n_singles >= 2:
            self._merge_chk = QCheckBox("Merge single samples into one")
            self._merge_chk.setChecked(self._merge_singles_init)
            self._merge_chk.toggled.connect(self._on_merge_toggle)
            lv.addWidget(self._merge_chk)
            merge_lbl = QLabel(
                "Single-sample inputs exit as ONE sample, named:")
            merge_lbl.setWordWrap(True)
            merge_lbl.setStyleSheet(
                f"color:{p.text_muted}; font-size:11px; font-weight:400;")
            merge_lbl.setEnabled(self._merge_singles_init)
            lv.addWidget(merge_lbl)
            self._merge_edit = QLineEdit(self._merged_name)
            self._merge_edit.setPlaceholderText("Combined")
            self._merge_edit.setEnabled(self._merge_singles_init)
            self._merge_edit.textChanged.connect(self._schedule_preview)
            lv.addWidget(self._merge_edit)
            self._merge_lbl = merge_lbl
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
        self._btn_select_all = QPushButton("Select all samples")
        self._btn_select_all.setFixedHeight(28)
        self._btn_select_all.clicked.connect(self._toggle_select_all)
        head.addWidget(self._btn_select_all)
        self._btn_all = QPushButton("Apply to selected samples")
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
        group_row = QHBoxLayout()
        self._group_lbl = QLabel("Group for single samples only (optional):")
        group_row.addWidget(self._group_lbl)
        self._group_edit = QLineEdit()
        self._group_edit.setPlaceholderText(
            "e.g. Group A — samples sharing a name merge together")
        self._group_edit.textChanged.connect(self._schedule_preview)
        group_row.addWidget(self._group_edit, 1)
        pv.addLayout(group_row)
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
                                 ('counts', 'Counts', 'cts')):
            self._pd_fields[key] = self._build_particle_data_field(
                pdv, key, title, unit)
        self.grp_pd.toggled.connect(self._schedule_preview)
        pv.addWidget(self.grp_pd)

    def _build_particle_data_field(self, parent_layout, key, title, unit):
        """Build one Particle Data sub-filter row (Mass, Counts).

        Args:
            parent_layout (QVBoxLayout): The Particle Data box's layout.
            key (str): 'mass' or 'counts'.
            title (str): Checkbox label, e.g. "Mass".
            unit (str): Fixed unit label shown next to the inputs.

        Returns:
            dict: Widget handles for this field, used by
                :meth:`_pane_config` / :meth:`_load_pane`.
        """
        p = _app_theme.palette
        box = QGroupBox(title)
        box.setCheckable(True)
        v = QVBoxLayout(box)
        v.setSpacing(6)

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
            key (str): 'mass' or 'counts'.
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
        gname = self._groups.get(name)
        if gname:
            text += f"\n      \U0001F517 Group: {gname}"
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
            self._update_select_all_label()
            self._schedule_preview()

    def _save_pane(self, name):
        """Store the right pane's state as the given sample's filter.

        Args:
            name (str): Sample name to store the configuration under.
        """
        if name and not self._loading:
            self._filters[name] = self._pane_config()
            if self._src_by_name.get(name, {}).get('origin') == 'single':
                gname = self._group_edit.text().strip()
                if gname:
                    self._groups[name] = gname
                else:
                    self._groups.pop(name, None)

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
        is_single = enabled and src.get('origin') == 'single'
        self._group_edit.setEnabled(is_single)
        self._group_lbl.setEnabled(is_single)
        self._group_edit.setText(self._groups.get(name, '') if is_single else '')
        if enabled and not is_single:
            why = ("Not available — this sample is already a group summed "
                   "upstream by a Multi-Sample node; group summing here "
                   "only applies to individual Single Sample inputs.")
            self._group_edit.setPlaceholderText(why)
            self._group_edit.setToolTip(why)
            self._group_lbl.setToolTip(why)
        else:
            default_hint = ("e.g. Group A — samples sharing a name merge "
                            "together")
            self._group_edit.setPlaceholderText(default_hint)
            self._group_edit.setToolTip("")
            self._group_lbl.setToolTip("")
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
        for key in ('mass', 'counts'):
            f = self._pd_fields[key]
            field_cfg = pd.get(key) or _default_particle_data_field()
            f['box'].setChecked(field_cfg.get('enabled', False))
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
            key (str): 'mass' or 'counts'.

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
                'counts': self._read_particle_data_field('counts'),
            },
        }

    def _apply_to_all(self):
        """Copy the current sample's filter — and, for single-sample rows,
        its Group name — to every checked ("selected for output") sample,
        pruned to each sample's available isotopes so nothing starts out
        stale.

        "Selected" here means checked in the left list — include/exclude
        and which-sample-is-being-edited are two independent controls (see
        the "Check = include in output · Click = edit its filter" hint), so
        this only touches samples the user has actually opted into the
        output, not every connected sample regardless of inclusion.

        If applying would overwrite one or more checked samples' EXISTING,
        DIFFERENT group name, this asks for confirmation first (naming the
        affected samples) rather than silently clobbering an assignment the
        user made deliberately elsewhere — see _group_overwrite_conflicts.
        A no-op re-application (checked samples that already carry the same
        group name) never triggers this, only an actual change does.
        """
        if not self._current:
            return
        cfg = self._pane_config()
        src_cur = self._src_by_name.get(self._current)
        gname = (self._group_edit.text().strip()
                 if src_cur and src_cur.get('origin') == 'single' else '')
        checked = set(self._checked_names())
        conflicts = self._group_overwrite_conflicts(checked, gname)
        if conflicts and not self._confirm_group_overwrite(conflicts, gname):
            return
        self._filters[self._current] = cfg
        if src_cur and src_cur.get('origin') == 'single':
            if gname:
                self._groups[self._current] = gname
            else:
                self._groups.pop(self._current, None)
        for s in self._sources:
            if s['name'] == self._current or s['name'] not in checked:
                continue
            self._filters[s['name']] = prune_config_to_labels(
                cfg, source_labels(s))
            if s.get('origin') == 'single':
                if gname:
                    self._groups[s['name']] = gname
                else:
                    self._groups.pop(s['name'], None)
        for i in range(self._list.count()):
            self._refresh_row(self._list.item(i))
        self._schedule_preview()

    def _group_overwrite_conflicts(self, checked, gname):
        """List checked single-sample names whose EXISTING group name would
        actually change if _apply_to_all proceeded with ``gname``.

        Excludes ``self._current`` (the user is editing that one directly,
        so no surprise there) and any sample whose stored group already
        equals ``gname`` (a re-application that changes nothing).

        Args:
            checked (set): Names checked in the left list.
            gname (str): The group name about to be applied (may be '').

        Returns:
            list: Affected sample names, in source order.
        """
        out = []
        for s in self._sources:
            name = s['name']
            if (name == self._current or name not in checked
                    or s.get('origin') != 'single'):
                continue
            existing = (self._groups.get(name) or '').strip()
            if existing and existing != gname:
                out.append(name)
        return out

    def _confirm_group_overwrite(self, conflicts, gname):
        """Ask before overwriting samples' existing, different group names.

        Args:
            conflicts (list): Sample names from _group_overwrite_conflicts.
            gname (str): The group name about to be applied (may be '').

        Returns:
            bool: True if the user chose to proceed.
        """
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Overwrite existing group assignments?")
        shown = conflicts[:5]
        names_txt = ", ".join(f'"{n}"' for n in shown)
        if len(conflicts) > 5:
            names_txt += f", and {len(conflicts) - 5} more"
        new_txt = f'"{gname}"' if gname else "no group (ungrouped)"
        box.setText(
            f"{len(conflicts)} of the selected samples already belong to a "
            f"different group: {names_txt}.\n\nApplying now will overwrite "
            f"their group assignment to {new_txt}.\n\nContinue?")
        proceed = box.addButton("Overwrite", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.setDefaultButton(proceed)
        box.exec()
        return box.clickedButton() is proceed

    def _toggle_select_all(self):
        """Check every sample row, or uncheck every row if all are already
        checked — a single button doubling as Select all / Deselect all."""
        n = self._list.count()
        if n == 0:
            return
        all_checked = all(
            self._list.item(i).checkState() == Qt.Checked
            for i in range(n) if self._list.item(i).data(Qt.UserRole))
        new_state = Qt.Unchecked if all_checked else Qt.Checked
        for i in range(n):
            item = self._list.item(i)
            if item.data(Qt.UserRole):
                item.setCheckState(new_state)
        self._update_select_all_label()
        self._schedule_preview()

    def _update_select_all_label(self):
        """Relabel the Select-all button to reflect the current check state."""
        if not hasattr(self, '_btn_select_all'):
            return
        n = self._list.count()
        rows = [self._list.item(i) for i in range(n)]
        rows = [it for it in rows if it.data(Qt.UserRole)]
        all_checked = bool(rows) and all(
            it.checkState() == Qt.Checked for it in rows)
        self._btn_select_all.setText(
            "Deselect all samples" if all_checked else "Select all samples")

    def _on_merge_toggle(self, checked):
        """React to the "Merge single samples into one" checkbox."""
        if self._merge_edit is not None:
            self._merge_edit.setEnabled(checked)
        if getattr(self, '_merge_lbl', None) is not None:
            self._merge_lbl.setEnabled(checked)
        self._schedule_preview()

    def get_merge_singles(self):
        """Report whether single-sample inputs should merge into one.

        Returns:
            bool: The checkbox state, or True when fewer than two
                single-sample inputs are connected (no checkbox exists).
        """
        if self._merge_chk is not None:
            return self._merge_chk.isChecked()
        return True

    def get_sample_groups(self):
        """Read the per-sample custom group names set for single-sample
        inputs (empty names are dropped — they mean "no custom group").

        Returns:
            dict: Sample name -> group name, single-sample entries only.
        """
        if self._current:
            self._save_pane(self._current)
        return {k: v for k, v in self._groups.items() if v}

    def get_dilution_resolutions(self):
        """Return the current dilution-mismatch resolutions.

        Returns:
            dict: {merged_group_name: resolution_dict}.
        """
        return dict(self._dilution_resolutions)

    def _compute_pending_merge_groups(self):
        """Mirror ParticleFilterNode._get_output_data_impl's group-formation
        logic against the dialog's OWN in-progress state (not yet committed
        to the node), so a dilution-mismatch check can run at Accept time
        before anything is saved.

        Returns:
            dict: {group_name: [sample_name, ...]} for every group of 2+
                single-origin samples that will actually be merged/summed
                together once this dialog is accepted.
        """
        singles = [s for s in self._sources if s.get('origin') == 'single']
        groups = {}
        if self._merge_chk is not None and self._merge_chk.isChecked():
            if len(singles) >= 2:
                gname = ((self._merge_edit.text().strip()
                         if self._merge_edit else '') or 'Combined')
                groups[gname] = [s['name'] for s in singles]
        else:
            for s in singles:
                gname = (self._groups.get(s['name']) or '').strip()
                if gname:
                    groups.setdefault(gname, []).append(s['name'])
        return {g: names for g, names in groups.items() if len(names) >= 2}

    def _resolve_pending_dilution_conflicts(self):
        """Run the dilution-mismatch check for every group about to form.

        Called from the Accept/OK handler, once. Updates
        self._dilution_resolutions in place for groups that need one and
        clears stale entries for groups that no longer conflict.

        Returns:
            bool: True to proceed with accept, False if the user cancelled
                a merge because of an unresolved dilution mismatch.
        """
        for gname, names in self._compute_pending_merge_groups().items():
            members = [(n, self._src_by_name.get(n, {}).get('conc'))
                       for n in names]
            res = resolve_dilution_conflict(self, gname, members)
            if res is False:
                return False
            if res is not None:
                self._dilution_resolutions[gname] = res
            else:
                self._dilution_resolutions.pop(gname, None)
        return True

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
        kept_total, stale_all, kept_by_name = 0, set(), {}
        for s in chosen:
            kept, stale = apply_sample_filter(s, self._filters.get(s['name']))
            kept_total += len(kept)
            stale_all |= stale
            kept_by_name[s['name']] = (len(kept), len(s['particles']))

        chosen_singles = [s for s in chosen if s.get('origin') == 'single']
        merge_dominant = self.get_merge_singles()
        grouped, ungrouped, group_order = {}, [], []
        if merge_dominant:
            # Merge-all dominates: every single sample folds into one
            # bucket for the preview too, regardless of any custom group
            # name — matches the actual output logic (_get_output_data_impl).
            ungrouped = list(chosen_singles)
        else:
            for s in chosen_singles:
                gname = (self._groups.get(s['name']) or '').strip()
                if gname:
                    if gname not in grouped:
                        grouped[gname] = []
                        group_order.append(gname)
                    grouped[gname].append(s)
                else:
                    ungrouped.append(s)
        merging = len(ungrouped) >= 2 and merge_dominant

        parts = []
        for gname in group_order:
            gk = sum(kept_by_name[s['name']][0] for s in grouped[gname])
            gt = sum(kept_by_name[s['name']][1] for s in grouped[gname])
            parts.append(f"{gname}: {gk}/{gt}")
        if merging:
            uk = sum(kept_by_name[s['name']][0] for s in ungrouped)
            ut = sum(kept_by_name[s['name']][1] for s in ungrouped)
            parts.append(f"{self.get_merged_name()}: {uk}/{ut}")
        else:
            for s in ungrouped:
                k, t = kept_by_name[s['name']]
                parts.append(f"{s['name']}: {k}/{t}")
        for s in chosen:
            if s.get('origin') != 'single':
                k, t = kept_by_name[s['name']]
                parts.append(f"{s['name']}: {k}/{t}")

        lines = [f"{kept_total} / {total} particles pass"]
        if parts:
            lines.append(" · ".join(parts))
        if group_order:
            n_grouped = sum(len(m) for m in grouped.values())
            lines.append(
                f"{n_grouped} sample" + ("s" if n_grouped != 1 else "")
                + f" grouped into {len(group_order)} named group"
                + ("s" if len(group_order) != 1 else "") + ": "
                + ", ".join(group_order))
        if merging:
            lines.append(f"{len(ungrouped)} remaining single-sample inputs "
                         f"exit as one sample \"{self.get_merged_name()}\"")
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
        silently; otherwise remind the user that OK can change whatever
        this filter feeds downstream, then close the dialog normally.

        The reminder used to only fire when a diff against the dialog's
        opening snapshot said something had actually changed, gated on
        finding a currently-open downstream plot window via a
        scene-graph walk. In practice that stayed silent even on runs
        where the user visibly watched a downstream chart's values change
        after clicking OK — replaced (per explicit user decision) with an
        unconditional reminder on every OK, since "did it really change"
        and "is a window really open somewhere downstream" are exactly the
        two things that kept failing to detect correctly live. A "don't
        show this again" opt-out keeps this from turning into nag-ware for
        someone who has already acknowledged it: it is application-wide and
        permanent, stored in :mod:`tools.render_settings` and shared with
        the sample-selector nodes' copy of the same reminder
        (``widget.canvas_widgets._warn_before_apply_changes``), so ticking
        it here silences every node on the canvas and stays silenced after
        a restart.
        """
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
        if self._current:
            self._save_pane(self._current)
        if (self._merge_chk is not None and self._merge_chk.isChecked()
                and any((v or '').strip() for v in self._groups.values())):
            from PySide6.QtWidgets import QMessageBox
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Merge-all overrides custom groups")
            box.setText(
                "\"Merge single samples into one\" is checked, and at least "
                "one sample also has a custom Group name set. Merge-all is "
                "the coarser control and wins: every single-sample input "
                "will exit as one sample named "
                f"\"{self.get_merged_name()}\", and the custom group "
                "name(s) will be ignored for this filter.\n\nUncheck "
                "\"Merge single samples into one\" if you want the custom "
                "groups to take effect instead.")
            proceed = box.addButton("Merge anyway", QMessageBox.AcceptRole)
            box.addButton("Go back", QMessageBox.RejectRole)
            box.setDefaultButton(proceed)
            box.exec()
            if box.clickedButton() is not proceed:
                return
        from tools.render_settings import (stale_warning_suppressed,
                                           set_stale_warning_suppressed)
        if not (self._suppress_stale_warning or stale_warning_suppressed()):
            from PySide6.QtWidgets import QMessageBox, QCheckBox
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Downstream plots may change")
            box.setText(
                "This filter feeds sample selectors, other filters, and "
                "plot/results nodes downstream — single-sample, "
                "multi-sample, and batch alike. Applying now will pass "
                "through with today's settings, so any open plot window "
                "fed by this filter will update to match.\n\nIf you want "
                "to keep a plot's current view, save it first, then come "
                "back and apply this filter.")
            dont_show = QCheckBox("Don't show this again (any node)")
            box.setCheckBox(dont_show)
            proceed = box.addButton("Proceed anyway", QMessageBox.AcceptRole)
            box.addButton("Go back", QMessageBox.RejectRole)
            box.setDefaultButton(proceed)
            box.exec()
            self._suppress_stale_warning_now = dont_show.isChecked()
            if dont_show.isChecked():
                set_stale_warning_suppressed(True)
            if box.clickedButton() is not proceed:
                return
        self.accept()

    def stale_warning_suppressed(self):
        """Read whether "Don't show this again" was checked on last accept.

        Reports this dialog's own view only. The authoritative, shared
        opt-out now lives in :mod:`tools.render_settings` and is written at
        the same moment the box is ticked; this stays so the owning node
        keeps its local copy in step and older callers keep working.

        Returns:
            bool: True if the reminder should be skipped for this node from
                now on — either it was already suppressed coming in, or the
                user just checked the box while accepting.
        """
        return self._suppress_stale_warning or getattr(
            self, '_suppress_stale_warning_now', False)

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
        # Unlike most node types, this one already walks every incoming
        # link itself (see _pull_upstream_all) rather than reading a single
        # overwritable input_data slot, so more than one upstream is safe —
        # opt in to the Manage Connections / scene.add_link multi-input rule.
        self.supports_multi_input = True
        self.input_data = None
        self.scene_ref = None
        self.sample_filters = {}
        self.selected_sources = None
        self.merged_name = "Combined"
        self.merge_singles = True
        self.sample_groups = {}
        # Signature -> resolution dict (see _duplicate_signature /
        # _warn_duplicate_source), remembering how a suspected duplicate
        # sample (same name or same particle count feeding this filter via
        # two different paths, e.g. a Multi-Sample stream AND a Single
        # Sample node both carrying "S1") was resolved, so reconnecting or
        # reopening the project doesn't ask again for the same pair.
        self.duplicate_resolutions = {}
        # {merged_group_name: resolution_dict} -- how a dilution-factor
        # mismatch among the samples merging into that group name was
        # resolved (see resolve_dilution_conflict / DilutionConflictDialog),
        # made once at Accept/OK time in ParticleFilterDialog._try_accept
        # and reused here on every recompute rather than re-prompted.
        self.dilution_resolutions = {}
        self._stale = []
        self._incoming_names = []
        # Legacy per-node opt-out for the "applying this will change open
        # plots" reminder (see ParticleFilterDialog._try_accept). The live
        # opt-out is application-wide (tools/render_settings.py); this is
        # still honoured if set, and kept so saved state stays valid.
        self.suppress_stale_warning = False

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

    def _stored_sample_names(self):
        """Sample names this node currently carries settings for.

        The union of every name-keyed piece of state — active per-sample
        filters, the output selection, and custom groups. Used to compare
        stored settings against what's actually connected now.
        """
        names = {n for n, c in self.sample_filters.items() if active_axes(c)}
        names |= set(self.sample_groups)
        if self.selected_sources:
            names |= set(self.selected_sources)
        return names

    def reconcile_incoming(self, parent_window=None, new_link=None):
        """Reconcile stored per-sample settings against the samples actually
        feeding this node right now — call after the input changes (e.g. a
        duplicated filter is wired to a different source). GUI thread only,
        since a partial mismatch shows a dialog.

        - No stored settings, or nothing connected: do nothing.
        - Total mismatch (no stored sample name is present in the incoming
          data): wipe the name-keyed settings to a blank slate, so a
          duplicated-then-rewired filter never carries the previous
          source's sample/isotope names into its warnings or output.
        - Partial mismatch (some stored names present, some gone): keep the
          settings but inform the user which matched and which didn't,
          offering to clear the settings for the samples that are gone.

        Args:
            parent_window: Dialog parent.
            new_link (WorkflowLink): The link that was *just* added, if this
                call was triggered by a fresh connection (scene.add_link) —
                None for any other trigger. Only when present do we also
                check whether that new source looks like a duplicate of an
                already-connected one (see _check_duplicate_source);
                reusing this same trigger point per the established
                decision that this check should fire on new connections
                only, not on every recompute.
        """
        if new_link is not None:
            self._check_duplicate_source(new_link, parent_window)
        sources = resolve_and_normalize_sources(
            self._pull_upstream_all(), self.duplicate_resolutions)
        incoming = {s['name'] for s in sources}
        stored = self._stored_sample_names()
        if not stored or not incoming:
            return
        matched = stored & incoming
        missing = stored - incoming
        if not matched:
            self.sample_filters = {}
            self.selected_sources = None
            self.sample_groups = {}
            self._recompute_stale(sources)
            self.configuration_changed.emit()
            return
        if missing:
            self._warn_partial_mismatch(
                parent_window, sorted(matched), sorted(missing),
                sorted(incoming - stored))

    def _check_duplicate_source(self, new_link, parent_window=None):
        """Detect whether the source that was just wired in looks like a
        duplicate of one already feeding this filter — same sample name, or
        same particle count (a cheap heuristic, not a deep content
        comparison, per explicit design: this needs to stay fast even on
        large particle sets). If a matching pair is found and hasn't
        already been resolved once before (see duplicate_resolutions),
        prompt the user to decide how to handle it.

        Args:
            new_link (WorkflowLink): The just-added link feeding this node.
            parent_window: Dialog parent.
        """
        scene = self.scene_ref
        if scene is None:
            return
        try:
            new_entries = _expand_upstream_entries(new_link.get_data())
        except Exception:
            _itk_log.exception(
                "Handled exception in _check_duplicate_source")
            return
        if not new_entries:
            return
        other_entries = []
        for lk in getattr(scene, 'workflow_links', []):
            if lk.sink_node is not self or lk is new_link:
                continue
            try:
                other_entries.extend(_expand_upstream_entries(lk.get_data()))
            except Exception:
                _itk_log.exception(
                    "Handled exception in _check_duplicate_source")
        for ne in new_entries:
            for oe in other_entries:
                same_name = ne['name'] == oe['name']
                same_count = ne['total'] == oe['total'] and ne['total'] > 0
                if not (same_name or same_count):
                    continue
                sig = _duplicate_signature(ne, oe)
                if sig in self.duplicate_resolutions:
                    continue
                self._warn_duplicate_source(
                    parent_window, new_link, ne, oe, sig)
                return

    def _warn_duplicate_source(self, parent_window, new_link, new_entry,
                               existing_entry, sig):
        """Ask the user how to handle a suspected duplicate sample.

        Args:
            parent_window: Dialog parent.
            new_link (WorkflowLink): The just-added link that triggered
                this — used directly by the "disconnect" choice.
            new_entry (dict): The just-connected source entry that triggered
                this (see _expand_upstream_entries).
            existing_entry (dict): The already-connected entry it collides
                with (same name, or same particle count).
            sig (str): This pair's signature — the key the chosen
                resolution is remembered under.
        """
        from PySide6.QtWidgets import QMessageBox, QInputDialog
        reason = ("the same sample name" if new_entry['name'] == existing_entry['name']
                  else "the same particle count")
        box = QMessageBox(parent_window)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Possible duplicate sample")
        box.setText(
            f"\"{new_entry['name']}\" ({new_entry['total']:,} particles) — "
            f"just connected — looks like it might be the same sample as "
            f"\"{existing_entry['name']}\" ({existing_entry['total']:,} "
            f"particles), already connected to this filter. They share "
            f"{reason}.\n\nThis is a quick name/count check, not a deep "
            f"comparison — it may be a false positive if these really are "
            f"two different samples. How should this filter treat them?")
        keep_btn = box.addButton("Keep as two separate samples…",
                                 QMessageBox.ActionRole)
        combine_btn = box.addButton("Combine into one sample…",
                                    QMessageBox.ActionRole)
        disconnect_btn = box.addButton("Disconnect the new connection",
                                       QMessageBox.DestructiveRole)
        ignore_btn = box.addButton("Ignore one of them",
                                   QMessageBox.AcceptRole)
        # Default to the non-destructive choice: keeping both. Dropping a
        # sample must be an explicit, deliberate click (see the dismissal
        # branch below), never what happens when the user just hits Enter or
        # closes the dialog — that would contradict the filter's
        # append-not-drop default (normalize_sources) and silently discard
        # data.
        box.setDefaultButton(keep_btn)
        box.exec()
        clicked = box.clickedButton()

        if clicked is keep_btn:
            name, ok = QInputDialog.getText(
                parent_window, "Name the new sample",
                f"\"{new_entry['name']}\" will be kept as a separate entry. "
                f"What should it be called?",
                text=f"{new_entry['name']} (2)")
            if not ok or not name.strip():
                return
            self.duplicate_resolutions[sig] = {
                'action': 'keep_separate',
                'target': (new_entry['name'], new_entry['total']),
                'rename_to': name.strip(),
            }
        elif clicked is combine_btn:
            name, ok = QInputDialog.getText(
                parent_window, "Name the combined sample",
                f"\"{new_entry['name']}\" and \"{existing_entry['name']}\" "
                f"will be combined into one sample. What should it be "
                f"called?",
                text=new_entry['name'])
            if not ok or not name.strip():
                return
            self.duplicate_resolutions[sig] = {
                'action': 'combine',
                'combined_name': name.strip(),
            }
        elif clicked is disconnect_btn:
            scene = self.scene_ref
            if scene is not None:
                li = scene.link_items.get(new_link)
                if li:
                    scene.delete_link(li)
            return
        elif clicked is ignore_btn:
            # Explicit, deliberate choice to drop one of the duplicates.
            self.duplicate_resolutions[sig] = {
                'action': 'ignore',
                'target': (new_entry['name'], new_entry['total']),
            }
        # else: dialog dismissed (Esc / window close) with no explicit
        # choice — keep BOTH samples. Store no resolution and fall through to
        # the recompute below, so the append-not-drop default disambiguates
        # them ("S1" / "S1 (2)") rather than silently discarding one.
        self._recompute_stale(resolve_and_normalize_sources(
            self._pull_upstream_all(), self.duplicate_resolutions))
        self.configuration_changed.emit()

    def _warn_partial_mismatch(self, parent_window, matched, missing, added):
        """Tell the user the newly connected source only partly matches the
        saved settings, and offer to drop the settings for samples that are
        no longer connected.

        Args:
            parent_window: Dialog parent.
            matched (list): Stored names still present (settings still apply).
            missing (list): Stored names no longer connected (settings idle).
            added (list): Incoming names with no saved filter yet.
        """
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(parent_window)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Sample mismatch")
        box.setText(
            "The samples feeding this filter don't fully match its saved "
            "settings. Your settings are kept — here's how they line up:")
        lines = []
        lines.append("✓ Still apply ({}): {}".format(
            len(matched), ", ".join(matched)))
        lines.append("⚠ Saved but not connected now ({}): {}".format(
            len(missing), ", ".join(missing)))
        if added:
            lines.append("＋ New, no filter yet ({}): {}".format(
                len(added), ", ".join(added)))
        lines.append(
            "\nThe \"not connected\" settings sit idle until those samples "
            "come back. You can keep them, or clear just those.")
        box.setInformativeText("\n".join(lines))
        keep = box.addButton("Keep settings", QMessageBox.AcceptRole)
        clear = box.addButton("Clear settings for missing samples",
                              QMessageBox.DestructiveRole)
        box.setDefaultButton(keep)
        box.exec()
        if box.clickedButton() is clear:
            for n in missing:
                self.sample_filters.pop(n, None)
                self.sample_groups.pop(n, None)
            if self.selected_sources is not None:
                self.selected_sources = [s for s in self.selected_sources
                                         if s not in missing]
            self._recompute_stale(resolve_and_normalize_sources(
                self._pull_upstream_all(), self.duplicate_resolutions))
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

        Wrapped in a broad try/except: this runs inside a background
        ``_CalculationWorker`` thread (``widget/canvas_widgets.py``), whose
        caller only logs failures at ``_itk_log.error`` level and otherwise
        drops them silently — a downstream plot window would keep showing
        whatever data it last received with no visible sign the recompute
        never happened. Logging with ``exception`` here (full traceback,
        at module import time this logger is already configured) makes a
        future occurrence diagnosable instead of invisible.

        Returns:
            dict: Single-sample data when one sample is chosen, multi-sample
                data when several are (regrouped with ``source_sample``
                tags); the unmodified upstream dict in the single-link
                no-filter case; None when upstream is unconfigured, no
                sample is selected, or recomputation raised.
        """
        try:
            return self._get_output_data_impl()
        except Exception:
            _itk_log.exception(
                "ParticleFilterNode.get_output_data failed — downstream "
                "nodes will keep their previous data instead of updating")
            return None

    def _dilution_resolution_for(self, group_name, sources):
        """Look up the stored dilution-mismatch resolution for a group,
        re-validated against its CURRENT members rather than blindly reused.

        The resolution was made once at Accept/OK time
        (ParticleFilterDialog._resolve_pending_dilution_conflicts); this
        just reads it back on every recompute. If the group's members no
        longer actually conflict (e.g. the user fixed a dilution factor
        elsewhere), the stale resolution is ignored so normal first-member
        behavior applies instead of forcing an unnecessary override.

        Args:
            group_name (str): The merged/summed output name.
            sources (list): The source entries currently forming that group.

        Returns:
            dict | None: The resolution dict, or None if none applies.
        """
        res = self.dilution_resolutions.get(group_name)
        if res is None:
            return None
        members = [(s['name'], s.get('conc')) for s in sources]
        if not dilution_factors_conflict(members):
            return None
        return res

    def _get_output_data_impl(self):
        upstreams = self._pull_upstream_all()
        if not upstreams:
            return None
        filterable = [u for u in upstreams
                      if u.get('type') in _FILTERABLE_TYPES]
        if not filterable:
            return upstreams[0]
        sources = resolve_and_normalize_sources(
            filterable, self.duplicate_resolutions)
        self._recompute_stale(sources)
        if self.selected_sources is None:
            chosen = sources
        else:
            chosen = [s for s in sources
                      if s['name'] in self.selected_sources]
            if not chosen and sources:
                # self.selected_sources names none of the current sources —
                # e.g. this node was duplicated (or its upstream swapped)
                # and the stored selection refers to samples that no longer
                # feed it. Treat it like an unset selection rather than
                # silently emitting nothing.
                chosen = sources
        if not chosen:
            return None
        any_active = any(active_axes(self.sample_filters.get(s['name']))
                         for s in chosen)
        if len(filterable) == 1 and len(chosen) == len(sources):
            data = filterable[0]
            if not any_active:
                # Inert pass-through still counts as a filter hop.
                return _apply_filt_provenance(data)
            combined = []
            for s in sources:
                kept, _stale = apply_sample_filter(
                    s, self.sample_filters.get(s['name']), retag=False)
                combined.extend(kept)
            out = dict(data)
            out['particle_data'] = combined
            out['filtered_particles'] = len(combined)
            return _apply_filt_provenance(out)
        filtered = []
        for s in chosen:
            kept, _stale = apply_sample_filter(
                s, self.sample_filters.get(s['name']))
            filtered.append((s, kept))
        singles = [(s, k) for s, k in filtered
                   if s.get('origin') == 'single']
        others = [(s, k) for s, k in filtered
                  if s.get('origin') != 'single']

        # "Merge single samples into one" dominates over per-sample custom
        # groups when both are set — it's the coarser, all-or-nothing
        # control, so it wins rather than being silently overridden by a
        # finer-grained group name (see ParticleFilterDialog._try_accept,
        # which warns the user about this precedence before it takes
        # effect). Only when merge_singles is off do custom group names
        # actually take effect; singles left ungrouped then stay separate.
        final = []
        if self.merge_singles:
            if len(singles) >= 2:
                name = (self.merged_name or '').strip() or 'Combined'
                merged_kept = []
                for _s, kept in singles:
                    merged_kept.extend(retag_particles(kept, name))
                res = self._dilution_resolution_for(
                    name, [s for s, _k in singles])
                final.append((merge_single_sources(
                    [s for s, _k in singles], name, res), merged_kept))
            else:
                final.extend(singles)
        else:
            grouped, ungrouped, group_order = {}, [], []
            for s, kept in singles:
                gname = (self.sample_groups.get(s['name']) or '').strip()
                if gname:
                    if gname not in grouped:
                        grouped[gname] = []
                        group_order.append(gname)
                    grouped[gname].append((s, kept))
                else:
                    ungrouped.append((s, kept))
            for gname in group_order:
                members = grouped[gname]
                merged_kept = []
                for _s, kept in members:
                    merged_kept.extend(retag_particles(kept, gname))
                res = self._dilution_resolution_for(
                    gname, [s for s, _k in members])
                final.append((merge_single_sources(
                    [s for s, _k in members], gname, res), merged_kept))
            final.extend(ungrouped)
        final.extend(others)
        # Stamp each output sample with the filter-provenance suffix
        # (base → base (filt x1); an already-filtered base (filt x1) →
        # base (filt x2); a merged/grouped name restarts at x1). Done here,
        # on the output names only, so the per-sample INPUT keys used above
        # (sample_filters / sample_groups / selected_sources) are untouched.
        # retag_particles mutates the already-owned filtered copies in place,
        # so this adds no extra allocation.
        stamped = []
        for s, kept in final:
            nm = _bump_filt_suffix(s['name'])
            stamped.append((dict(s, name=nm), retag_particles(kept, nm)))
        final = stamped
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
        """Refresh cached knowledge of the incoming samples: which isotope
        labels a filter references but the sample no longer has, and which
        sample names are actually connected right now (so ``is_active()``
        and ``summary_text()`` can tell a real setting apart from a
        ``sample_filters``/``selected_sources`` entry left over from a
        duplicate or a rewired upstream — see those methods).

        Args:
            sources (list): Source entries from :func:`normalize_sources`.
        """
        self._incoming_names = [s['name'] for s in sources or []]
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

        Only counts ``sample_filters``/``selected_sources`` entries that
        name a currently-connected sample (``self._incoming_names``) —
        entries left over from a duplicate or a rewired upstream refer to
        samples that aren't actually feeding this node anymore, so they
        shouldn't make an unconfigured filter look active.

        Returns:
            bool: True when any currently-connected sample has an active
                filter, or the sample selection currently narrows anything.
        """
        current = set(self._incoming_names)
        filters_active = any(active_axes(c) for n, c in self.sample_filters.items()
                              if n in current)
        sources_active = bool(self.selected_sources) and any(
            n in current for n in self.selected_sources)
        return filters_active or sources_active

    def summary_text(self):
        """Build the live summary shown under the node icon.

        Returns:
            str: e.g. "2 samples + 1 filtered", a single sample's criteria
                when only one filter is set, "No filter" when inactive
                (including when every stored setting is left over from a
                duplicate/rewire and matches nothing currently connected),
                "⚠ stale" when stale criteria are detected.
        """
        if self._stale:
            return "⚠ stale"
        current = set(self._incoming_names)
        parts = []
        if self.selected_sources is not None:
            matched = [n for n in self.selected_sources if n in current]
            if matched:
                n = len(matched)
                parts.append(f"{n} sample" + ("s" if n != 1 else ""))
        filtered = {n: c for n, c in self.sample_filters.items()
                    if active_axes(c) and n in current}
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
        dlg = ParticleFilterDialog(
            parent_window, snapshots, self.sample_filters,
            self.selected_sources, self.merged_name, owner_node=self,
            suppress_stale_warning=self.suppress_stale_warning,
            merge_singles=self.merge_singles, sample_groups=self.sample_groups,
            duplicate_resolutions=self.duplicate_resolutions,
            dilution_resolutions=self.dilution_resolutions)
        if dlg.exec() == QDialog.Accepted:
            self.sample_filters = dlg.get_sample_filters()
            self.selected_sources = dlg.get_selected_sources()
            self.merged_name = dlg.get_merged_name()
            self.merge_singles = dlg.get_merge_singles()
            self.sample_groups = dlg.get_sample_groups()
            self.dilution_resolutions = dlg.get_dilution_resolutions()
            self.suppress_stale_warning = dlg.stale_warning_suppressed()
            self._recompute_stale(resolve_and_normalize_sources(
                snapshots, self.duplicate_resolutions))
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
