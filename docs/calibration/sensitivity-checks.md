# `sensitivity_checks.py`

Quality checks on an ionic calibration.

Pure numpy/scipy, no Qt, so every check can be unit-tested on its own. The
Ionic Calibration window runs them after each calculation and lists the
results in its Checks window.

Checks
------
* :func:`slope_uncertainty` – standard error and 95 % interval of a slope
* :func:`linearity_check` – does the top standard fall below the line?
* :func:`abundance_check` – do isotopes of one element scale with abundance?
* :func:`repeat_standard_drift` – do repeated standards agree over the run?
* :func:`blank_source` – which standard the LOD/LOQ noise comes from
* :class:`SensitivityHistory` – slopes saved per day, compared with the last day

---

## Constants

| Name | Value |
|------|-------|
| `LINEARITY_LIMIT_PCT` | `5.0` |
| `ABUNDANCE_LIMIT_PCT` | `10.0` |
| `DRIFT_LIMIT_PCT` | `5.0` |
| `HISTORY_LIMIT_PCT` | `20.0` |

## Classes

### `SensitivityHistory`

Slopes kept per day in a small JSON file, to follow the instrument.

One entry per isotope and day: saving again on the same day replaces
that day's value. :meth:`previous` returns the latest earlier day.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, path=None)` |  |
| `_load` | `(self)` |  |
| `record` | `(self, slopes, day=None)` | Store {isotope_key: slope} for *day* (today by default) and save. |
| `previous` | `(self, key, day=None)` | (day, slope) of the latest entry before *day*, or None. |
| `compare` | `(self, key, slope, day=None, limit_pct=HISTORY_LIMIT_PCT)` | Change of *slope* against the latest earlier day. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `slope_uncertainty` | `(x, y, y_std=None, method='simple')` | Standard error and 95 % confidence half-width of a calibration slope. |
| `linearity_check` | `(x, y, limit_pct=LINEARITY_LIMIT_PCT)` | Test whether the highest standard falls below the line of the others. |
| `abundance_check` | `(isotopes, limit_pct=ABUNDANCE_LIMIT_PCT)` | Compare the isotopes of each element with their natural abundance. |
| `repeat_standard_drift` | `(x, y, limit_pct=DRIFT_LIMIT_PCT)` | Compare standards measured more than once during the run. |
| `blank_source` | `(x)` | Describe which standard the LOD/LOQ noise comes from. |
| `drift_factors` | `(x, y, included=None)` | Relative sensitivity at each standard, from standards measured more than once. |
