# `sia_stats.py`

Statistics and history for single-ion area (SIA) distributions.

Qt-free helpers used by :mod:`loading.SIA_manager`:

* per-mass sigma summary with standard errors, a robust outlier rule
  (modified z-score on the median absolute deviation) and an
  inverse-variance weighted mean,
* a weighted straight-line fit of sigma against m/z,
* isotope labels for an m/z value,
* a small JSON history of loaded SIAs with control limits.

---

## Constants

| Name | Value |
|------|-------|
| `MASS_MATCH_TOL` | `2.0` |
| `ISOTOPE_LABEL_TOL` | `0.5` |
| `ROBUST_Z_LIMIT` | `3.5` |
| `MIN_HISTORY_FOR_LIMITS` | `3` |
| `_SUPERSCRIPT` | `str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')` |

## Classes

### `SIAHistory`

SIA records kept in a JSON file to follow the detector between sessions.

Loading the same SIA again (same instrument, source and acquisition
time) replaces its record instead of adding a new one.

Args:
    path (str | None): JSON file; :func:`default_history_path` when None.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, path=None)` |  |
| `_load` | `(self)` |  |
| `save` | `(self)` | Write the history to disk. |
| `sorted_entries` | `(self)` | Records sorted by date. |
| `record` | `(self, entry)` | Add or replace a record and save. |
| `remove` | `(self, key)` | Delete a record by key and save. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `sigma_standard_error` | `(sigma, n)` | Approximate standard error of a lognormal sigma estimated from n events. |
| `robust_outlier_mask` | `(values, limit=ROBUST_Z_LIMIT)` | Flag outliers with the modified z-score of Iglewicz and Hoaglin. |
| `weighted_mean_sd` | `(values, weights)` | Weighted mean and weighted standard deviation. |
| `linear_trend` | `(x, y, weights=None)` | Weighted least-squares straight line ``y = a + b x``. |
| `summarize_per_mass` | `(per_mass, exclude_outliers=False)` | Summary of the per-mass sigma values used by the comparison plot. |
| `effective_sigma` | `(calculated_sigma, per_mass, exclude_outliers)` | Sigma the application should use. |
| `nearest_per_mass` | `(per_mass, target_mass, tol=MASS_MATCH_TOL)` | Per-mass entry closest to a target m/z. |
| `superscript_label` | `(label)` | Turn an isotope label such as ``'56Fe'`` into ``'⁵⁶Fe'``. |
| `isotope_index` | `(elements)` | Flat list of natural isotopes from periodic-table element records. |
| `isotopes_at_mass` | `(index, mass, tol=ISOTOPE_LABEL_TOL, preferred=())` | Isotope labels found at an m/z value. |
| `mass_label` | `(mass, index, preferred=())` | Isotope label for an m/z value. |
| `parse_datetime` | `(text)` | Parse an ISO-like date string. |
| `history_entry` | `(info, per_mass, source_path, effective=None, now=None)` | Build one history record from a loaded SIA. |
| `control_limits` | `(values)` | Mean and ±2 SD / ±3 SD limits of earlier values. |
| `classify` | `(value, limits)` | Where a value falls against control limits. |
| `default_history_path` | `()` | Location of the SIA history file next to the other app data. |
