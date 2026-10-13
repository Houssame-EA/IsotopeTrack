# `analysis.py`

spICP-ToF-MS analyses the assistant calls instead of writing them itself.

Every function takes the :class:`~results.ai.data.Dataset` first; the sandbox
binds it, so generated code calls ``compare_samples("Ti")`` directly. Each
returns a pandas DataFrame the model can pass straight to ``show_table``.
Test results and caveats go in ``df.attrs["note"]``, which the table header
shows.

The statistics are deliberately conventional: Kruskal-Wallis and
Mann-Whitney for distributions, a Poisson test of shared events against
the expected random coincidence rate, chi-square
residuals for combination enrichment, and Holm's correction whenever many
tests are run together.

---

## Constants

| Name | Value |
|------|-------|
| `_RNG_SEED` | `7` |
| `P_FLOOR` | `1e-300` |
| `FUNCTIONS` | `{'element_summary': element_summary, 'compare_samples': c…` |
| `SIGNATURES` | `[("element_summary(quantity='diameter_nm', by=None, eleme…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `pfloor` | `(p)` | Keep a p-value off exact zero, which floating point reaches but statistics never does. |
| `holm` | `(pvalues)` | Holm step-down adjustment of a list of p-values. |
| `_note` | `(df, text)` | Attach a caveat or test result to a table and return it. |
| `_values` | `(ds, quantity, element, mask=None)` | Positive, finite values of one quantity of one element. |
| `_median_ci` | `(values, n_boot=400)` | Bootstrap 95 % interval of the median. |
| `_geo` | `(v)` | Geometric mean and geometric standard deviation of positive values. |
| `_log_kde` | `(v)` | KDE of log10 values, or ``None`` when there are too few or identical values. |
| `_log_mode` | `(v)` | Most likely value of a positive distribution, from a KDE on the log scale. |
| `_height_at` | `(v, x)` | Height of the log-scale density at *x*, as a share of its peak. |
| `_groups` | `(ds, by)` | Group keys for *by*, which is ``sample``, ``run``, ``class`` or ``None``. |
| `element_summary` | `(ds, quantity='diameter_nm', by=None, elements=None)` | Detection frequency and distribution of a quantity for every element. |
| `compare_samples` | `(ds, element, quantity='diameter_nm', by='sample', groups=None)` | Compare one element's distribution across samples, with tests. |
| `_pair_counts` | `(ds, a, b)` | Particles with a, with b, with both, and in total. |
| `coincidence` | `(ds, element_a, element_b)` | Are particles with both elements real, or two particles arriving together? |
| `co_occurrence` | `(ds, elements=None, min_count=10, top=25)` | Which element pairs share particles more, or less, than chance allows. |
| `coincidence_overview` | `(ds)` | How many multi-element events could be chance coincidences, run by run. |
| `size_distribution` | `(ds, element, quantity='diameter_nm', by='sample')` | Shape of one element's size or mass distribution, with truncation checks. |
| `near_detection_limit` | `(ds, quantity='mass_fg', factor=1.5, min_count=5)` | Elements whose detections crowd against the detection limit. |
| `find_outliers` | `(ds, quantity='mass_fg', element=None, threshold=5.0, top=50)` | Particles far outside their element's usual range. |
| `time_bursts` | `(ds, element=None, bin_s=None, alpha=0.01)` | Stretches of a run where particles arrive far faster than usual. |
| `combination_enrichment` | `(ds, by='sample', min_count=5, top=30)` | Element combinations over- or under-represented in a sample. |
| `long_format` | `(ds, quantity='diameter_nm', elements=None)` | One row per particle and element, handy for per-element plots. |
| `cluster_particles` | `(ds, elements=None, k=3, algorithm='K-Means', scaling='CLR', quantity=` | Cluster particles by composition with the Clustering module's engine. |
