# -*- coding: utf-8 -*-
"""Shared reader API for rendering Particle Classifier output in viz nodes.

Pure Python, **no Qt** -- importable and unit-testable headless from
anywhere. The matching UI piece (the role picker) lives beside the other
reusable settings-group builders in ``results/shared_plot_utils.py``
(``ClassifierViewGroup``), because that is where every settings dialog
already looks for them.

Why this module exists
----------------------

The Particle Classifier collapses each particle's composition dicts to a
single ``{bucket_label: value}`` entry so a bucket looks "exactly like
another isotope" downstream (``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §7).
That works for any node reading one composition key at a time, and breaks
every node that needs the particle's whole key-SET (co-occurrence
groupings) or 2+ keys from one particle at once (ratios, correlations,
ternary vertices). Rather than a bespoke fix per node, the classifier now
*dual-carries* the untouched originals alongside the collapse, and this
module is the single seam every viz node reads them through.

See ``.claude/aug24.md``, "Classifier -> viz plotting correctness".

The role model
--------------

A bucket plays exactly one role in a given plot, and which roles are even
*available* is a property of the node's arity class, not of the chart type:

``ROLE_SERIES``
    The bucket IS the plotted category (today's behavior: one bar, one
    wedge, one histogram series per bucket). Only meaningful for nodes that
    read one composition key at a time -- for anything else the collapse is
    exactly what breaks the chart, so offering SERIES would be offering the
    bug.
``ROLE_FACET``
    The bucket partitions particles into separate panels; real isotopes go
    back on the axes *within* each panel. "Within Smelter-type particles,
    does Fe correlate with Ti?"
``ROLE_ENCODE``
    One shared plot over real isotopes; the bucket becomes a color/marker/
    highlight on individual marks. The canonical "scatter colored by
    classification". For aggregate-statistic charts (correlation matrix,
    network) there are no per-particle marks to color, so ENCODE there means
    annotating the isotope axis labels by which expression references them.
``ROLE_OFF``
    Ignore buckets; render real isotopes exactly as an unclassified stream
    would. The honest default for every non-SERIES node, so a chart never
    silently degenerates -- it shows the normal thing until the user opts in.

A fifth role, VALIDATE (comparing a *discovered* clustering against the
*asserted* buckets), is specific to the clustering node and deliberately
not implemented here -- see ``aug24.md``'s "Hibernated: clustering".
"""

from __future__ import annotations

from tools.particle_classifier_relabel import (
    RAW_KEY, BUCKET_KEY, SRC_INDEX_KEY,
)

import logging
_itk_log = logging.getLogger("IsotopeTrack.results.classifier_view")


# ── Roles ──────────────────────────────────────────────────────────────

ROLE_SERIES = 'series'
ROLE_FACET = 'facet'
ROLE_ENCODE = 'encode'
ROLE_OFF = 'off'

#: Config key holding a node's chosen role. Deliberately a FLAT scalar, not
#: a nested dict: node configs are persisted through a hardcoded attribute
#: allow-list in ``save_export/project_manager.py`` that includes ``config``
#: but would silently drop a new node *attribute*, and a nested dict in a
#: class-level ``DEFAULT_CONFIG`` is exactly the shape that caused the
#: shared-mutable config leak (see ``shared_plot_utils.deep_copy_config``).
ROLE_CONFIG_KEY = 'classifier_role'

#: Human-readable labels for the role picker.
ROLE_LABELS = {
    ROLE_OFF: "Off - plot isotopes, ignore classifier groups",
    ROLE_SERIES: "Groups as data - plot the classifier groups themselves",
    ROLE_FACET: "One panel per group - isotopes on the axes",
    ROLE_ENCODE: "Color by group - isotopes on the axes",
}

#: Arity classes (see the module docstring). A node declares its own class;
#: everything about role availability follows from it.
ARITY_PER_KEY = 'per_key'          #: one key at a time / population aggregate
ARITY_KEY_SET = 'key_set'          #: needs the particle's whole key-set
ARITY_MULTI_KEY = 'multi_key'      #: needs 2+ keys from one particle at once

_ROLES_BY_ARITY = {
    ARITY_PER_KEY: (ROLE_SERIES, ROLE_FACET, ROLE_ENCODE, ROLE_OFF),
    ARITY_KEY_SET: (ROLE_FACET, ROLE_ENCODE, ROLE_OFF),
    ARITY_MULTI_KEY: (ROLE_FACET, ROLE_ENCODE, ROLE_OFF),
}

_DEFAULT_ROLE_BY_ARITY = {
    ARITY_PER_KEY: ROLE_SERIES,
    ARITY_KEY_SET: ROLE_OFF,
    ARITY_MULTI_KEY: ROLE_OFF,
}


