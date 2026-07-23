# `dilution_utils.py`

Dilution factor UI: the per-sample editor dialog and the one-time prompt.

The underlying calculations (dilution detection, effective volume,
particles/mL, etc.) live in ``utils/dilution.py``. This module only builds
the Qt dialogs and menu hints.

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
| `open_dilution_factor_dialog` | `(window)` | Open the per sample dilution factor editor for a window. |
| `maybe_prompt_dilution` | `(window)` | Show a one time prompt inviting dilution correction of particles per mL. |
| `highlight_tools_menu` | `(window)` | Briefly animate the Tools menu to indicate where dilution is entered. |
