# `nu_raw_spectrum.py`

Resolved mass spectrum rebuilt from the ``.raw`` snapshots of a Nu run.

Besides the integrated data, Nu Instruments software writes a few raw
digitizer snapshots per run (about one per second). Each snapshot is one TOF
extraction covering the full mass range, stored as sample-to-sample
differences. Their running sum is the waveform; adding all snapshots gives a
resolved spectrum where peak shape, resolution and the position of each
integration window can be checked.

---

## Constants

| Name | Value |
|------|-------|
| `ZOOM_HALF_WIDTH` | `0.5` |
| `MIN_IONS_FOR_WIDTH` | `20` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_read_text` | `(path)` | Return the text of a plain or gzip-compressed file. |
| `_iter_records` | `(text)` | Yield the JSON records of a ``.raw`` file. |
| `read_nu_raw_spectrum` | `(folder_path)` | Sum the raw snapshots of a Nu run folder into one resolved spectrum. |
| `_time_to_mass` | `(run_info, time_ns)` | Convert flight time to m/z with the run's mass calibration. |
| `spectrum_masses` | `(run_info, n_points)` | Return the m/z of every point of a raw spectrum. |
| `integration_window` | `(run_info, target_mass)` | Return the integration and baseline windows closest to a mass. |
| `integration_windows` | `(run_info)` | Return the integration window of every measured mass. |
| `peak_check` | `(masses, spectrum, target_mass, window=None, half_width=ZOOM_HALF_WIDT` | Measure the peak nearest a mass in a resolved spectrum. |
