# `discovery.py`

Detectors that search particle data for findings worth a plot node.

Each detector takes an :class:`~results.insights.engine.AnalysisContext` and
returns :class:`~results.insights.engine.Suggestion` cards. Detectors that look
*inside* a material (interferences, stoichiometry, co-occurrence, rare
particles, composition shape) are run once per replicate group by the engine
in :mod:`results.insights.engine`; detectors that look *across* samples handle
the groups themselves.

The statistics favour being quiet over being wrong. Every detector applies an
effect-size floor on top of any significance test, families of tests are
corrected for false discovery, and replicate groups are compared as groups so
that two replicates of one material are never reported as different samples.

---

## Constants

| Name | Value |
|------|-------|
| `MIN_GROUP_PARTICLES` | `20` |
| `INTERFERENCE_MIN_OVERLAP` | `15` |
| `INTERFERENCE_MIN_SHARE` | `0.7` |
| `INTERFERENCE_MAX_RATIO` | `0.2` |
| `INTERFERENCE_MAX_SPREAD` | `0.3` |
| `STOICHIOMETRY_MIN_OVERLAP` | `30` |
| `STOICHIOMETRY_MAX_SPREAD` | `0.2` |
| `STOICHIOMETRY_MAX_COUPLING` | `0.4` |
| `COOCCURRENCE_MIN_CONFIDENCE` | `0.8` |
| `COOCCURRENCE_MIN_LIFT` | `1.5` |
| `COOCCURRENCE_AVOID_RATIO` | `0.25` |
| `RARE_MAX_COUNT` | `25` |
| `RARE_MIN_COUNT` | `3` |
| `DETECTION_LIMIT_MIN_SHARE` | `0.15` |
| `SIZE_TREND_MIN_RHO` | `0.3` |
| `TIME_MIN_PARTICLES` | `200` |
| `TIME_DRIFT_MIN_FOLD` | `1.25` |
| `REPLICATE_FOLD` | `1.5` |
| `REPLICATE_RATE_GAP` | `0.15` |
| `REPLICATE_MARGIN` | `2.0` |
| `_SUPERSCRIPT_PLUS` | `'⁺'` |
| `_SUPERSCRIPT_TWO_PLUS` | `'²⁺'` |
| `ISOTOPE_MIN_PARTICLES` | `20` |
| `ISOTOPE_ABUNDANCE_GAP` | `0.25` |
| `ISOTOPE_GROUP_MIN_GAP` | `0.02` |
| `ISOTOPE_MODE_SEPARATION` | `0.01` |
| `ISOTOPE_TRACK_MIN_RHO` | `0.4` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_rr` | `()` | Return :mod:`results.insights.engine`, imported on first use. |
| `mass_symbol` | `(label: str) → tuple[int \| None, str \| None]` | Split an isotope label into mass number and symbol. |
| `same_element` | `(a: str, b: str) → bool` | Return whether two labels are isotopes of one element. |
| `mass_related` | `(a: str, b: str) → bool` | Return whether two masses could be an oxide, hydroxide or M²⁺ of each other. |
| `_robust_sd` | `(values: np.ndarray) → float` | Spread of *values* from the median absolute deviation, scaled to a standard deviation. |
| `_config_key` | `(config: dict) → str` | Stable text form of a node config, used to tell findings apart. |
| `_n_elements` | `(ctx) → np.ndarray` | Number of elements detected in each particle, cached on the context. |
| `_times` | `(ctx) → np.ndarray` | Particle start times in seconds, ``nan`` where missing, cached on the context. |
| `_figure_spec` | `(data_type: str, **panel) → dict` | Build a one-panel Figure Builder design. |
| `_simple_ratio` | `(value: float, max_term: int=4, tolerance: float=0.08) → str \| None` | Name the small whole-number ratio closest to *value*, if one is close. |
| `analyse_interference` | `(ctx, progress=None) → list` | Find masses that behave like an oxide, hydroxide or doubly charged ion. |
| `interference_pair` | `(ctx, a: str, b: str) → bool` | Return whether one of two masses behaves like an interference from the other. |
| `_interference_stats` | `(ctx, parent: str, child: str) → dict \| None` | Measure how much *child* behaves like an interference from *parent*. |
| `analyse_stoichiometry` | `(ctx, progress=None) → list` | Find element pairs held at a fixed ratio, the mark of one defined phase. |
| `analyse_cooccurrence` | `(ctx, progress=None) → list` | Find elements that turn up together, or avoid each other, more than chance allows. |
| `analyse_rare` | `(ctx, progress=None) → list` | Point out elements found in only a handful of particles. |
| `analyse_network` | `(ctx, progress=None) → list` | Find a connected group of four or more mutually correlated elements. |
| `analyse_ternary` | `(ctx, progress=None) → list` | Suggest a ternary plot for the most common three-element particles. |
| `analyse_single_multi` | `(ctx, progress=None) → list` | Contrast elements found alone with elements found in mixtures. |
| `analyse_detection_limit` | `(ctx, progress=None) → list` | Flag distributions cut off by the detection limit. |
| `analyse_size_composition` | `(ctx, progress=None) → list` | Find elements whose share of a particle changes with particle size. |
| `analyse_time` | `(ctx, progress=None) → list` | Check each sample's acquisition for drift and bursts. |
| `_rate_finding` | `(name: str, t: np.ndarray)` | Test one sample's particle arrival rate for drift or bursts. |
| `_signal_drift` | `(ctx, name: str, in_sample: np.ndarray, t_all: np.ndarray)` | Follow the median signal of the main elements in one sample over time. |
| `_replicate_metrics` | `(ctx, indices: list[int], elements: list[str]) → dict` | Summarise each replicate on the measures used to judge agreement. |
| `_disagreement` | `(kind: str, values: list[float]) → tuple[int \| None, float, float] \| N` | Find a replicate that disagrees with its siblings on one measure. |
| `analyse_replicates` | `(ctx, progress=None) → list` | Check that replicates of one material agree, and say which one does not. |
| `_describe_gap` | `(kind: str, gap: float) → str` | Word a replicate gap as a fold or a percentage-point difference. |
| `_replicate_flag_card` | `(rr, group, members, flags, flagged_elements, sample_cfg)` | Build the card for a replicate group with a disagreement. |
| `_replicate_agree_card` | `(rr, group, members, metrics, elements, sample_cfg)` | Build the card for a replicate group whose replicates agree. |
| `merge_group_findings` | `(items, scope_order, n_groups: int) → list` | Merge the same finding reported by several replicate groups into one card. |
| `isotope_pairs` | `(ctx, max_per_element: int=3) → list[tuple[str, str, str]]` | List the isotope ratios to examine: two isotopes of the same element. |
| `ratio_values` | `(ctx, num: str, den: str) → tuple[np.ndarray, np.ndarray]` | Return the particles usable for a ratio, and the ratio in each. |
| `_natural_ratio` | `(num: str, den: str) → float \| None` | Natural abundance ratio of two isotopes, or ``None`` when unknown. |
| `_ratio_config` | `(num: str, den: str, x_axis: str) → dict` | Isotopic ratio plot settings for one ratio. |
| `analyse_isotope_ratios` | `(ctx, progress=None) → list` | Examine every isotope ratio within one material. |
| `analyse_isotope_groups` | `(ctx, progress=None) → list` | Compare each isotope ratio between replicate groups. |
