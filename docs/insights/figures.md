# `figures.py`

Figures that tell the story behind a finding.

Besides the single plot a card proposes, every finding can be opened as a
Figure Builder figure with panels a to f and a legend underneath. The panels
tell the finding's story in order: the pattern itself, the evidence behind
it, what it means, and the limits to keep in mind. Wherever it helps, the
panels show the element in counts, mass and size, with the element's own
detection limit from the calibration marked on each axis (LOD in net counts,
MDL in fg, SDL in nm), so it is plain how much of a pattern sits near the
detection limit, and the legend quotes the values. Panels comparing samples
carry a significance test.

:func:`figure_for` builds the design; the panel adds it to the canvas as a
Figure Builder node fed by a selector holding the finding's samples.

---

## Constants

| Name | Value |
|------|-------|
| `QUANTITY_NAMES` | `{'counts': 'counts', 'mass': 'mass (fg)', 'd': 'size (nm)'}` |
| `WITH_COLOR` | `'#c2410c'` |
| `WITHOUT_COLOR` | `'#64748b'` |
| `LIMIT_NAMES` | `{'counts': 'LOD', 'mass': 'MDL', 'd': 'SDL'}` |
| `LIMIT_UNITS` | `{'counts': 'net counts', 'mass': 'fg', 'd': 'nm'}` |
| `LIMIT_SPREAD` | `1.1` |
| `DESIGNS` | `{'interference': _interference, 'isotope': _isotope_pair,…` |
| `ISOTOPE_DESIGNS` | `{_isotope_pair, _isotope_track, _isotope_groups}` |
| `MAX_PANELS` | `6` |

## Classes

### `FigureContext`

What the data offers the figure.

Attributes:
    quantities: Quantity prefixes present: ``counts``, ``mass``, ``d``.
    limits: ``(prefix, label)`` to ``{sample: value}``, each element's
        detection limit per sample from the calibration: net LOD in
        counts, MDL in fg and SDL in nm.
    smallest: ``(prefix, label)`` to the smallest detected value, used
        only where no calibrated limit is available.
    multi_sample: Whether the figure covers more than one sample.
    groups: How many samples or replicate groups the figure compares.
    used: ``(prefix, label)`` pairs whose limit a panel drew, filled while
        the story is built so the legend can quote their values.

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_panel` | `(kind: str, title: str, **settings) → dict` | One panel's settings, before it is given a place on the page. |
| `_expr` | `(prefix: str, label: str) → str` | Expression reading *label* in quantity *prefix*. |
| `_limit` | `(ctx: FigureContext, prefix: str, label: str) → dict` | Detection-limit line settings for a panel showing *label* in *prefix*. |
| `limits_sentence` | `(ctx: FigureContext) → str` | Legend sentence quoting the detection limits drawn in the figure. |
| `_fmt` | `(value: float) → str` | Short number for a legend. |
| `_histogram` | `(ctx: FigureContext, prefix: str, label: str, title: str='', **extra) ` | Histogram of one element in one quantity, with its detection limit marked. |
| `_quantity_panels` | `(ctx: FigureContext, label: str) → list[dict]` | Histograms of one element in every quantity the data carries. |
| `_with_without` | `(label: str, other: str) → dict` | Grouping rules splitting particles by whether they carry *other*. |
| `_by_sample` | `(ctx: FigureContext) → dict` | Group by sample when there is more than one. |
| `_detail` | `(s, label: str, default: str='') → str` | Return one of a finding's numbers by its label, or *default*. |
| `_ratio_lines` | `(natural, axis: str) → dict` | A reference line at the natural ratio on the given axis (``"x"`` or ``"y"``). |
| `_test` | `(groups: int, log_values: bool=True) → dict` | Significance test settings for a panel comparing *groups* groups. |
| `_test_sentence` | `(groups: int, what: str, log_values: bool=True) → str` | One sentence naming the test a panel shows and how to read it. |
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
| `story_layout` | `(n: int, caption: str='') → tuple[list[list[float]], list[float], floa` | Place *n* panels above a caption sized to its text. |
| `caption_text` | `(title: str, captions: list[str]) → str` | Write the figure legend: the title, then one sentence per panel letter. |
| `figure_for` | `(s, ctx: FigureContext) → dict \| None` | Build the figure that tells a finding's story, panels a to f with a legend. |
| `context_from` | `(particles: list[dict], labels, limits: dict \| None=None, multi_sample` | Work out what a figure can show from the particles it will draw. |
