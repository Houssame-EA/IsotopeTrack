# `evidence.py`

Numbers behind a finding's figure, measured on the particles the figure draws.

The explained figure's legend should report what its panels show, not what
they are expected to show. Every function here reads the same particle table
the Figure Builder node will draw from, with the same expressions and
filters, so a number in the legend is the number in the panel.

:class:`Checks` collects the verdict line closing the legend: each check is
passed (✓), failed (✗) or undecided (–) with a short reason.

---

## Constants

| Name | Value |
|------|-------|
| `BOOTSTRAP` | `400` |
| `BAND_K` | `2.0` |
| `EXCESS_OK` | `1.3` |
| `EXCESS_LOW` | `0.6` |
| `DRIFT_RHO` | `0.15` |
| `COINCIDENCE_SHARE` | `0.1` |

## Classes

### `Checks`

The checks a figure ran, written as the legend's closing line.

| Method | Signature | Description |
|--------|-----------|-------------|
| `add` | `(self, ok: bool \| None, text: str) → None` | Record a check: ``True`` passed, ``False`` failed, ``None`` undecided. |
| `line` | `(self) → str` | The verdict line, or an empty string when nothing was checked. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `table_from` | `(units, pool) → object \| None` | The particle table a figure's selector will produce. |
| `_eval` | `(table, expr: str) → np.ndarray` | Evaluate an expression on the table as floats. |
| `mask` | `(table, rule: str='') → np.ndarray` | Particles passing a filter expression; every particle for an empty rule. |
| `values` | `(table, expr: str, rule: str='') → np.ndarray` | Finite positive values of *expr* among the particles passing *rule*. |
| `by_sample` | `(table, expr: str, rule: str='') → list[tuple[str, np.ndarray]]` | ``(sample, values)`` for every sample of the table, in its order. |
| `fmt` | `(x: float, digits: int=3) → str` | A number for a legend. |
| `pct` | `(x: float) → str` | A share as a percentage for a legend. |
| `p_text` | `(p: float) → str` | A p-value for a legend. |
| `median_ci` | `(v: np.ndarray, seed: int=0) → tuple[float, float, float]` | Median and its bootstrap 95% interval. |
| `fold_ci` | `(a: np.ndarray, b: np.ndarray, seed: int=0) → tuple[float, float, floa` | Ratio of the medians of *a* to *b* with a bootstrap 95% interval. |
| `spearman` | `(x: np.ndarray, y: np.ndarray) → tuple[float, float, int]` | Spearman's rho, its p-value and the number of pairs used. |
| `ratio_spread` | `(table, num: str, den: str, rule: str='', factor: float=1.0, group: np` | How the ratio of two isotopes scatters compared with counting statistics. |
| `ratio_drift` | `(table, num: str, den: str, rule: str='') → tuple[float, float, int]` | Rank correlation of a particle's isotope ratio with its denominator counts. |
| `replicate_medians` | `(table, expr: str, rule: str='') → dict[str, list[float]]` | Each sample's replicate medians of *expr*: sample → one median per replicate. |
| `replicate_test` | `(meds: dict[str, list[float]], log: bool=True) → tuple[float \| None, s` | Test between samples on replicate medians, when every sample has two or more. |
| `amount` | `(table) → tuple[np.ndarray, str]` | Each particle's total amount, in fg when calibrated, otherwise in counts. |
| `size_classes` | `(table, rule: str='') → list[tuple[str, np.ndarray]]` | Small, medium and large particles (thirds of total amount) among those passing *rule*. |
| `by_size` | `(table, expr: str, rule: str='') → list[tuple[str, float, int]]` | Median of *expr* in small, medium and large particles: ``(class, median, n)``. |
| `size_holds` | `(table, x_expr: str, y_expr: str, rule: str='') → list[tuple[str, floa` | Rank correlation of two expressions within each size class: ``(class, rho, n)``. |
| `detected_share_by_size` | `(table, element: str, rule: str='') → list[tuple[str, float, int]]` | Share of particles carrying *element* in each size class: ``(class, share, n)``. |
| `coincidence` | `(table, a: str, b: str) → dict \| None` | Co-detections of two elements against those expected from chance coincidence. |
| `independence` | `(table, a: str, b: str, rule: str='') → dict \| None` | Co-detections of two elements against those expected if they were independent. |
| `near_limit` | `(v: np.ndarray, limit: float \| None, factor: float=2.0) → float \| None` | Share of values within *factor* of the detection limit. |
| `_num` | `(x) → float` | A float, or NaN when *x* is not a number. |
