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
    RAW_KEY, BUCKET_KEY, SRC_INDEX_KEY, MATCH_ISOTOPES_KEY,
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

#: Human-readable labels for the role picker (per-node manual QA pass,
#: 2026-08-24 -- names and one-line descriptions are user-specified wording,
#: keep verbatim).
ROLE_LABELS = {
    ROLE_SERIES: "GROUPS - plot the classifier groups themselves",
    ROLE_FACET: "PANELS - one subplot per group, plotting isotopic data",
    ROLE_ENCODE: "COLORS - Isotopic data color-coded by classifier groups",
    ROLE_OFF: "OFF - Ignore particle classifier groups",
}

#: Arity classes (see the module docstring). A node declares its own class;
#: everything about role availability follows from it.
ARITY_PER_KEY = 'per_key'          #: one key at a time / population aggregate
ARITY_KEY_SET = 'key_set'          #: needs the particle's whole key-set
ARITY_MULTI_KEY = 'multi_key'      #: needs 2+ keys from one particle at once

#: Heatmap is structurally a set-of-keys node (a row is a particle's whole
#: isotope co-occurrence signature) -- the same class as ``element_composition
#: _plot``/``single_multiple_element_plot``, for which offering ROLE_SERIES
#: would be offering the original degenerate-collapse bug back. Heatmap gets
#: its OWN arity constant, not ``ARITY_KEY_SET``, because it has a bespoke,
#: safe GROUPS aggregation those other two don't (:func:`group_composition_rows`
#: builds a real multi-isotope-column row per bucket, never a 1x1 collapse) --
#: so SERIES is genuinely safe here, and *only* here. Do not reuse this arity
#: for a node that lacks that dedicated aggregation path.
ARITY_HEATMAP = 'heatmap'

#: ``correlation_matrix``, same reasoning as ``ARITY_HEATMAP``: it is a
#: multi-key node, but unlike its ``ARITY_MULTI_KEY`` siblings (network,
#: molar/isotopic ratio, ternary) it has a bespoke, non-degenerate GROUPS
#: mode -- a MIXED vocabulary where real isotopes and classifier groups share
#: both axes (:func:`results.results_matrix.build_mixed_columns`), so an
#: isotope x group cell is populated for every matched particle with no
#: overlap between definitions required. Handing plain SERIES to the other
#: multi-key nodes would hand them the original degenerate collapse instead,
#: which is exactly why this needs its own constant rather than widening
#: ``ARITY_MULTI_KEY``.
ARITY_MATRIX = 'matrix'

_ROLES_BY_ARITY = {
    # Per-key-independent charts (histogram, element bar, box, pie,
    # concentration) offer GROUPS and OFF only. PANELS/COLORS are genuinely
    # useful on these -- "one histogram per particle type" and "one shared
    # histogram color-coded by particle type" are both real comparative
    # questions -- but they're deliberately OUT OF SCOPE for the
    # classifier->viz push and deferred as a future "extra feature" (see
    # .claude/aug24.md's improvements list for the rationale and worked
    # examples). GROUPS already answers what these charts are for; the
    # multi-key/set-of-keys nodes need the effort far more.
    ARITY_PER_KEY: (ROLE_SERIES, ROLE_OFF),
    ARITY_KEY_SET: (ROLE_FACET, ROLE_ENCODE, ROLE_OFF),
    ARITY_MULTI_KEY: (ROLE_FACET, ROLE_ENCODE, ROLE_OFF),
    ARITY_HEATMAP: (ROLE_SERIES, ROLE_FACET, ROLE_ENCODE, ROLE_OFF),
    ARITY_MATRIX: (ROLE_SERIES, ROLE_FACET, ROLE_ENCODE, ROLE_OFF),
}