def available_roles(arity):
    """Roles a node of this arity class may offer.

    Args:
        arity (str): One of ``ARITY_PER_KEY`` / ``ARITY_KEY_SET`` /
            ``ARITY_MULTI_KEY``.

    Returns:
        tuple: Valid role constants, in presentation order. Unknown arity
            falls back to the most conservative set (no SERIES).
    """
    return _ROLES_BY_ARITY.get(arity, (ROLE_FACET, ROLE_ENCODE, ROLE_OFF))


def default_role(arity):
    """The role a node of this arity should start in.

    ``ARITY_PER_KEY`` defaults to SERIES so existing behavior is bit-for-bit
    unchanged for the nodes the collapse always worked for; everything else
    defaults to OFF so it renders something *correct* rather than degenerate
    until the user opts into bucket awareness.
    """
    return _DEFAULT_ROLE_BY_ARITY.get(arity, ROLE_OFF)


def effective_role(config, input_data, arity):
    """Resolve the role actually in force for this render.

    Must be called at **render time**, every render -- never resolved once
    at link time and cached. Saved projects restore canvas links with
    connection rules suspended (``save_export/project_manager.py``), the
    user can change the role after connecting, and the upstream classifier's
    own overlap mode can change underneath a configured downstream node. All
    three mean a stored role can be stale or impossible by the time it
    matters.

    Args:
        config (dict): The viz node's config.
        input_data (dict | None): The node's current upstream data.
        arity (str): The node's arity class.

    Returns:
        str: A role that is valid for this node AND this stream. Always
            ``ROLE_OFF`` when the upstream is not a classifier stream, so a
            node wired to a plain sample behaves exactly as it always has.
    """
    if not is_classifier_stream(input_data):
        return ROLE_OFF
    role = (config or {}).get(ROLE_CONFIG_KEY) or default_role(arity)
    allowed = available_roles(arity)
    if role not in allowed:
        _itk_log.debug(
            "Classifier role %r not available for arity %r; falling back to %r",
            role, arity, default_role(arity))
        return default_role(arity)
    return role


# ── Stream introspection ───────────────────────────────────────────────

def is_classifier_stream(input_data):
    """Whether this upstream data came through a Particle Classifier.

    Detected by the dict-level registry the classifier attaches, not by any
    node-type check -- the data may have travelled through a Temp Node or
    another passthrough on the way here.
    """
    if not isinstance(input_data, dict):
        return False
    return '_classifier_registry' in input_data


def bucket_registry(input_data):
    """``{label: {'color', 'is_group', 'definitions': [...]}}`` for the stream.

    Returns an empty dict for a non-classifier stream, so callers can read
    it unconditionally.
    """
    if not isinstance(input_data, dict):
        return {}
    return input_data.get('_classifier_registry') or {}


def bucket_labels(input_data):
    """Every bucket label this stream can contain, in registry order."""
    return list(bucket_registry(input_data).keys())


def bucket_color(input_data, label, default=None):
    """The user's chosen color for one bucket, or ``default``."""
    entry = bucket_registry(input_data).get(label)
    return (entry or {}).get('color') or default


def expressions_for(input_data, label):
    """The literal classifier expression(s) defining one bucket.

    A list, because a bucket backed by a *group* can pool several
    definitions -- flattening to one string would silently drop the rest.

    Args:
        input_data (dict | None): The node's upstream data.
        label (str): The bucket label.

    Returns:
        list[str]: Expression texts, possibly empty (the ``Unclassified``
            bucket has no defining expression).
    """
    entry = bucket_registry(input_data).get(label) or {}
    return [d.get('expression_text') for d in entry.get('definitions', [])
            if d.get('expression_text')]


def bucket_caption(input_data, label, max_len=80):
    """A display string naming a bucket AND what actually defines it.

    "orange = Smelter" means nothing to a scientist evaluating whether a
    classification is sound; the isotope expression does
    (``.claude/july22.md`` #8). Use this anywhere a bucket is titled.

    Args:
        input_data (dict | None): The node's upstream data.
        label (str): The bucket label.
        max_len (int): Truncate the expression part beyond this many chars.

    Returns:
        str: e.g. ``"Smelter (60Ni+107Ag)"``, ``"Smelter (60Ni+107Ag | 197Au)"``
            for a multi-definition group, or just ``"Unclassified"`` when
            there is no expression to show.
    """
    exprs = expressions_for(input_data, label)
    if not exprs:
        return label
    joined = ' | '.join(exprs)
    if len(joined) > max_len:
        joined = joined[:max_len - 1] + '…'
    return f"{label} ({joined})"


