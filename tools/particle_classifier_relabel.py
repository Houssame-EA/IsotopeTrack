# -*- coding: utf-8 -*-
"""Particle relabeling logic for the Particle Classifier node (Stage 4).

Pure Python, no Qt: given a node's definitions/groups/overlap-mode/
unmatched-mode configuration and a list of particle dicts for one sample,
decide which definition (if any) each particle matches, resolve overlaps,
and relabel matched particles' composition dicts under their assigned
group label — per ``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §5, §6, §7.

Composition-dict aggregation policy (confirmed against the app's actual
Mass Fraction Calculator semantics — see ``mainwindow.py``'s
``get_mass_fraction``/``get_molecular_weight`` and the per-particle
calculation loop around ``particle['particle_mass_fg'] = ...``):

- ``elements`` (counts), ``element_mass_fg``, ``element_moles_fmol`` are
  raw, additive, MFC-independent quantities — always safely summed across
  a definition's matched isotopes.
- ``mass_percentages``/``mole_percentages`` are ratios of the above over
  particle-wide totals that do not change under a same-particle relabel,
  so they are additive too (sum of the matched isotopes' own percentages)
  and are always safely recomputed.
- ``particle_mass_fg``/``particle_moles_fmol``/``mass_fg`` (and the
  metadata feeding them: ``mass_fractions_used``, ``densities_used``,
  ``molar_masses``) depend on a *per-element* Mass Fraction Calculator
  choice (compound formula / density / molecular weight) that can
  legitimately differ between isotopes. Merging isotopes that all belong
  to the SAME definition is still safe (they're already one particle's
  internally-consistent composition, no different from how the app
  already reports multi-isotope particles today). Merging PARTICLES from
  DIFFERENT definitions pooled under one shared group name is where the
  ambiguity lives: those particles may carry different underlying MFC
  assumptions, so a mean/aggregate of their ``particle_mass_fg`` mixes
  incompatible bases ("apples and oranges labelled as bananas"). This
  module never silently decides that question — see ``GroupPoolingPolicy``
  below, chosen once per multi-definition group via the dialog's warning
  modal (design §11: no silent user-facing decisions).

Diameter fields (``element_diameter_nm``, ``particle_diameter_nm``) are
never read or written anywhere in this module, per the standing
project-wide constraint (``.claude/SESSION_CONTEXT.md`` §2 /
``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §2).
"""

from __future__ import annotations

from typing import Literal

from tools.particle_classifier_expr import (
    parse, ExpressionSyntaxError, evaluate, referenced_isotopes,
)

import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.particle_classifier_relabel")

#: Composition dicts that are always safely summed across a matched
#: definition's referenced isotopes, regardless of group pooling.
_ADDITIVE_KEYS = ('elements', 'element_mass_fg', 'element_moles_fmol')

#: Composition dicts that are additive too (ratios over an unchanged
#: particle-wide total), recomputed the same way as _ADDITIVE_KEYS.
_PERCENTAGE_KEYS = ('mass_percentages', 'mole_percentages')

#: Composition/metadata dicts that depend on a per-element Mass Fraction
#: Calculator choice and are only safe to keep when a group is backed by
#: exactly one definition (see module docstring / GroupPoolingPolicy).
_MFC_DEPENDENT_KEYS = (
    'particle_mass_fg', 'particle_moles_fmol', 'mass_fg',
    'mass_fractions_used', 'densities_used', 'molar_masses',
)

GroupPoolingPolicy = Literal["keep", "drop_mfc"]

#: Every composition dict the relabel pass rewrites or drops. Their
#: pre-relabel originals are carried through under ``RAW_KEY`` so downstream
#: nodes that need real isotopes (rather than the collapsed bucket label)
#: can still get at them -- see the "dual-carry" note below.
_RELABELED_KEYS = _ADDITIVE_KEYS + _PERCENTAGE_KEYS + _MFC_DEPENDENT_KEYS