_DEFAULT_ROLE_BY_ARITY = {
    ARITY_PER_KEY: ROLE_SERIES,
    ARITY_KEY_SET: ROLE_OFF,
    ARITY_MULTI_KEY: ROLE_OFF,
    ARITY_HEATMAP: ROLE_OFF,
    ARITY_MATRIX: ROLE_OFF,
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


# ── Aggregation scope (GROUPS role only): DEFINITION vs TOTAL PARTICLE ───
#
# Orthogonal to the role model above, and meaningful only under
# ROLE_SERIES/GROUPS -- every other role either shows real isotopes
# directly (OFF) or has no single per-bucket number to begin with
# (FACET/ENCODE), so there is nothing for this axis to modify there.
#
# **Two different, both-legitimate scientific questions, per-node choice
# (found live, 2026-08-25, from a mean-above-the-whisker box-plot reading
# that turned out to be real but misleading)**:
#
# - SCOPE_DEFINITION ("of the isotopes that DEFINE this group, how much is
#   there"): a matched particle's bucket value counts only the isotopes its
#   triggering expression names -- the classifier's own destructive
#   collapse has always computed exactly this, so this is also the
#   historical/default behavior, unchanged, for every node that doesn't
#   opt into the other scope.
# - SCOPE_TOTAL_PARTICLE ("of the particles that QUALIFY for this group,
#   how much are they emitting in total"): every isotope a qualifying
#   particle actually carries counts, not just the trigger isotope(s) --
#   e.g. a "Smelter" particle triggered by 60Ni alone still contributes its
#   Fe, Cu, everything else to Smelter's total, because the particle is
#   what qualified, not just its diagnostic isotope.
#
# Neither is "more correct" -- a scientist asking "what does the arsenic
# look like in particles I've called Poison" wants DEFINITION; one asking
# "how much mass are Smelter-type particles emitting, period" wants
# TOTAL PARTICLE. See ``MATCH_ISOTOPES_KEY`` in
# ``tools.particle_classifier_relabel`` for the underlying dual-carried
# isotope set this reads, and ``composition_items_for_role`` below for
# where the choice actually changes what a node renders.
SCOPE_DEFINITION = 'definition'
SCOPE_TOTAL_PARTICLE = 'total_particle'

#: Config key holding a node's chosen aggregation scope. Same flat-scalar
#: rationale as ROLE_CONFIG_KEY.
SCOPE_CONFIG_KEY = 'classifier_agg_scope'

SCOPE_LABELS = {
    SCOPE_DEFINITION: "BY DEFINITION - only the isotopes that define this group count toward its value",
    SCOPE_TOTAL_PARTICLE: "TOTAL PARTICLE - every isotope on a qualifying particle counts toward its value",
}


def effective_scope(config, input_data):
    """Resolve the aggregation scope actually in force for this render.

    Same call-fresh-every-render discipline as :func:`effective_role`, and
    for the same reasons (stale saved config, mid-session changes).

    Args:
        config (dict): The viz node's config.
        input_data (dict | None): The node's current upstream data.

    Returns:
        str: ``SCOPE_DEFINITION`` or ``SCOPE_TOTAL_PARTICLE``. Always
            ``SCOPE_DEFINITION`` (the historical behavior) when the upstream
            isn't a classifier stream, or when the stored value is missing
            or invalid.
    """
    if not is_classifier_stream(input_data):
        return SCOPE_DEFINITION
    scope = (config or {}).get(SCOPE_CONFIG_KEY)
    return scope if scope in (SCOPE_DEFINITION, SCOPE_TOTAL_PARTICLE) else SCOPE_DEFINITION


# ── Group-row denominator (GROUPS role, set-of-keys aggregation only) ────
#
# A third, independent axis -- meaningful only where a single row aggregates
# MANY particles into a per-isotope statistic (today: heatmap_plot's GROUPS
# role via group_composition_rows below). Per-key-independent nodes never
# hit this ambiguity: a histogram/box-plot bucket's value is one number, not
# a statistic-over-a-list. Heatmap's *existing* (non-classifier) combination
# rows don't hit it either -- a combination is DEFINED by every member
# particle sharing the exact same isotope set, so "mean over the row" and
# "mean over detections" are always identical there. It only appears once
# GROUPS makes a row's membership heterogeneous (particles that qualify for
# one bucket don't all necessarily carry the same isotopes).
#
# Found live, 2026-08-25, working through the heatmap GROUPS spec: given a
# classifier group's mean Fe value, is the denominator "every particle in
# the group" (particles that don't carry Fe count as a real 0 -- the bulk,
# population-wide average) or "only particles that carry Fe" (the average
# conditioned on detection)? Both are real, different numbers a scientist
# might want; neither is a bug.
DENOMINATOR_WHOLE_GROUP = 'whole_group'
DENOMINATOR_DETECTED_ONLY = 'detected_only'

#: Config key holding a node's chosen group-row denominator. Same flat-
#: scalar rationale as ROLE_CONFIG_KEY / SCOPE_CONFIG_KEY.
DENOMINATOR_CONFIG_KEY = 'classifier_group_denominator'

DENOMINATOR_LABELS = {
    DENOMINATOR_WHOLE_GROUP: "Whole Group - every particle in the group counts, particles without the isotope count as 0",
    DENOMINATOR_DETECTED_ONLY: "Detected Only - only particles that actually carry the isotope count",
}


def effective_denominator(config, input_data):
    """Resolve the group-row denominator actually in force for this render.

    Same call-fresh-every-render discipline as :func:`effective_role` /
    :func:`effective_scope`.

    Returns:
        str: ``DENOMINATOR_WHOLE_GROUP`` or ``DENOMINATOR_DETECTED_ONLY``.
            Always ``DENOMINATOR_WHOLE_GROUP`` when the upstream isn't a
            classifier stream, or the stored value is missing or invalid.
    """
    if not is_classifier_stream(input_data):
        return DENOMINATOR_WHOLE_GROUP
    val = (config or {}).get(DENOMINATOR_CONFIG_KEY)
    return val if val in (DENOMINATOR_WHOLE_GROUP, DENOMINATOR_DETECTED_ONLY) else DENOMINATOR_WHOLE_GROUP


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


def scope_isotopes(particle, scope):
    """The isotope keys "in scope" for this particle's bucket membership,
    under a :data:`SCOPE_DEFINITION` vs :data:`SCOPE_TOTAL_PARTICLE` choice.

    ``SCOPE_TOTAL_PARTICLE`` always means "every isotope the particle
    actually carries" -- recoverable directly from the particle's own raw
    composition, so no dual-carried set is needed for that half.

    ``SCOPE_DEFINITION`` reads ``MATCH_ISOTOPES_KEY`` (the isotope set the
    particle's own matched definition(s) referenced, dual-carried at
    relabel time -- see ``tools.particle_classifier_relabel``), falling
    back to every isotope on the particle when that dual-carry is absent
    (a non-classifier stream, or a particle from before this feature
    existed), so this is always safe to call.

    Args:
        particle (dict): A particle dict.
        scope (str): ``SCOPE_DEFINITION`` or ``SCOPE_TOTAL_PARTICLE``.

    Returns:
        set: Isotope label strings.
    """
    if scope == SCOPE_TOTAL_PARTICLE:
        return set(composition(particle, 'elements', collapsed=False).keys())
    match = particle.get(MATCH_ISOTOPES_KEY)
    if match is not None:
        return set(match)
    return set(composition(particle, 'elements', collapsed=False).keys())


def composition_items_for_role(particle, data_key, role, scope=SCOPE_DEFINITION):
    """``(label, value)`` pairs one particle contributes for ``data_key``
    under a GROUPS-or-OFF role (and, only under GROUPS, a DEFINITION-vs-
    TOTAL-PARTICLE aggregation scope -- see the module-level docs above
    ``effective_scope``), for per-key nodes that read the same quantity
    across every data type a user can pick (box/strip plot's
    Counts/Mass/Moles/Diameter switch is the motivating case).

    Two different key shapes need two different answers, and ``scope``
    changes each of them differently:

    - A key the classifier itself relabels (present in the particle's
      dual-carried :data:`RAW_KEY` snapshot -- ``elements``,
      ``element_mass_fg``, ``element_moles_fmol``, and the MFC-dependent
      keys): under OFF this returns the raw per-isotope entries
      (``composition(collapsed=False)``), unaffected by ``scope``. Under
      GROUPS with the default ``SCOPE_DEFINITION``, this returns the
      classifier's own already-summed bucket entry exactly as it always
      has -- bit-for-bit unchanged, since that collapse has always been
      isotope-scoped to the matched definition. Under GROUPS with
      ``SCOPE_TOTAL_PARTICLE``, this instead re-sums the particle's real
      per-isotope values over *every* isotope the particle carries, not
      just the ones its matched definition named -- honoring the SAME
      Mass-Fraction-Calculator pooling-safety gate the classifier's own
      collapse already enforces: if that collapse has no entry for this
      particle's bucket at all (an MFC-dependent key the classifier chose
      not to keep for a multi-definition "drop_mfc" pooled group -- see
      ``tools.particle_classifier_relabel``'s module docstring), this
      returns nothing here either, rather than silently fabricating a
      mixed-MFC-basis number the classifier itself refused to compute.
    - A key the classifier deliberately never rewrites (the diameter
      fields -- there is no principled way to sum a diameter across
      isotopes, so the classifier leaves them alone regardless of scope):
      there is no bucket-collapsed dict to fall back on at all. OFF returns
      each isotope's own value under its own label, unchanged. GROUPS
      instead re-labels the particle's raw per-isotope entries under its
      *bucket* label -- ``SCOPE_DEFINITION`` keeps only the isotopes that
      defined this particle's bucket membership, ``SCOPE_TOTAL_PARTICLE``
      keeps every isotope the particle carries. Either way each isotope
      stays its own data point (there is nothing to sum for a diameter),
      just filed by group instead of by isotope. A passthrough particle
      (no bucket assigned) falls back to its real isotope labels
      unfiltered, since there is nothing to group by.

    Args:
        particle (dict): A particle dict.
        data_key (str): e.g. ``'elements'``, ``'element_diameter_nm'``.
        role (str): ``ROLE_OFF`` or ``ROLE_SERIES`` -- the only roles a
            per-key node ever has to pass here.
        scope (str): ``SCOPE_DEFINITION`` (default, matches every node's
            historical behavior) or ``SCOPE_TOTAL_PARTICLE``. Ignored
            entirely under ``ROLE_OFF`` -- real isotopes are shown either
            way, so there is no bucket value for a scope choice to modify.

    Returns:
        list[tuple]: ``(label, value)`` pairs, order-preserving.
    """
    if role == ROLE_OFF:
        return list(composition(particle, data_key, collapsed=False).items())

    raw_snapshot = particle.get(RAW_KEY)
    is_relabeled_key = isinstance(raw_snapshot, dict) and data_key in raw_snapshot

    if is_relabeled_key:
        definition_view = composition(particle, data_key, collapsed=True)
        if scope != SCOPE_TOTAL_PARTICLE:
            return list(definition_view.items())
        label = bucket_of(particle)
        if label is None:
            # Passthrough: no bucket was ever assigned, so definition_view
            # here is already the particle's real, untouched isotope-keyed
            # dict (never relabeled in the first place) -- nothing to
            # re-sum, same value under either scope.
            return list(definition_view.items())
        if label not in definition_view:
            # A matched particle whose bucket has no entry at all for this
            # key -- e.g. an MFC-dependent key the classifier's own
            # collapse deliberately dropped for a "drop_mfc" pooled group.
            # TOTAL PARTICLE must not silently fabricate a number the
            # classifier itself refused to compute.
            return []
        isotopes = scope_isotopes(particle, scope)
        raw_values = raw_snapshot.get(data_key) or {}
        total = sum(v for iso, v in raw_values.items() if iso in isotopes)
        return [(label, total)]

    label = bucket_of(particle)
    if label is None:
        return list(composition(particle, data_key, collapsed=False).items())
    isotopes = scope_isotopes(particle, scope)
    raw_values = composition(particle, data_key, collapsed=False)
    return [(label, v) for iso, v in raw_values.items() if iso in isotopes]


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


def group_composition_rows(particles, data_key, scope, denominator):
    """Aggregate real per-isotope values into one row per classifier bucket.

    The GROUPS-role primitive for any node whose row is a population
    statistic rather than a single particle or a single bucket-collapsed
    scalar -- today, ``heatmap_plot``'s GROUPS role (see ``ARITY_HEATMAP``);
    built generally so a future node can reuse it without re-deriving the
    MFC-gate/scope/denominator interaction below.

    Returns the same ``{label: {'particle_count': int, 'total_values':
    {isotope: [values...]}}}`` shape ``results_heatmap.py``'s existing
    combination-row builder already produces, so the entire downstream
    rendering pipeline (cell statistic, cell spread, search/filter,
    percentage conversion) is reused unmodified -- a group row is, to that
    pipeline, indistinguishable from a combination row.

    Args:
        particles (list): Particle dicts (one sample's worth).
        data_key (str): e.g. ``'elements'``, ``'element_mass_fg'``.
        scope (str): :data:`SCOPE_DEFINITION` or :data:`SCOPE_TOTAL_PARTICLE`
            -- which isotopes are even eligible to appear in a matched
            particle's row at all. Unlike ``composition_items_for_role``,
            this never re-*sums* isotopes into one number (a heatmap column
            is one isotope, not a bucket total), so the two scopes never
            produce different numbers here, only different COLUMN
            visibility: DEFINITION shows the same real per-isotope values as
            TOTAL_PARTICLE, just with non-referenced-isotope columns absent.
        denominator (str): :data:`DENOMINATOR_WHOLE_GROUP` (every accepted
            member of the bucket contributes an entry to every column that
            ANY member has -- 0 for isotopes it doesn't itself carry, giving
            every column the same length so ``_per_particle_percentages``-
            style parallel-index logic keeps working) or
            :data:`DENOMINATOR_DETECTED_ONLY` (a particle only contributes
            to columns it actually carries -- column lengths vary).

    Returns:
        dict: ``{bucket_label: {'particle_count': int, 'total_values':
        {isotope: [values...]}}}``. ``particle_count`` is the bucket's TRUE
        membership count (independent of ``data_key``/gating below, so it
        doesn't fluctuate as the user switches data type) and drives both
        "sorted by abundance" and the row's ``(N)`` label downstream.
        Passthrough particles (no bucket) are excluded -- GROUPS has nothing
        to group them by.
    """
    rows = {}
    for p in particles:
        label = bucket_of(p)
        if label is None:
            continue
        entry = rows.setdefault(label, {'particle_count': 0, '_members': []})
        entry['particle_count'] += 1

        # An MFC-dependent key (particle_mass_fg etc.) that the classifier's
        # OWN collapse refused to write for this particle's bucket (a
        # multi-definition "drop_mfc" pooled group) must not have this
        # aggregation silently re-derive a mixed-MFC-basis number from raw
        # data the classifier itself declined to vouch for -- same principle
        # as composition_items_for_role's TOTAL_PARTICLE gate, applied here
        # to BOTH scopes: a per-isotope breakdown across the group's members
        # is itself the kind of cross-particle aggregation that gate exists
        # to block, so DEFINITION needs the same protection TOTAL_PARTICLE
        # does (unlike composition_items_for_role, where DEFINITION was safe
        # because it only ever echoed the classifier's own pre-vetted
        # collapsed number back, never re-read raw values itself).
        raw_snapshot = p.get(RAW_KEY)
        is_relabeled_key = isinstance(raw_snapshot, dict) and data_key in raw_snapshot
        if is_relabeled_key:
            definition_view = composition(p, data_key, collapsed=True)
            if label not in definition_view:
                continue

        isotopes = scope_isotopes(p, scope)
        raw_values = composition(p, data_key, collapsed=False)
        contributing = {iso: v for iso, v in raw_values.items() if iso in isotopes}
        entry['_members'].append(contributing)

    out = {}
    for label, entry in rows.items():
        total_values = {}
        members = entry['_members']
        if denominator == DENOMINATOR_DETECTED_ONLY:
            for contributing in members:
                for iso, v in contributing.items():
                    total_values.setdefault(iso, []).append(v)
        else:
            all_isotopes = set()
            for contributing in members:
                all_isotopes.update(contributing.keys())
            for contributing in members:
                for iso in all_isotopes:
                    total_values.setdefault(iso, []).append(contributing.get(iso, 0.0))
        out[label] = {'particle_count': entry['particle_count'],
                      'total_values': total_values}
    return out


#: Last-resort color for a bucket the registry has no usable color for.
#: Deliberately a real, visible color rather than None: a bucket that
#: silently renders as "no color at all" is indistinguishable from a bug
#: (and was one -- see ``default_row_bucket_colors``).
FALLBACK_BUCKET_COLOR = '#3B82F6'

#: The synthetic bucket the classifier assigns to particles that matched no
#: definition, when its unmatched mode is "unclassified" (the literal label
#: ``tools.particle_classifier_relabel`` emits and registers).
UNCLASSIFIED_LABEL = 'Unclassified'


def default_row_bucket_colors(input_data, row_particles,
                              include_unclassified=False):
    """Classifier-derived underline color(s) for one COLORS-mode heatmap row.

    A heatmap row (outside GROUPS role) is a raw isotope co-occurrence
    signature, not a single particle -- but classifier matching is
    presence-only (``tools.particle_classifier_expr``'s grammar has no
    value/threshold operators), so every particle sharing one row's exact
    isotope signature evaluates identically against every definition. A
    row's bucket membership is therefore always uniform: either every
    particle in it matches the same single bucket, or (``double_count``)
    every one of them matches the same SET of buckets. There is never a
    genuine per-particle split to weight -- an equal fraction per distinct
    matched bucket, collected across the row's members, is the complete
    answer (verified 2026-08-25; an earlier headcount-weighted-split design
    was based on a mistaken belief that value-based expressions existed in
    this grammar -- they don't).

    Args:
        input_data (dict | None): The node's upstream data (for bucket
            registry colors).
        row_particles (list): The particle dicts that collapsed into this
            one row (i.e. share its exact isotope signature). Under
            ``double_count`` this naturally includes >1 dict per real
            particle, one per matched bucket -- harmless here since only the
            resulting SET of labels is used.

        include_unclassified (bool): Whether the synthetic
            :data:`UNCLASSIFIED_LABEL` bucket earns a color. Defaults to
            **False**: "unclassified" and "passthrough" are two spellings of
            the same fact -- this particle matched nothing the user defined
            -- and they should look identical (uncolored) rather than
            differing purely because of an upstream mode switch that says
            nothing about the science. Colored = matched something the user
            actually defined.

    Returns:
        list[str]: Hex color strings, one per distinct matched bucket,
        registry-ordered (stable regardless of particle iteration order).
        Empty when the row has no colorable classified members (an
        all-passthrough or all-unclassified row -- nothing to color).

        A bucket whose registry entry carries no usable color still gets
        :data:`FALLBACK_BUCKET_COLOR` rather than being dropped: silently
        omitting it is indistinguishable from "this row isn't classified",
        which is exactly how a colorless-bucket bug hid itself once already.
    """
    labels_in_row = {bucket_of(p) for p in row_particles} - {None}
    if not include_unclassified:
        labels_in_row -= {UNCLASSIFIED_LABEL}
    if not labels_in_row:
        return []
    registry = bucket_registry(input_data)
    # Registry order first (stable, user-meaningful), then any label the
    # particles carry that the registry somehow doesn't list -- rather than
    # dropping it, which would silently under-color a real row.
    ordered_labels = [lbl for lbl in registry if lbl in labels_in_row]
    ordered_labels += sorted(labels_in_row - set(ordered_labels))
    return [bucket_color(input_data, lbl, FALLBACK_BUCKET_COLOR)
            for lbl in ordered_labels]


def has_multiple_buckets(input_data):
    """Whether faceting/encoding by bucket would produce more than one group.

    A single-bucket stream makes FACET and ENCODE degenerate (one panel, or
    one color) -- worth checking before offering them as meaningful.
    """
    return len(bucket_registry(input_data)) > 1


# ── Overlap mode / double-count awareness ──────────────────────────────

def overlap_mode(input_data):
    """The classifier's overlap resolution mode for this stream.

    Returns:
        str | None: ``'double_count'`` or ``'priority'``, or None when the
            stream isn't a classifier stream at all (nothing to report).
    """
    if not isinstance(input_data, dict):
        return None
    return input_data.get('_classifier_overlap_mode')


def is_double_count(input_data):
    """Whether a particle can be emitted into more than one bucket at once.

    Under ``double_count`` overlap mode, one source particle matching 2+
    definitions is emitted once per matching definition (see
    ``tools.particle_classifier_relabel.relabel_particles``). Any node that
    SUMS or COUNTS per bucket (GROUPS-role bar/pie/concentration charts) will
    therefore total to MORE than the real particle count when this is true
    -- worth surfacing to the user rather than leaving as an unexplained
    discrepancy.
    """
    return overlap_mode(input_data) == 'double_count'


# ── Mass-aware sorting for classifier bucket labels ─────────────────────

def mass_sort_key(input_data, label, data_key='elements'):
    """A numeric sort key that makes classifier bucket labels sort like
    isotopes, instead of tying at the "no parseable mass" fallback.

    ``results.utils_sort.sort_elements_by_mass`` sorts real isotope labels
    (e.g. ``'60Ni'``) by their embedded mass number, and falls back to a
    constant for anything it can't parse -- which is every classifier bucket
    label (``'Smelter'`` has no mass number), so under GROUPS role every
    bucket ties and the resulting order is just whatever the data happened
    to build in, not a real ordering. This computes each bucket's substitute:
    the MEAN mass number of the real isotopes actually present across every
    particle assigned to that bucket (via the classifier's dual-carried raw
    composition) -- e.g. a "Smelter" bucket defined by ``60Ni+107Ag`` sorts
    at roughly (60+107)/2, alongside isotopes of similar mass, rather than
    after all of them.

    A label that ISN'T a registered bucket (a real isotope -- OFF role, or a
    passthrough particle's own key showing through under GROUPS) falls
    through to its own parsed mass number, so this is a safe drop-in
    replacement for ``sort_elements_by_mass`` wherever ``input_data`` is
    available: identical behavior on non-classifier data, meaningful
    behavior on bucket labels.

    Args:
        input_data (dict | None): The node's upstream data.
        label (str): One bar/wedge/series label to compute a sort key for.
        data_key (str): Which composition dict to read masses from -- only
            matters in that it must be one whose keys are isotope labels
            (e.g. ``'elements'``); the values themselves aren't used.

    Returns:
        float: Ascending sort key, comparable across bucket and isotope
            labels alike.
    """
    from results.utils_sort import extract_mass_and_element
    registry = bucket_registry(input_data)
    if label not in registry:
        mass, _ = extract_mass_and_element(label)
        return mass
    particles = (input_data or {}).get('particle_data') or []
    masses = []
    for p in particles:
        if bucket_of(p) != label:
            continue
        for iso in composition(p, data_key).keys():
            m, _ = extract_mass_and_element(iso)
            if m != 999:
                masses.append(m)
    if masses:
        return sum(masses) / len(masses)
    return 999.0  # e.g. an Unclassified bucket with zero matched isotopes


def sort_labels_by_mass(input_data, labels, data_key='elements'):
    """``sort_elements_by_mass``-shaped drop-in that also handles bucket
    labels sanely (see :func:`mass_sort_key`)."""
    return sorted(labels, key=lambda lbl: mass_sort_key(input_data, lbl, data_key))


def sort_label_dict_by_mass(input_data, label_dict, data_key='elements'):
    """``sort_element_dict_by_mass``-shaped drop-in that also handles
    classifier bucket-label keys sanely (see :func:`mass_sort_key`).

    ``data_key`` intentionally stays at its ``'elements'`` default even when
    the caller is displaying a different quantity (mass/moles/diameter):
    it only reads isotope-key *vocabulary* to compute a mass number, never
    values, and ``elements`` (particle counts) is the one composition dict
    guaranteed present for every particle regardless of which quantity is
    selected for display.
    """
    if not label_dict:
        return label_dict
    ordered = sort_labels_by_mass(input_data, list(label_dict.keys()), data_key)
    return {label: label_dict[label] for label in ordered}


# ── Nodes whose classifier support is not shipped yet ──────────────────
#
# These viz nodes embed the shared ClassifierViewGroup UI (so a role picker
# APPEARS in their settings) but nothing in them ever reads the chosen role
# -- an audit on 2026-08-31 found the picker was inert on nine node types.
# Worse than inert, in fact: a classified particle's composition dict is
# destructively collapsed to {bucket_label: total}, so a node that reads
# particle['elements'] directly sees one synthetic "isotope" per bucket and
# renders confident nonsense rather than failing.
#
# Until each node gets its own role wiring (see the per-node checklist in
# .claude/aug24.md), the honest behaviour is the one the user asked for:
# operate EXACTLY as if no classifier were attached, and say so once.
# `declassified_stream` provides the "exactly as if" half.
CLASSIFIER_WIP_NODE_TYPES = frozenset({
    'pie_chart_plot',
    'element_composition_plot',
    'concentration_comparison',
    'molar_ratio_plot',
    'isotopic_ratio_plot',
    'single_multiple_element_plot',
    'network_diagram',
    'triangle_plot',
    # Built 2026-08-26 on branch `clank-away-at-correlation`, deleted with
    # that branch 2026-08-31 without ever being manually verified.
    'correlation_plot',
    # clustering_plot is hibernated by decision (the VALIDATE concept is its
    # own project), and is deliberately NOT listed -- it is blocked, not WIP.
})


def classifier_support_is_wip(node_type):
    """Whether classifier support is unshipped for this viz node type.

    Args:
        node_type (str | None): A viz node's ``node_type`` string.

    Returns:
        bool: True when the node must ignore classifier structure entirely.
    """
    return node_type in CLASSIFIER_WIP_NODE_TYPES


def declassified_particles(particles):
    """Particles as they would have been with no classifier in the chain.

    Two things have to be undone, and undoing only one of them still leaves
    a wrong plot:

    1. **The destructive collapse.** Each matched particle's composition
       dicts were replaced by ``{bucket_label: summed_total}``. The originals
       were dual-carried under :data:`RAW_KEY`, so they can be restored
       exactly -- this is the whole reason dual-carry exists.
    2. **``double_count`` copies.** A particle matching two definitions was
       emitted as two dicts. With no classifier there would be ONE particle,
       so leaving both in double-weights it in every count, sum and
       distribution. :func:`dedupe_particles` drops the copies.

    The ``_``-prefixed classifier keys are left on the returned dicts: they
    are additive, no non-classifier code path reads them, and stripping them
    would cost a second full copy for no benefit.

    Args:
        particles (list): Particle dicts from a classifier stream.

    Returns:
        list: New particle dicts with raw composition restored, one per real
        particle. Non-classifier particles pass through untouched.
    """
    out = []
    for p in dedupe_particles(particles or []):
        raw = p.get(RAW_KEY)
        if not isinstance(raw, dict):
            out.append(p)
            continue
        restored = dict(p)
        # Only the keys the classifier actually rewrote are in the snapshot;
        # everything else on the particle is already original.
        for data_key, original in raw.items():
            restored[data_key] = original
        out.append(restored)
    return out


def declassified_stream(input_data):
    """``input_data`` with classifier structure undone -- see
    :func:`declassified_particles`.

    Returns the input unchanged when it did not come through a classifier,
    so callers can apply this unconditionally in ``process_data``.

    ``selected_isotopes`` is restored from the ``_raw_selected_isotopes``
    snapshot too: the classifier replaces that list with its bucket labels,
    and a node that ignores buckets must be offered real isotopes to plot.

    Args:
        input_data (dict | None): Upstream data dict.

    Returns:
        dict | None: A shallow copy with raw particles, or the original.
    """
    if not is_classifier_stream(input_data):
        return input_data
    out = dict(input_data)
    out['particle_data'] = declassified_particles(
        input_data.get('particle_data') or [])
    raw_iso = input_data.get('_raw_selected_isotopes')
    if raw_iso:
        out['selected_isotopes'] = raw_iso
    # Drop the registry LAST: is_classifier_stream keys off it, so removing
    # it is what makes every downstream `is_classifier_stream` check answer
    # False and every role resolve to OFF, with no per-node cooperation.
    out.pop('_classifier_registry', None)
    return out


def adopt_declassified(node, input_data):
    """``process_data`` helper for a node whose classifier support is WIP.

    Records on the node whether classifier structure was actually stripped
    (so ``shared_plot_utils.maybe_warn_classifier_wip`` can tell the user
    once, and only when a classifier really is upstream), then returns the
    stream with that structure undone.

    Args:
        node: The viz node adopting the data.
        input_data (dict | None): Upstream data dict.

    Returns:
        dict | None: What the node should store as ``self.input_data``.
    """
    node._classifier_was_stripped = is_classifier_stream(input_data)
    return declassified_stream(input_data)
