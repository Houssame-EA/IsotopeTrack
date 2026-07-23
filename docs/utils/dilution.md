# `dilution.py`

Dilution and particle-concentration calculations (non-visual).

Pure logic operating on a window-like object that exposes the relevant
sample data. The dilution editor dialog and prompt UI live in
``tools/dilution_utils.py``; this module has no Qt-widget dependencies so it
can be unit-tested without a GUI.

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `normalize_factor` | `(value, minimum=1.0)` | Coerce a value into a valid dilution factor. |
| `get_sample_dilution` | `(window, sample_name)` | Return the dilution factor stored for a sample on a window. |
| `set_sample_dilution` | `(window, sample_name, factor)` | Store a dilution factor for a sample on a window. |
| `detect_dilution_from_name` | `(name)` | Detect a dilution factor encoded in a sample or file name. |
| `detect_dilution_for_sample` | `(window, sample_name)` | Detect a dilution factor for a sample, preferring its source file name. |
| `has_transport_rate` | `(window)` | Report whether a window has a usable transport rate calibration. |
| `effective_acquisition_time` | `(window, sample_name, element_key=None)` | Return the analyzed acquisition time in seconds for a sample. |
| `effective_volume_ml` | `(window, sample_name, element_key=None)` | Return the analyzed sample volume in millilitres for a sample. |
| `particles_per_ml` | `(window, sample_name, particle_count, element_key=None, apply_dilution` | Return the particle number concentration in particles per millilitre. |