#: Per-particle key holding ``{composition_key: original_dict}`` -- the
#: untouched, real-isotope-keyed composition dicts as they arrived from
#: upstream.
#:
#: **Dual-carry**: the destructive collapse in :func:`_relabel_composition`
#: is preserved exactly as-is (so every downstream node that reads one
#: composition key at a time keeps behaving identically), and the originals
#: ride along beside it. This costs essentially nothing:
#: :func:`_relabel_composition` *builds new dicts* and never mutates the
#: source, so these are shared references, not copies.
#:
#: The leading underscore is deliberate and load-bearing:
#: ``save_export/fast_project_io.py`` silently drops ``_``-prefixed particle
#: keys on save, while routing any *other* unrecognized key into a
#: per-particle ``extras`` dict -- which would defeat the columnar save
#: format. The underscore is what keeps dual-carry off disk.
RAW_KEY = '_classifier_raw'

#: Per-particle key holding the assigned bucket label (str), or None for a
#: particle that passed through unclassified under ``unmatched_mode ==
#: "passthrough"`` and therefore still carries its real composition.
BUCKET_KEY = '_classifier_bucket'

#: Per-particle key holding this particle's index within its source sample's
#: input list. Needed because the codebase has no per-particle identity of
#: any kind, and ``double_count`` overlap mode emits ONE input particle as
#: SEVERAL output particles (one per matching definition). Any statistic
#: computed over real isotopes downstream (Pearson r, network edge weights,
#: clustering) would silently double-weight such a particle without a key to
#: dedupe on. Unique only *within* a sample, so the real identity is the
#: pair ``(source_sample, _classifier_src_index)`` -- see
#: ``results.classifier_view.particle_identity``.
SRC_INDEX_KEY = '_classifier_src_index'

#: Per-particle key holding the SET of isotopes that this particle's own
#: matched definition(s) actually reference -- i.e. exactly the isotope set
#: :func:`_relabel_composition` used to build the bucket-collapsed entry
#: above (the ``elements``/``element_mass_fg``/etc. keys). This is how a
#: downstream reader recovers "which isotopes were summed into this bucket
#: value" once that value is just a single collapsed number with no memory
#: of its own inputs.
#:
#: **Why this exists (counting-scope note, flagged per explicit request)**:
#: a matched particle's bucket total has always counted only the isotopes
#: its triggering expression names -- e.g. a "Smelter" particle defined by
#: ``60Ni`` contributes only its ``60Ni`` mass/moles/count to Smelter's
#: total, even if that same particle also carries Fe, Cu, or anything else.
#: That is a deliberate, still-supported reading ("of the isotopes that
#: DEFINE this group, how much is there") but it is not the only one a
#: scientist needs: "of the particles that QUALIFY for this group, how much
#: are they emitting in total" requires every isotope the qualifying
#: particle actually carries, not just the trigger isotope(s). Neither
#: reading is more "correct" than the other -- they answer different
#: questions -- so both stay available: the classifier's own collapse above
#: keeps computing the DEFINITION-scoped answer (unchanged, so every
#: already-shipped node is bit-for-bit unaffected), and a viz node that
#: wants the TOTAL-PARTICLE answer instead reads this isotope set (or, for
#: "every isotope on the particle" specifically, just the particle's own
#: full raw composition -- no dual-carry needed for that half) via
#: ``results.classifier_view``'s ``SCOPE_DEFINITION`` / ``SCOPE_TOTAL_PARTICLE``
#: choice. Absent for a passthrough particle (no bucket was ever assigned,
#: so the question doesn't apply). Explicitly set to "every isotope the
#: particle carries" for Unclassified, since there is no expression to
#: scope by in the first place -- DEFINITION and TOTAL-PARTICLE are
#: therefore always the SAME set for Unclassified, by construction, not by
#: special-casing.
MATCH_ISOTOPES_KEY = '_classifier_match_isotopes'


def _raw_composition_snapshot(particle):
    """Capture references to a particle's pre-relabel composition dicts.

    Args:
        particle (dict): The source particle, read-only here.

    Returns:
        dict: ``{composition_key: original_dict}`` for every relabeled key
            actually present on the particle. Values are the *same* dict
            objects, not copies -- safe because nothing in this module
            mutates a source particle's composition dicts (they are rebuilt,
            see :func:`_relabel_composition`).
    """
    snap = {}
    for key in _RELABELED_KEYS:
        src = particle.get(key)
        if isinstance(src, dict):
            snap[key] = src
    return snap


