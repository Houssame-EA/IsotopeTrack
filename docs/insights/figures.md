# `figures.py`

Figures that tell the story behind a finding.

Besides the single plot a card proposes, every finding can be opened as a
Figure Builder figure with panels a to f and a legend underneath. The panels
tell the finding's story in order: the pattern itself, the evidence behind
it, what it means, and the limits to keep in mind. Amounts are shown in one
unit only: element mass (fg), or counts when the samples carry no mass
calibration. Findings about the ion signal itself, isotope ratios,
interferences and signal drift, stay in counts, where they arise. Each axis
marks the element's own detection limit from the calibration (MDL in fg,
LOD in net counts), so it is plain how much of a pattern sits near the
detection limit, and the legend quotes the values. Panels comparing samples
carry a significance test, run on replicate medians when the samples are
replicated.

When the figure's particles are known (:attr:`FigureContext.table`), the
legend reports what the panels show, measured on those same particles with
:mod:`results.insights.evidence`, and closes with a line of checks, each
passed or failed. Legends sit below their plot and reference lines are named
there, so no writing covers the data.

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
| `BETWEEN_DESIGNS` | `frozenset({_comparison, _replicates, _signature, _isotope…` |
| `MAX_PANELS` | `6` |
| `OVERLAY_KINDS` | `frozenset({'histogram', 'ecdf', 'box', 'violin', 'bar', '…` |
| `MAX_SPLIT_GROUPS` | `3` |
| `MAX_GROUP_ROWS` | `4` |
| `XY_KINDS` | `frozenset({'scatter', 'hexbin', 'density', 'contour'})` |
| `GROUP_ROW_VIEWS` | `3` |

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
    main: The element detected in most of the figure's particles.
    present: Isotopes detected in enough particles to plot.
    table: The particle table the figure will draw from, when known;
        the legend's measured numbers and checks need it.
    mass_bias: The exponential-law reference set up in an Isotopic Ratio
        node, ``{ref_num, ref_den, certified, measured}``, when there is
        one; isotope ratios are then corrected for mass bias.
    checks: The checks run while the story is built, closing the legend.

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_panel` | `(kind: str, title: str, **settings) → dict` | One panel's settings, before it is given a place on the page. |
| `_expr` | `(prefix: str, label: str) → str` | Expression reading *label* in quantity *prefix*. |
| `_limit` | `(ctx: FigureContext, prefix: str, label: str) → dict` | Detection-limit line settings for a panel showing *label* in *prefix*. |
| `limits_sentence` | `(ctx: FigureContext) → str` | Legend sentence quoting the detection limits drawn in the figure. |
| `_fmt` | `(value: float) → str` | Short number for a legend. |
| `_histogram` | `(ctx: FigureContext, prefix: str, label: str, title: str='', **extra) ` | Histogram of one element in one quantity, with its detection limit marked. |
| `_unit` | `(ctx: FigureContext) → str` | The one quantity amount panels use: mass when calibrated, counts otherwise. |
| `_amount` | `(ctx: FigureContext, label: str) → str` | Expression reading *label* in the figure's amount unit. |
| `_amount_name` | `(ctx: FigureContext, label: str) → str` | Axis name for *label* in the figure's amount unit, e.g. ``"Pb mass (fg)"``. |
| `_with_without` | `(label: str, other: str) → dict` | Grouping rules splitting particles by whether they carry *other*. |
| `_by_sample` | `(ctx: FigureContext) → dict` | Group by sample when there is more than one. |
| `_detail` | `(s, label: str, default: str='') → str` | Return one of a finding's numbers by its label, or *default*. |
| `_ratio_lines` | `(natural, axis: str) → dict` | A reference line at the natural ratio on the given axis (``"x"`` or ``"y"``). |
| `_test` | `(groups: int, log_values: bool=True) → dict` | Significance test settings for a panel comparing *groups* groups. |
| `_test_sentence` | `(groups: int, what: str, log_values: bool=True) → str` | One sentence naming the test a panel shows and how to read it. |
| `_crust_known` | `(minor: str, major: str) → bool` | Whether the upper crust gives a ratio for *minor* to *major*. |
| `_can_check` | `(ctx: FigureContext, major: str, minor: str) → bool` | Whether a detectability check of *minor* in *major* particles can be drawn. |
| `_detect_box` | `(ctx: FigureContext, major: str, minor: str, title: str, **grouping) →` | Box plot of the major element's mass with the mass needed to see *minor*. |
| `_detect_caption` | `(major: str, minor: str) → str` | Sentence explaining a detectability panel. |
| `_strip` | `(ctx: FigureContext, el: str, title: str, by: str='sample') → dict` | Every particle as a dot per sample, coloured by its element combination. |
| `_strip_caption` | `(el: str) → str` | Sentence explaining a bubble dot plot. |
| `_minerals_for` | `(elements) → list[str]` | Reference minerals holding at least two of *elements*, for a ternary. |
| `_used` | `(s, num: str, den: str, extra: str='') → str` | Filter keeping the particles the finding's ratio was measured on. |
| `_cut_sentence` | `(s) → str` | Sentence saying which particles a ratio panel keeps, or nothing. |
| `_cut_line` | `(s, den: str) → dict` | A vertical line at the signal cut, when the cut is on the denominator. |
| `_cut_line_sentence` | `(s, den: str) → str` | Sentence explaining the signal-cut line, when the panel draws one. |
| `_bias_factor` | `(ctx: FigureContext, num: str, den: str) → float \| None` | Mass-bias correction factor for *num*/*den*, when a reference is set up. |
| `_ratio` | `(ctx: FigureContext, num: str, den: str) → str` | The ratio expression the figure plots, corrected for mass bias when it can be. |
| `_ratio_name` | `(ctx: FigureContext, num: str, den: str) → str` | Axis name of a ratio, saying when it is corrected. |
| `_bias_sentence` | `(ctx: FigureContext, num: str, den: str, natural) → str` | Sentence saying how mass bias was handled. |
| `_ratio_signal` | `(ctx: FigureContext, num: str, den: str, title: str, natural, **extra)` | The ratio of each particle against its denominator counts, with the counting band. |
| `_band_sentence` | `(den: str, natural, grouped: bool=False) → str` | Sentence explaining the counting band on a ratio-against-signal panel. |
| `_spread_sentence` | `(ctx: FigureContext, s, num: str, den: str, grouped: bool=False) → str` | Measured share inside the band and excess scatter, per sample when *grouped*. |
| `_drift_check` | `(ctx: FigureContext, s, num: str, den: str) → str` | Check, above the signal cut, whether the ratio still changes with signal. |
| `_natural_check` | `(ctx: FigureContext, s, num: str, den: str, natural) → None` | Check how far the (corrected) median ratio sits from the natural ratio. |
| `_three_isotope` | `(ctx: FigureContext, s, num: str, den: str, **extra)` | The ²⁰⁸Pb/²⁰⁶Pb against ²⁰⁷Pb/²⁰⁶Pb plot with source references, when Pb allows it. |
| `_isotope_pair` | `(s, ctx, natural=None)` |  |
| `_isotope_track` | `(s, ctx, natural=None)` |  |
| `_isotope_groups` | `(s, ctx, natural=None)` |  |
| `_limit_value` | `(ctx: FigureContext, prefix: str, label: str) → float \| None` | The detection-limit value a panel draws for *label*, or ``None``. |
| `_size_box` | `(ctx: FigureContext, value: str, title: str, y_label: str, rule: str='` | Box plot of *value* in small, medium and large particles. |
| `_size_sentence` | `(ctx: FigureContext, value: str, what: str, rule: str='') → str` | Measured medians by size class and whether they differ, adding a check. |
| `_size_caption` | `(what: str) → str` | Sentence explaining a size-class panel. |
| `_coincidence_sentence` | `(ctx: FigureContext, a: str, b: str) → str` | Co-detections against chance coincidence of two particles, adding a check. |
| `_interference` | `(s, ctx)` |  |
| `_comparison` | `(s, ctx)` |  |
| `_replicates` | `(s, ctx)` |  |
| `_signature` | `(s, ctx)` |  |
| `_share_size_sentence` | `(ctx: FigureContext, el: str, rule: str='') → str` | Measured detected share by size class, adding a check on its trend. |
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
| `_type_definition` | `(s) → dict` | The particle-type definition carried by a types card. |
| `_type_panels` | `(s, definition, title)` | The card's own PCA panel, retitled for the story. |
| `_types_overview` | `(s, ctx)` |  |
| `_particle_type` | `(s, ctx)` |  |
| `story_layout` | `(n: int, caption: str='') → tuple[list[list[float]], list[float], floa` | Place *n* panels above a caption sized to its text. |
| `caption_text` | `(title: str, captions: list[str]) → str` | Write the figure legend: the title, then one sentence per panel letter. |
| `group_names` | `(ctx: FigureContext) → list[str]` | The groups the figure compares: the samples of its table, when there are two or more. |
| `_for_group` | `(panel: dict, name: str) → dict` | A copy of *panel* showing only the particles of group *name*. |
| `_axis_range` | `(values: np.ndarray, log: bool) → tuple[float, float] \| None` | A padded range covering *values*, in log or linear terms. |
| `same_ranges` | `(ctx: FigureContext, panels: list[dict]) → list[dict]` | Give the per-group copies of an X–Y panel the same axis ranges. |
| `by_groups` | `(story: list, names: list[str], ctx: FigureContext \| None=None) → list` | Lay a story out to compare groups. |
| `arrange` | `(rows, names: list[str], between: bool)` | Choose how a grouped figure is laid out, from what the finding is about. |
| `rows_layout` | `(rows, n_groups: int, caption: str='')` | Place grouped rows above the legend: a wide panel spans its row, the others share it equally. |
| `rows_caption` | `(title: str, rows, names: list[str], views=None) → str` | The legend of a grouped figure, naming the panel of each group. |
| `_group_values` | `(ctx: FigureContext, expr: str, rule: str, names: list[str])` | ``(group, values)`` of *expr* among the particles passing *rule*, per group. |
| `_medians_between` | `(ctx: FigureContext, expr: str, rule: str, what: str, names: list[str]` | Compare a value's median between groups, adding a check; return the sentence. |
| `_correlation_between` | `(ctx: FigureContext, a: str, b: str, names: list[str]) → str` | Rank correlation of two elements in each group, adding a check; return the sentence. |
| `between_groups` | `(s, ctx: FigureContext, design, names: list[str]) → str` | The legend sentence comparing the finding between groups, with its check. |
| `figure_for` | `(s, ctx: FigureContext) → dict \| None` | Build the figure that tells a finding's story, panels a to f with a legend. |
| `context_from` | `(particles: list[dict], labels, limits: dict \| None=None, multi_sample` | Work out what a figure can show from the particles it will draw. |
