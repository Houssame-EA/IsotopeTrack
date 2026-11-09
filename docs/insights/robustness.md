# `robustness.py`

How well each Insights finding holds up: effect, evidence, replicates, coincidence.

Detectors find patterns on the particles of a whole replicate group, where
thousands of particles make almost any trend significant. This module asks
the follow-up questions a reader would ask of a card:

* **Effect**: how large the pattern is, measured on the finding's particles.
* **Evidence**: the corrected significance the detector reported.
* **Reproducible**: whether the pattern is seen in each replicate on its own.
  The replicate, not the particle, is what was repeated, so a pattern carried
  by one replicate is flagged even when the pooled test is overwhelming.
* **Coincidence**: for two elements found in the same particles, how many such
  particles two particles arriving within one event would give by chance.

:func:`attach` stores the result on each finding as :class:`Evidence` and
lowers the ranking score of findings that do not hold in every replicate,
so the panel lists reproducible findings first.

---

## Constants

| Name | Value |
|------|-------|
| `MIN_REPLICATE_PARTICLES` | `25` |
| `MIN_REPLICATE_CORRELATION` | `0.5` |
| `RATIO_TOLERANCE` | `1.25` |
| `ISOTOPE_TOLERANCE` | `0.03` |
| `COINCIDENCE_MIN_FOLD` | `2.0` |
| `PAIR_KEYS` | `{'correlation', 'stoichiometry', 'cooccurrence_with'}` |
| `ASSESSORS` | `{'correlation': _correlation, 'stoichiometry': _stoichiom…` |
| `ELEMENTS_NEEDED` | `{'correlation': 2, 'stoichiometry': 2, 'cooccurrence_with…` |

## Classes

### `ReplicateCheck`

One replicate's result for a finding.

Attributes:
    label: Short replicate name shown on the card, such as ``"r2"``.
    ok: Whether the pattern holds in this replicate.
    value: The replicate's own number, such as ``"ρ +0.71"``.

### `Evidence`

What the card's evidence strip shows.

Attributes:
    effect: Size of the pattern, e.g. ``"ρ +0.61"`` or ``"3.3×"``.
    evidence: Corrected significance, e.g. ``"q = 3.1e-187"``; empty when
        the detector reported none.
    replicates: One check per replicate; empty when the finding's samples
        are not replicated.
    coincidence: ``(observed, expected)`` co-detections, or ``None``.

| Method | Signature | Description |
|--------|-----------|-------------|
| `n_ok` | `(self) → int` | Replicates where the pattern holds. |
| `reproducible` | `(self) → bool \| None` | Whether every replicate passes, or ``None`` when none were checked. |
| `coincidence_fold` | `(self) → float \| None` | Observed co-detections over those expected by chance. |
| `failed` | `(self) → list` | The replicates where the pattern is not seen. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_short` | `(member: str, group_name: str) → str` | Replicate label without its group name, e.g. ``"r2"`` for ``"Influent_r2"``. |
| `_replicate_units` | `(ctx, s) → list[tuple[object, list[tuple[str, int]]]]` | Replicated groups among a finding's samples, with each member's sample index. |
| `_labels` | `(units) → dict[str, str]` | Short card label for every replicate, prefixed by its group when several are shown. |
| `_scope_mask` | `(ctx, s) → np.ndarray` | Particles belonging to the finding's samples. |
| `_detail` | `(s, *names) → str` | First detail value whose label matches one of *names*. |
| `_evidence_text` | `(s) → str` | The corrected significance the detector wrote into its details. |
| `_spearman` | `(a: np.ndarray, b: np.ndarray) → float \| None` | Rank correlation of two arrays, or ``None`` when it cannot be computed. |
| `_correlation` | `(ctx, s, units, labels, mask) → Evidence` | Rank correlation of the two elements in each replicate. |
| `_stoichiometry` | `(ctx, s, units, labels, mask) → Evidence` | Median ratio of the two elements in each replicate, against the pooled one. |
| `_lift` | `(ctx, rows, a, b) → tuple[float, float, int] \| None` | Co-detections of *a* and *b* in *rows*, against independence. |
| `_cooccurrence` | `(ctx, s, units, labels, mask) → Evidence` | How much more, or less, often the two elements share particles in each replicate. |
| `_separated` | `(values: dict[str, float], groups: dict[str, list[str]], labels, fmt) ` | Check that every replicate of the top group sits above every replicate of the bottom one. |
| `_group_labels` | `(ctx, s) → tuple[dict, dict]` | Every compared sample's group, and card labels prefixed by group. |
| `_comparison` | `(ctx, s, units, labels, mask) → Evidence` | Median signal in each replicate, checked for a clean gap between the groups. |
| `_signature` | `(ctx, s, units, labels, mask) → Evidence` | Detection rate in each replicate, checked for a clean gap between the groups. |
| `_isotope` | `(ctx, s, units, labels, mask) → Evidence` | Median isotope ratio in each replicate, against the pooled one. |
| `_isotope_groups` | `(ctx, s, units, labels, mask) → Evidence` | Median isotope ratio in each replicate, checked for a clean gap between the groups. |
| `_ratio_split` | `(ctx, s, units, labels, mask) → Evidence` | The two populations' ratios in each replicate, checked for the same split. |
| `_times` | `(ctx) → tuple[np.ndarray, np.ndarray]` | Arrival time and event duration of every particle, cached on the context. |
| `_num` | `(x) → float` | A float, or NaN for anything that is not a number. |
| `coincidence` | `(ctx, a: str, b: str, mask: np.ndarray) → tuple[int, float] \| None` | Co-detections of two elements against those chance coincidence would give. |
| `assess` | `(ctx, s) → Evidence \| None` | Measure how well one finding holds up. |
| `rank_weight` | `(ev: Evidence \| None) → float` | Factor applied to a finding's ranking score from its evidence. |
| `attach` | `(ctx, suggestions: list) → list` | Store each finding's evidence on it and re-weight its ranking score. |