def group_pooling_status(definitions):
    """Classify every group by how many definitions feed into it.

    Args:
        definitions (list): The node's definition dicts.

    Returns:
        dict: ``{group_name: n_definitions}`` for every group name actually
            referenced by at least one definition (a group registered but
            unused by any definition is omitted). Definitions with no
            ``group_name`` are each their own bucket of one and never
            appear here.
    """
    counts = {}
    for d in definitions:
        name = d.get('group_name')
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def multi_definition_groups(definitions):
    """List group names backed by 2+ definitions (design's ambiguity case).

    Args:
        definitions (list): The node's definition dicts.

    Returns:
        list: Group names with more than one definition assigned.
    """
    counts = group_pooling_status(definitions)
    return sorted(name for name, n in counts.items() if n > 1)


def _bucket_label_and_color(d, groups):
    """Resolve one matched definition's output label and color.

    Args:
        d (dict): The matched definition.
        groups (dict): ``{group_name: color}`` registry (global).

    Returns:
        tuple: (label, color).
    """
    group = d.get('group_name')
    if group:
        return group, groups.get(group, d.get('color') or '#3B82F6')
    label = d.get('expression_text') or d.get('id')
    return label, d.get('color') or '#3B82F6'


def suggested_label_colors(definitions, groups, unmatched_mode, unclassified_color):
    """Build the ``{label: hex}`` map for every synthetic label this node
    can produce, so downstream viz nodes can seed their own default bar/
    legend colors from the color the user already chose in this dialog
    (see :func:`results.shared_plot_utils.seed_suggested_element_colors`).

    Args:
        definitions (list): The node's definitions (any/all samples).
        groups (dict): ``{group_name: color}`` registry, deliberately
            GLOBAL across every sample (see
            :class:`tools.particle_classifier_node.ParticleClassifierNode`'s
            ``groups`` docstring) -- a group name means one consistent
            color for that substance everywhere it's used.
        unmatched_mode ("unclassified" | "discard" | "passthrough"): §6.
        unclassified_color (str): Color for the Unclassified bucket.

    Returns:
        dict: ``{label: hex_color}`` for every label this node's current
            configuration can emit.
    """
    out = {}
    for d in definitions:
        if not (d.get('expression_text') or '').strip():
            continue
        label, color = _bucket_label_and_color(d, groups)
        out[label] = color
    if unmatched_mode == 'unclassified':
        out['Unclassified'] = unclassified_color
    return out


def build_bucket_registry(definitions, groups, unmatched_mode,
                          unclassified_color):
    """Describe every bucket label this configuration can emit.

    Downstream nodes need more than the friendly bucket name to be
    scientifically useful: "orange = Smelter" tells a scientist nothing
    about what actually qualifies as a Smelter particle -- the isotope
    expression does (``.claude/july22.md`` #8). This is the lookup that
    makes the literal expression recoverable at render time.

    Deliberately **list-shaped** on ``definitions``: a group backed by 2+
    definitions (see :func:`multi_definition_groups`) has that many
    expressions and match-modes, and flattening them to a single string
    would silently drop all but one.

    Args:
        definitions (list): The node's definitions (any/all samples).
        groups (dict): ``{group_name: color}`` registry, global across
            samples.
        unmatched_mode ("unclassified" | "discard" | "passthrough"): §6.
        unclassified_color (str): Color for the Unclassified bucket.

    Returns:
        dict: ``{label: {'color': hex, 'is_group': bool, 'definitions':
            [{'id', 'expression_text', 'match_mode', 'target_sample'}, ...]}}``.
            Definitions with a blank expression are skipped. Labels are not
            guaranteed unique across definitions (two ungrouped definitions
            can share expression text, and a group name can collide with
            another definition's expression text) -- colliding definitions
            accumulate into one entry's ``definitions`` list rather than
            overwriting each other, and a warning is logged.
    """
    out = {}
    for d in definitions:
        if not (d.get('expression_text') or '').strip():
            continue
        label, color = _bucket_label_and_color(d, groups)
        entry = out.get(label)
        if entry is None:
            entry = out[label] = {
                'color': color,
                'is_group': bool(d.get('group_name')),
                'definitions': [],
            }
        elif entry['color'] != color:
            _itk_log.warning(
                "Bucket label %r is produced by definitions with differing "
                "colors (%r vs %r); keeping the first.",
                label, entry['color'], color)
        entry['definitions'].append({
            'id': d.get('id'),
            'expression_text': d.get('expression_text'),
            'match_mode': d.get('match_mode', 'partial'),
            'target_sample': d.get('target_sample'),
        })
    for label, entry in out.items():
        if not entry['is_group'] and len(entry['definitions']) > 1:
            _itk_log.warning(
                "Bucket label %r is produced by %d separate ungrouped "
                "definitions (identical expression text); downstream nodes "
                "will treat them as one bucket.",
                label, len(entry['definitions']))
    if unmatched_mode == 'unclassified':
        out.setdefault('Unclassified', {
            'color': unclassified_color,
            'is_group': False,
            'definitions': [],
        })
    return out


