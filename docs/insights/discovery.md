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
| `INTERFERENCE_MIN_OVERLAP` | `10` |
| `INTERFERENCE_MIN_SHARE` | `0.7` |
| `INTERFERENCE_MIN_SHARE_PARTIAL` | `0.2` |
| `INTERFERENCE_MAX_RATIO` | `0.2` |
| `INTERFERENCE_MAX_SPREAD` | `0.3` |
| `INTERFERENCE_MAX_RATIO_NEIGHBOUR` | `0.02` |
| `INTERFERENCE_MAX_SLOPE_NEIGHBOUR` | `2.0` |
| `INTERFERENCE_CLEAR_FACTOR` | `3.0` |
| `INTERFERENCE_MIN_CLEAR` | `15` |
| `INTERFERENCE_MAX_SLOPE` | `1.6` |
| `INTERFERENCE_EXCESS_FACTOR` | `2.0` |
| `INTERFERENCE_SIBLING_REAL` | `0.3` |
| `INTERFERENCE_MIN_PLAUSIBLE` | `0.3` |
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
| `RATIO_SPLIT_MIN_PARTICLES` | `30` |
| `RATIO_SPLIT_MIN_FOLD` | `1.5` |
| `RATIO_SPLIT_MAX_ELEMENTS` | `12` |
| `RATIO_SPLIT_WITH_COLOR` | `'#c2410c'` |
| `RATIO_SPLIT_WITHOUT_COLOR` | `'#64748b'` |
| `_SUPERSCRIPT_PLUS` | `'⁺'` |
| `_SUPERSCRIPT_TWO_PLUS` | `'²⁺'` |
| `_RATE_KINDS` | `('oxide', 'hydroxide', 'doubly charged ion')` |
| `_INTERFERENCE_KIND_RANK` | `{'oxide': 0, 'doubly charged ion': 0, 'hydroxide': 1, 'hy…` |
| `ISOTOPE_MIN_PARTICLES` | `20` |
| `ISOTOPE_ABUNDANCE_GAP` | `0.25` |
| `ISOTOPE_GROUP_MIN_GAP` | `0.02` |
| `ISOTOPE_MODE_SEPARATION` | `0.01` |
| `ISOTOPE_TRACK_MIN_RHO` | `0.4` |
| `TYPES_MIN_PARTICLES` | `300` |
| `TYPES_MAX_ELEMENTS` | `10` |
| `TYPES_FIT_SIZE` | `4000` |
| `TYPES_MIN_SILHOUETTE` | `0.25` |
| `TYPES_BOOTSTRAP` | `20` |
| `TYPES_MIN_JACCARD` | `0.75` |
| `TYPES_MIN_SHARE` | `0.03` |
| `TYPES_PCA_FACTOR` | `1.5` |
| `TYPE_COLORS` | `('#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '…` |

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
| `_interference_targets` | `(mass: int, symbol: str) → list[tuple[int, str, str, bool]]` | List the masses an ion of *symbol* at *mass* can appear on. |
| `isotope_abundances` | `() → dict[str, dict[int, float]]` | Natural isotope abundances of every element, ``{symbol: {mass number: fraction}}``. |
| `_run_masses` | `(ctx) → dict[int, np.ndarray]` | Signal per particle at masses that were not selected but read from the run. |
| `_signal_by_mass` | `(ctx, run: dict) → dict[int, tuple[np.ndarray, np.ndarray]]` | Every mass on hand as ``{mass: (values, known)}``. |
| `_plausibility` | `(symbol: str, mass: int, values, detected, masses) → float` | How well an element's main isotope backs it as the parent at *mass*. |
| `_pair_stats` | `(ctx, values, detected, child: str, neighbour: bool, slope_values=None` | Measure how much *child* behaves like an interference from a parent signal. |
| `_interference_stats` | `(ctx, parent: str, child: str, neighbour: bool=False) → dict \| None` | Measure how much *child* behaves like an interference from a selected *parent*. |
| `interference_flags` | `(ctx) → list[dict]` | Decide, for every suspect mass, whether it is an interference and from what. |
| `_excess_over_oxide` | `(ctx, parents, f: dict, symbol: str, rate: float) → None` | Mark a suspect as holding a real element when even an oxide could not explain it. |
| `_sibling_check` | `(ctx, masses, parents, f: dict) → None` | Look for the suspect element on one of its isotopes the parent cannot reach. |
| `analyse_interference` | `(ctx, progress=None) → list` | Flag masses whose particles may be an interference from another element. |
| `_join` | `(items: list[str]) → str` | Join words as ``"a"``, ``"a and b"`` or ``"a, b and c"``. |
| `_flag_notes` | `(f: dict, said: set) → str` | Sentences about how one flag was reached, each said once per card. |
| `_interference_card` | `(rr, parent_symbol: str, child_symbol: str, flags: list[dict])` | Build one card for every mass of *child_symbol* explained by *parent_symbol*. |
| `_excess_card` | `(rr, child_symbol: str, flags: list[dict])` | Card for suspect masses that carry an interference and a real element as well. |
| `interference_pair` | `(ctx, a: str, b: str) → bool` | Return whether one of two masses behaves like an interference from the other. |
| `analyse_stoichiometry` | `(ctx, progress=None) → list` | Find element pairs held at a fixed ratio, the mark of one defined phase. |
| `ratio_split_rules` | `(c: str) → dict` | Grouping rules splitting particles by whether they carry *c*. |
| `ratio_split_panel` | `(a: str, b: str, c: str) → dict` | The scatter that shows a ratio split: a/b against b, coloured by c, grey without c. |
| `analyse_ratio_split` | `(ctx, progress=None) → list` | Find element ratios that take two values depending on whether a third element is present. |
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
| `ratio_cut` | `(ctx, num: str, den: str) → tuple[str, float] \| None` | The signal cut an isotope ratio is measured above. |
| `ratio_values` | `(ctx, num: str, den: str) → tuple[np.ndarray, np.ndarray]` | Return the particles usable for a ratio, and the ratio in each. |
| `_natural_ratio` | `(num: str, den: str) → float \| None` | Natural abundance ratio of two isotopes, or ``None`` when unknown. |
| `_ratio_config` | `(num: str, den: str, x_axis: str) → dict` | Isotopic ratio plot settings for one ratio. |
| `analyse_isotope_ratios` | `(ctx, progress=None) → list` | Examine every isotope ratio within one material. |
| `analyse_isotope_groups` | `(ctx, progress=None) → list` | Compare each isotope ratio between replicate groups. |
| `_type_elements` | `(ctx, matrix, det, multi) → list[str]` | One isotope per element, detected in at least 5 % of the multi-element particles. |
| `_bootstrap_jaccard` | `(X, labels, k, rng) → np.ndarray` | Mean Jaccard similarity of each cluster with its best match over bootstrap refits. |
| `_type_name` | `(det_rows: np.ndarray, shares: np.ndarray, elements: list[str]) → str` | Name a type by the elements most of its particles carry, largest share first. |
| `find_particle_types` | `(ctx, progress=None)` | Look for stable particle types among the multi-element particles. |
| `_types_spec` | `(found, title, highlight=None) → dict` | Figure Builder design: PCA of the compositions, particles coloured by type. |
| `_share_text` | `(stat, groups) → list[tuple[str, str]]` | Share of the type in each sample group, as detail rows. |
| `analyse_particle_types` | `(ctx, progress=None) → list` | Report stable particle types, if the multi-element particles fall into any. |
