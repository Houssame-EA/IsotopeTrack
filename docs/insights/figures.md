# `figures.py`

Four-panel figures that explain a finding.

Besides the single plot a card proposes, every finding can be opened as a
Figure Builder figure with panels a to d, chosen to show the evidence behind
it. Wherever it helps, the panels show the element in counts, mass and size,
with the detection threshold marked on count axes and the smallest detected
particle marked on mass and size axes, so it is plain how much of a pattern
sits near the detection limit.

:func:`figure_for` builds the design; the panel adds it to the canvas as a
Figure Builder node fed by a selector holding the finding's samples.

---

## Constants

| Name | Value |
|------|-------|
| `QUANTITY_NAMES` | `{'counts': 'counts', 'mass': 'mass (fg)', 'd': 'size (nm)'}` |
| `GRID` | `([0.0, 0.0, 0.5, 0.5], [0.5, 0.0, 0.5, 0.5], [0.0, 0.5, 0…` |
| `WITH_COLOR` | `'#c2410c'` |
| `WITHOUT_COLOR` | `'#64748b'` |
| `DESIGNS` | `{'interference': _interference, 'isotope': _isotope_pair,…` |
| `ISOTOPE_DESIGNS` | `{_isotope_pair, _isotope_track, _isotope_groups}` |

## Classes

### `FigureContext`

What the data offers the figure.

Attributes:
    quantities: Quantity prefixes present: ``counts``, ``mass``, ``d``.
    thresholds: Isotope label to its detection threshold in counts, where
        the processing recorded one.
    smallest: ``(prefix, label)`` to the smallest detected value, used to
        mark the practical detection limit on mass and size axes.
    multi_sample: Whether the figure covers more than one sample.

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_panel` | `(kind: str, title: str, **settings) → dict` | One panel's settings, before it is given a place on the page. |
| `_expr` | `(prefix: str, label: str) → str` | Expression reading *label* in quantity *prefix*. |
| `_limit` | `(ctx: FigureContext, prefix: str, label: str) → dict` | Detection-limit line settings for a panel showing *label* in *prefix*. |
| `_histogram` | `(ctx: FigureContext, prefix: str, label: str, title: str='', **extra) ` | Histogram of one element in one quantity, with its detection limit marked. |
| `_quantity_panels` | `(ctx: FigureContext, label: str) → list[dict]` | Histograms of one element in every quantity the data carries. |
| `_with_without` | `(label: str, other: str) → dict` | Grouping rules splitting particles by whether they carry *other*. |
| `_by_sample` | `(ctx: FigureContext) → dict` | Group by sample when there is more than one. |
| `_interference` | `(s, ctx)` |  |
| `_isotope_pair` | `(s, ctx, natural=None)` |  |
| `_isotope_track` | `(s, ctx, natural=None)` |  |
| `_isotope_groups` | `(s, ctx, natural=None)` |  |
| `_comparison` | `(s, ctx)` |  |
| `_replicates` | `(s, ctx)` |  |
| `_signature` | `(s, ctx)` |  |
| `_stoichiometry` | `(s, ctx)` |  |
| `_correlation` | `(s, ctx)` |  |
| `_cooccurrence` | `(s, ctx)` |  |
| `_rare` | `(s, ctx)` |  |
| `_distribution` | `(s, ctx)` |  |
| `_size_trend` | `(s, ctx)` |  |
| `_time` | `(s, ctx)` |  |
| `_composition` | `(s, ctx)` |  |
| `_network` | `(s, ctx)` |  |
| `_outlier` | `(s, ctx)` |  |
| `_needs_elements` | `(s) → bool` | Whether the design for *s* needs the elements it names to exist. |
| `figure_for` | `(s, ctx: FigureContext) → dict \| None` | Build the four-panel figure explaining a finding. |
| `context_from` | `(particles: list[dict], labels, thresholds: dict \| None=None, multi_sa` | Work out what a figure can show from the particles it will draw. |
