# `signal_stats.py`

Exclusion-aware signal statistics (non-visual).

The mean signal reported in summaries, mass-spectrum bars and exports must be
computed over the *analyzed* part of a trace only: time windows the user has
dropped with an exclusion region are not part of the acquisition any more, so
they must not contribute to the mean, the standard deviation or the RSD --
exactly as ``utils.dilution.effective_acquisition_time`` already removes them
from the acquisition time.

This also removes non-finite samples. Nu autoblanking writes ``np.nan`` into
the blanked mass/time windows (``loading.vitesse_loading.blank_nu_signal_data``),
and a single NaN turns a plain ``np.mean`` into NaN for the whole trace. A
sample that is not a number was never measured, so it is treated like excluded
time rather than poisoning the result.

Pure logic, no Qt dependency, so it can be unit-tested without a GUI.

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_time_array_for` | `(window, sample_name)` | Return the time axis stored for a sample, or None. |
| `analyzed_mask` | `(window, sample_name, element_key, signal)` | Boolean keep-mask over a signal: True where the sample counts. |
| `analyzed_signal` | `(window, sample_name, element_key, signal)` | Return only the samples that count towards signal statistics. |
| `mean_signal` | `(window, sample_name, element_key, signal, default=0.0)` | Mean signal over the analyzed part of a trace. |
| `mean_std_signal` | `(window, sample_name, element_key, signal, ddof=0, default=0.0)` | Mean and standard deviation over the analyzed part of a trace. |
