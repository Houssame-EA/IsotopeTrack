# `detection_registry.py`

Registry of single-particle detection threshold methods.

This module is the single source of truth for the detection methods
IsotopeTrack offers. Each method declares its stable id, the label shown in the
UI, whether the user can pick it, and the numeric hooks the detection engine
uses to turn a background level (lambda) into a threshold.

Adding a new detection method is done *here* — define a :class:`DetectionMethod`
and :func:`register` it — without editing the ``if/elif`` dispatch that used to
live in ``processing/peak_detection.py``.

The numeric hooks mirror, expression for expression, the original branches they
replaced, so detection results are unchanged. ``tests/test_detection_registry.py``
checks that equivalence against a reference transcription of the old logic.

Only numpy is imported, so this module is safe to import (and unit-test) without
PySide6, numba, or scipy.

---

## Constants

| Name | Value |
|------|-------|
| `GAUSSIAN_LOW_COUNT` | `5.0` |
| `GAUSSIAN_LOW_FRACTION` | `0.05` |
| `AUTOMATIC_LOW_BACKGROUND_ID` | `'CPLN table'` |
| `_BY_ID` | `{}` |
| `_ORDER` | `[]` |
| `DEFAULT_METHOD_ID` | `'Poisson'` |

## Classes

### `DetectionMethod`

One detection method: metadata plus the numeric hooks the engine calls.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, id, label, *, is_manual=False, user_selectable=True, single, ar` | Describe one detection method. |
| `single_threshold` | `(self, engine, lambda_bkgd, alpha, sigma)` | Threshold for a single background value. |
| `array_threshold` | `(self, engine, lambda_bkgd_array, alpha, sigma)` | Threshold for an array of background values (moving window). |
| `__repr__` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `gaussian_z` | `(alpha)` | Return the one-sided normal quantile of an error rate. |
| `is_gaussian_background` | `(signal)` | Tell whether a signal's background is high enough for a Gaussian threshold. |
| `_automatic_choice` | `(signal)` | Return the method id the Automatic choice uses for a signal. |
| `_poisson_single` | `(engine, lam, alpha, sigma)` | 3-sigma Poisson threshold (unclipped) — the historic ``else`` fallback. |
| `_poisson_array_clipped` | `(method, engine, lam_arr, alpha, sigma)` | 3-sigma Poisson threshold over an array, clipping lambda at 1. |
| `_manual_array` | `(method, engine, lam_arr, alpha, sigma)` | Manual method over an array — historically routed through the Poisson |
| `_analytic_interp_array` | `(method, engine, lam_arr, alpha, sigma)` | Interpolated thresholds across the background range for analytic methods. |
| `_cpln_lognormal_single` | `(engine, lam, alpha, sigma)` | Analytic Compound Poisson Log-Normal threshold. |
| `_cpln_table_single` | `(engine, lam, alpha, sigma)` | Lookup-table Compound Poisson Log-Normal threshold (uses caller sigma). |
| `_gaussian_single` | `(engine, lam, alpha, sigma)` | Gaussian threshold from the background level alone. |
| `_gaussian_array` | `(method, engine, lam_arr, alpha, sigma)` | Gaussian threshold over an array of background levels, with the Poisson spread. |
| `register` | `(method)` | Register a :class:`DetectionMethod` (returns it, for decorator-style use). |
| `get` | `(name)` | Return the method for ``name`` (a stored or label string). |
| `resolve` | `(name, signal)` | Return the name of the method actually applied to ``signal``. |
| `method_text` | `(threshold_data)` | Return the method a threshold was computed with, for display. |
| `all_methods` | `()` | All registered methods in registration order. |
| `selectable_labels` | `()` | UI labels for the user-selectable methods, in registration order. |
