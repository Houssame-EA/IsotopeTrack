# `dilution_utils.py`

---

## Classes

### `DilutionFactorDialog` *(extends `QDialog`)*

Per sample dilution factor editor with filename auto detection.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window, sample_names)` | Build the dilution factor dialog for the given samples. |
| `_build_ui` | `(self)` | Construct the dialog widgets and populate stored values. |
| `_apply_detected` | `(self, sample_name, value)` | Set a single sample spinbox to a detected dilution factor. |
| `_apply_all_detected` | `(self)` | Apply every detectable dilution factor to its sample spinbox. |
| `_reset_all` | `(self)` | Reset every sample spinbox to a dilution factor of one. |
| `_save` | `(self)` | Persist all spinbox values into the main window dilution store. |

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
| `open_dilution_factor_dialog` | `(window)` | Open the per sample dilution factor editor for a window. |
| `maybe_prompt_dilution` | `(window)` | Show a one time prompt inviting dilution correction of particles per mL. |
| `highlight_tools_menu` | `(window)` | Briefly animate the Tools menu to indicate where dilution is entered. |