def _parse_definitions(definitions):
    """Parse every definition's expression exactly once.

    ``parse()`` is a pure function of ``expression_text`` alone — it does
    not depend on any particle — so it must never run inside a per-particle
    loop. :func:`relabel_particles` calls this once per classification pass
    (not once per particle) and reuses the result across every particle,
    which is what actually matters for large particle populations: with
    N particles and M definitions, parsing/re-parsing per particle costs
    O(N*M) redundant work for something that is really only O(M).

    Args:
        definitions (list): Definitions to parse.

    Returns:
        dict: ``{definition_id: (ast, referenced_isotopes_set)}``, omitting
            any definition with blank or unparseable expression text (a
            warning is logged once per such definition here, not once per
            particle that would otherwise have re-triggered it).
    """
    parsed = {}
    for d in definitions:
        text = d.get('expression_text', '')
        if not text.strip():
            continue
        try:
            ast = parse(text)
        except ExpressionSyntaxError:
            _itk_log.warning(
                "Definition %s has an unparseable expression at "
                "classification time, skipping: %r", d.get('id'), text)
            continue
        parsed[d['id']] = (ast, referenced_isotopes(ast))
    return parsed


def classify_particle(particle, definitions, overlap_mode, parsed=None):
    """Decide which definition(s) match one particle.

    Args:
        particle (dict): A particle dict (only its ``elements`` key's
            keys are used to build the present-isotope set — matches the
            app's existing convention that presence is driven by raw
            counts, see ``tools.particle_filter.detected_labels``).
        definitions (list): Definitions to test, already filtered to the
            particle's sample and in priority order (index 0 = highest).
        overlap_mode ("double_count" | "priority"): §5 semantics.
        parsed (dict | None): Precomputed :func:`_parse_definitions` result
            to reuse instead of re-parsing on every call — pass this from
            any per-particle loop. When omitted (e.g. direct/test callers
            classifying a single particle in isolation), each definition
            is parsed on demand exactly as before.

    Returns:
        list: Matched definitions, in priority order. Under
            ``"priority"`` mode this list has at most one entry (the
            highest-priority match; a particle claimed by it is invisible
            to every lower-priority definition — no partial claiming).
            Under ``"double_count"`` every matching definition is
            returned.
    """
    present = set((particle.get('elements') or {}).keys())
    matched = []
    for d in definitions:
        text = d.get('expression_text', '')
        if not text.strip():
            continue
        if parsed is not None:
            entry = parsed.get(d['id'])
            if entry is None:
                continue
            ast, _isotopes = entry
        else:
            try:
                ast = parse(text)
            except ExpressionSyntaxError:
                _itk_log.warning(
                    "Definition %s has an unparseable expression at "
                    "classification time, skipping: %r", d.get('id'), text)
                continue
        mode = d.get('match_mode', 'partial')
        if evaluate(ast, present, mode):
            matched.append(d)
            if overlap_mode == 'priority':
                break
    return matched