def raw_selected_isotopes(input_data):
    """The upstream isotope vocabulary, before bucket relabeling.

    Nodes that build element/axis pickers from ``selected_isotopes`` get
    bucket labels once a classifier is upstream -- correct for SERIES, but
    useless for FACET/ENCODE/OFF, which need the real isotopes. This returns
    the untouched upstream list on a classifier stream, and falls through to
    the normal ``selected_isotopes`` otherwise, so callers can use it
    unconditionally in place of a direct read.

    Returns:
        list: Isotope entry dicts (same shape as ``selected_isotopes``).
    """
    if not isinstance(input_data, dict):
        return []
    if is_classifier_stream(input_data):
        raw = input_data.get('_raw_selected_isotopes')
        if raw:
            return raw
    return input_data.get('selected_isotopes') or []


def raw_isotope_labels(input_data):
    """Just the label strings from :func:`raw_selected_isotopes`."""
    return [i.get('label') for i in raw_selected_isotopes(input_data)
            if isinstance(i, dict) and i.get('label')]


# ── Per-particle access ────────────────────────────────────────────────

def composition(particle, data_key, collapsed=False):
    """One particle's composition dict for ``data_key``.

    **Defaults to the REAL isotope composition**, not the classifier's
    collapsed bucket entry. That polarity is deliberate: it means a node
    fixed to read through this helper keeps working unchanged if the
    destructive collapse is ever removed entirely -- that becomes a one-line
    change here instead of unwinding a special case from every viz module.
    Pass ``collapsed=True`` to explicitly opt into the bucket-as-isotope view
    (what ``ROLE_SERIES`` wants).

    Falls back to the particle's own dict whenever there is nothing carried
    (non-classifier stream, or a key the classifier never rewrote such as
    the diameter fields), so this is always safe to call.

    Args:
        particle (dict): A particle dict.
        data_key (str): e.g. ``'elements'``, ``'element_mass_fg'``.
        collapsed (bool): Read the bucket-keyed dict instead of the real one.

    Returns:
        dict: ``{label: value}``. Empty dict when absent.
    """
    if collapsed:
        return particle.get(data_key) or {}
    raw = particle.get(RAW_KEY)
    if isinstance(raw, dict) and data_key in raw:
        return raw[data_key] or {}
    return particle.get(data_key) or {}


def bucket_of(particle):
    """The bucket label assigned to one particle.

    Returns None for an unclassified passthrough particle (which still
    carries its real composition) and for any particle from a
    non-classifier stream.
    """
    return particle.get(BUCKET_KEY)


def particle_identity(particle):
    """A hashable identity for one *source* particle.

    Under ``double_count`` overlap mode the classifier emits one input
    particle once per matching definition, so several output particles can
    share an identity. That is the point: it is the key to dedupe on before
    computing any statistic over real isotopes.

    Returns:
        tuple | None: ``(source_sample, src_index)``, or None when the
            stream carries no index (non-classifier data), in which case
            there is nothing to dedupe.
    """
    idx = particle.get(SRC_INDEX_KEY)
    if idx is None:
        return None
    return (particle.get('source_sample'), idx)


def dedupe_particles(particles):
    """Collapse double-counted copies back to one particle each.

    **Mandatory before any statistic computed over real isotopes** (Pearson
    r, network edge weights, clustering): a particle matching two
    definitions is emitted twice, and every copy carries the *same* real
    composition, so leaving them in silently double-weights that particle
    and biases the result. It is NOT wanted for faceting, where the particle
    genuinely belongs in two panels, nor for SERIES, which has always
    counted per-bucket by design.

    Order-stable; keeps the first copy of each identity. Particles with no
    identity (non-classifier stream) pass through untouched.

    Args:
        particles (list): Particle dicts.

    Returns:
        list: One particle per source identity.
    """
    seen = set()
    out = []
    for p in particles:
        ident = particle_identity(p)
        if ident is None:
            out.append(p)
            continue
        if ident in seen:
            continue
        seen.add(ident)
        out.append(p)
    return out


def particles_by_bucket(particles, include_unclassified=True):
    """Partition particles by assigned bucket -- the FACET primitive.

    Args:
        particles (list): Particle dicts.
        include_unclassified (bool): Keep the ``'Unclassified'`` bucket.

    Returns:
        dict: ``{label: [particles]}``, insertion-ordered by first
            appearance. Passthrough particles (bucket None) are grouped
            under the key None so a caller can decide what to do with them
            -- they are real, unclassified data, not an error.
    """
    out = {}
    for p in particles:
        label = bucket_of(p)
        if label == 'Unclassified' and not include_unclassified:
            continue
        out.setdefault(label, []).append(p)
    return out


def has_multiple_buckets(input_data):
    """Whether faceting/encoding by bucket would produce more than one group.

    A single-bucket stream makes FACET and ENCODE degenerate (one panel, or
    one color) -- worth checking before offering them as meaningful.
    """
    return len(bucket_registry(input_data)) > 1
