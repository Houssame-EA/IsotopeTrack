# `acquisition.py`

Raw signals and per-sample results for the assistant.

The particle table only holds what was detected. Many questions need what
the main window measured around it: the raw trace of a run, the ionic
background, the detection limits, particles per mL and the mass
concentration. This module reads those stores without changing them and
hands them over as plain arrays and one pandas table, computed with the same
formulas as the summary export, so the assistant and the exported files give
the same numbers.

Two sources share one interface: :class:`WindowAcquisition` reads a live main
window and :class:`StaticAcquisition` holds prepared arrays and rows, for the
tests, the benchmark and training data. Nothing here touches Qt.

---

## Constants

| Name | Value |
|------|-------|
| `METHOD_KEYS` | `{'Force through zero': 'zero', 'Simple linear': 'simple',…` |
| `SUMMARY_COLUMNS` | `['sample', 'run', 'element', 'particles', 'particles_per_…` |

## Classes

### `Acquisition`

Raw traces and per-run results, the interface the sandbox uses.

Subclasses provide :meth:`run_names`, :meth:`labels`, :meth:`trace` and
:meth:`_rows`; grouping, element lookup and caching live here.

Attributes:
    groups (dict): ``{run: sample}`` when runs were pooled into samples
        before reaching the assistant; runs absent map to themselves.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, groups=None)` | Create the source. |
| `run_names` | `(self)` | Return the runs whose raw signal is available. |
| `labels` | `(self, run)` | Return the isotope labels recorded for *run*. |
| `trace` | `(self, run, label)` | Return ``(time_s, counts)`` arrays of one channel, or ``None``. |
| `_rows` | `(self)` | Return the per-run, per-element result dictionaries. |
| `sample_of` | `(self, run)` | Return the sample a run belongs to. |
| `resolve_run` | `(self, name)` | Map a run or sample name to one run. |
| `signal` | `(self, sample, element, t0=None, t1=None)` | Raw trace of one element in one run. |
| `summary` | `(self)` | Per-run, per-element results, built once. |

### `StaticAcquisition` *(extends `Acquisition`)*

Prepared traces and rows, for the tests, the benchmark and training.

Args:
    signals (dict): ``{run: {label: (time_s, counts)}}``.
    rows (list): Summary rows; ``sample`` is filled from *groups* when absent.
    groups (dict): ``{run: sample}`` of pooled runs.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, signals=None, rows=None, groups=None)` | Store the prepared data. |
| `run_names` | `(self)` | Return the runs that carry a trace. |
| `labels` | `(self, run)` | Return the labels of one run. |
| `trace` | `(self, run, label)` | Return the stored arrays of one channel. |
| `_rows` | `(self)` | Return the given rows with the sample column filled in. |

### `WindowAcquisition` *(extends `Acquisition`)*

Reads the main window's stores, read-only.

Args:
    window: The main window.
    runs (list): Runs to expose, or ``None`` for every loaded sample.
    groups (dict): ``{run: sample}`` of pooled runs.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, window, runs=None, groups=None)` | Bind to the window. |
| `available` | `(window)` | Whether *window* holds raw signals at all. |
| `run_names` | `(self)` | Return the runs with raw data. |
| `_elements` | `(self)` | Return ``(element_key, label, symbol, mass)`` of the selected isotopes, by mass. |
| `_channels` | `(self, run)` | Return the ``{mass: array}`` channels of a run. |
| `_channel` | `(self, run, mass)` | Return the signal array of the channel nearest *mass*, or ``None``. |
| `_time` | `(self, run)` | Return the time axis of a run in s, or ``None``. |
| `labels` | `(self, run)` | Return the labels of the selected isotopes present in *run*. |
| `trace` | `(self, run, label)` | Return the time axis and the signal of one channel. |
| `_slope` | `(self, key)` | Return ``(slope cps/ppb, method name)`` of the ionic calibration. |
| `_density` | `(self, symbol)` | Return the element density in g/cm3, or NaN. |
| `_compound` | `(self, key, run, symbol)` | Return ``(mass fraction, density)`` of the compound set for an element. |
| `_mean_diameter` | `(self, masses, density)` | Mean sphere diameter in nm of *masses* at *density*, or NaN. |
| `_acquisition_s` | `(self, run, key)` | Analyzed acquisition time of a run, exclusions removed. |
| `_analyzed` | `(self, run, key, y)` | Signal with excluded regions and non-finite points removed. |
| `_rows` | `(self)` | Compute one row per run and selected isotope, as the summary export does. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `match_label` | `(name, labels)` | Find the isotope label a user or model meant among *labels*. |
| `_num` | `(v)` | Return *v* as a float, or NaN when it is missing or not a number. |
| `from_dataset` | `(data_context, parent_window, run_to_sample=None)` | Pick the acquisition source for a dataset. |