def count_matches_per_definition(particles, definitions, overlap_mode):
    """Effective per-definition particle-match counts for one sample.

    "Effective" means post-priority-resolution, not each definition's raw
    formula match in isolation: reuses :func:`classify_particle`'s own
    matching, so under ``"priority"`` mode a particle already claimed by a
    higher-priority definition does not also count toward a lower-priority
    one (matches classify_particle's break-on-first-match semantics
    exactly); under ``"double_count"`` every definition a particle matches
    gets credit independently. This is intentionally the same notion of
    "match" the real relabeling pass uses, so the displayed count matches
    what downstream viz nodes will actually show — not just "how many
    particles satisfy this expression in a vacuum."

    Intended to be called only at explicit commit points (dialog OK /
    Apply to Current/Selected Samples), never per keystroke — see the
    dialog's ``_recompute_match_counts_for_sample``.

    Args:
        particles (list): Particle dicts for one sample.
        definitions (list): This sample's definitions, in priority order.
        overlap_mode ("double_count" | "priority"): §5.

    Returns:
        dict: ``{definition_id: count}`` for every definition passed in
            (0 for definitions that matched nothing, including blank or
            unparseable expressions).
    """
    parsed = _parse_definitions(definitions)
    counts = {d['id']: 0 for d in definitions}
    for p in particles:
        for d in classify_particle(p, definitions, overlap_mode, parsed=parsed):
            counts[d['id']] += 1
    return counts


def _relabel_composition(particle, label, isotopes, keep_mfc_keys):
    """Build the relabeled composition dicts for one matched particle.

    Args:
        particle (dict): Source particle (read-only here).
        label (str): The synthetic label to key every aggregated dict by.
        isotopes (set): The matched definition's referenced isotopes to
            aggregate (only these keys are pulled from each composition
            dict — any other isotope present on the particle but outside
            the matched definition's own vocabulary is correctly excluded,
            same as the evaluator's partial/exact semantics already do).
        keep_mfc_keys (bool): Whether to also aggregate/keep the
            MFC-dependent keys (True for single-definition groups, False
            for multi-definition groups whose policy resolved to
            "drop_mfc").

    Returns:
        dict: ``{key: {label: value}}`` for every relabeled key that had
            at least one matched isotope present, ready to assign onto a
            copy of ``particle``.
    """
    out = {}
    for key in _ADDITIVE_KEYS:
        src = particle.get(key) or {}
        total = sum(v for iso, v in src.items() if iso in isotopes)
        if any(iso in src for iso in isotopes):
            out[key] = {label: total}
    for key in _PERCENTAGE_KEYS:
        src = particle.get(key) or {}
        total = sum(v for iso, v in src.items() if iso in isotopes)
        if any(iso in src for iso in isotopes):
            out[key] = {label: total}
    if keep_mfc_keys:
        for key in _MFC_DEPENDENT_KEYS:
            src = particle.get(key)
            if not isinstance(src, dict):
                continue
            present_isotopes = [iso for iso in isotopes if iso in src]
            if not present_isotopes:
                continue
            if key in ('mass_fractions_used', 'densities_used', 'molar_masses'):
                # Per-element calculator metadata, not an additive value —
                # keep the first matched isotope's entry as a representative
                # snapshot rather than fabricating a combined number.
                out.setdefault(key, {})[label] = src[present_isotopes[0]]
            else:
                # particle_mass_fg / particle_moles_fmol / mass_fg: safe to
                # sum only because every referenced isotope belongs to the
                # SAME definition, i.e. the same single particle's own
                # already-internally-consistent composition (see module
                # docstring) — this is the single-definition-group case.
                out[key] = {label: sum(src[iso] for iso in present_isotopes)}
    return out


