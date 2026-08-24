# `particle_classifier_relabel.py`

Particle relabeling logic for the Particle Classifier node (Stage 4).

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

---

## Constants

| Name | Value |
|------|-------|
| `_ADDITIVE_KEYS` | `('elements', 'element_mass_fg', 'element_moles_fmol')` |
| `_PERCENTAGE_KEYS` | `('mass_percentages', 'mole_percentages')` |
| `_MFC_DEPENDENT_KEYS` | `('particle_mass_fg', 'particle_moles_fmol', 'mass_fg', 'm…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `group_pooling_status` | `(definitions)` | Classify every group by how many definitions feed into it. |
| `multi_definition_groups` | `(definitions)` | List group names backed by 2+ definitions (design's ambiguity case). |
| `_bucket_label_and_color` | `(d, groups)` | Resolve one matched definition's output label and color. |
| `suggested_label_colors` | `(definitions, groups, unmatched_mode, unclassified_color)` | Build the ``{label: hex}`` map for every synthetic label this node |
| `_parse_definitions` | `(definitions)` | Parse every definition's expression exactly once. |
| `classify_particle` | `(particle, definitions, overlap_mode, parsed=None)` | Decide which definition(s) match one particle. |
| `count_matches_per_definition` | `(particles, definitions, overlap_mode)` | Effective per-definition particle-match counts for one sample. |
| `_relabel_composition` | `(particle, label, isotopes, keep_mfc_keys)` | Build the relabeled composition dicts for one matched particle. |
| `relabel_particles` | `(particles, definitions, groups, overlap_mode, unmatched_mode, unclass` | Relabel one sample's particles per the node's classifier config. |