def relabel_particles(particles, definitions, groups, overlap_mode,
                      unmatched_mode, unclassified_color,
                      group_pooling_policies=None):
    """Relabel one sample's particles per the node's classifier config.

    Args:
        particles (list): Particle dicts for one sample (already filtered
            to that sample by the caller).
        definitions (list): This sample's definitions
            (``target_sample``-filtered and in global priority order —
            see :meth:`tools.particle_classifier_node.ParticleClassifierNode.definitions_for_sample`).
        groups (dict): ``{group_name: color}`` registry (global across
            samples). Only ever used here to resolve a label, never a
            color -- the label output doesn't actually depend on it
            either (grouped definitions label by ``group_name``
            directly), so this is effectively inert; kept for API
            symmetry with :func:`suggested_label_colors` and in case a
            future caller needs it.
        overlap_mode ("double_count" | "priority"): §5.
        unmatched_mode ("unclassified" | "discard" | "passthrough"): §6.
        unclassified_color (str): Color for the Unclassified bucket.
        group_pooling_policies (dict | None): ``{group_name: "keep" |
            "drop_mfc"}`` for every multi-definition group (see
            :func:`multi_definition_groups`), as chosen by the user via
            the dialog's warning modal. A multi-definition group with no
            recorded policy defaults to ``"drop_mfc"`` (the safe choice —
            never fabricate a mixed-basis particle-mass number without an
            explicit user opt-in).

    Returns:
        list: New particle dicts (shallow copies; upstream data is never
            mutated). Double-counted particles (design §5, "double_count"
            mode with 2+ simultaneous matches) appear once per matching
            definition, each copy relabeled for that one definition/group.
    """
    group_pooling_policies = group_pooling_policies or {}
    multi_groups = set(multi_definition_groups(definitions))
    parsed = _parse_definitions(definitions)
    out = []
    for src_index, p in enumerate(particles):
        raw = _raw_composition_snapshot(p)
        matches = classify_particle(p, definitions, overlap_mode, parsed=parsed)
        if not matches:
            if unmatched_mode == 'discard':
                continue
            elif unmatched_mode == 'passthrough':
                copy = p.copy()
                # Passthrough particles keep their real composition, so RAW_KEY
                # is redundant for them -- set it anyway so every particle in
                # the stream answers the same way and readers never need a
                # special case (see results.classifier_view.composition).
                copy[RAW_KEY] = raw
                copy[BUCKET_KEY] = None
                copy[SRC_INDEX_KEY] = src_index
                out.append(copy)
                continue
            else:  # 'unclassified'
                copy = p.copy()
                all_isotopes = set((p.get('elements') or {}).keys())
                copy.update(_relabel_composition(
                    p, 'Unclassified', all_isotopes, keep_mfc_keys=True))
                copy[RAW_KEY] = raw
                copy[BUCKET_KEY] = 'Unclassified'
                copy[SRC_INDEX_KEY] = src_index
                # No expression to scope by, so DEFINITION and TOTAL-PARTICLE
                # are the same set here by construction (see MATCH_ISOTOPES_KEY).
                copy[MATCH_ISOTOPES_KEY] = all_isotopes
                out.append(copy)
                continue
        for d in matches:
            entry = parsed.get(d['id'])
            if entry is None:
                continue
            _ast, isotopes = entry
            label, _color = _bucket_label_and_color(d, groups)
            group = d.get('group_name')
            if group and group in multi_groups:
                # 2+ definitions pool into this group: only keep the
                # MFC-dependent dicts if the user explicitly opted in via
                # the dialog's warning modal; default to the safe choice
                # (drop) when no policy was ever recorded (design §11 —
                # never silently fabricate a mixed-basis number).
                keep_mfc = group_pooling_policies.get(group) == 'keep'
            else:
                # No group, or a group backed by exactly one definition:
                # always safe, this is pure relabeling of one already
                # internally-consistent particle population.
                keep_mfc = True
            copy = p.copy()
            copy.update(_relabel_composition(p, label, isotopes, keep_mfc))
            if not keep_mfc:
                # p.copy() is shallow: the MFC-dependent keys are still
                # present (still keyed by the ORIGINAL isotope labels,
                # never relabeled) unless explicitly removed here.
                for key in _MFC_DEPENDENT_KEYS:
                    copy.pop(key, None)
            copy[RAW_KEY] = raw
            copy[BUCKET_KEY] = label
            # Every copy emitted for this source particle shares one index --
            # which is exactly the dedupe key downstream statistics need under
            # double_count (see SRC_INDEX_KEY).
            copy[SRC_INDEX_KEY] = src_index
            # This copy's own DEFINITION-scoped isotope set -- see
            # MATCH_ISOTOPES_KEY. Under double_count, each of a particle's
            # several copies carries its OWN matched definition's isotopes
            # here (not the union), consistent with each copy representing
            # that one definition's claim on the particle.
            copy[MATCH_ISOTOPES_KEY] = set(isotopes)
            out.append(copy)
    return out
