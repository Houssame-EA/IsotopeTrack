# `TE_input.py`

---

## Classes

### `InputMethodCalibration` *(extends `QMainWindow`)*

Weight-method calibration widget with live preview and direct-rate entry.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialise the Weight Method Calibration window. |
| `apply_theme` | `(self, *_)` | Re-apply styling from the current theme palette.  Covers the |
| `_init_ui` | `(self)` | Build and wire all UI elements. |
| `_create_intro_section` | `(self, parent_layout)` | Add the introductory description group box. |
| `_create_measurement_section` | `(self, parent_layout)` | Add the measurement-input group box (units + four fields). |
| `_create_calculation_section` | `(self, parent_layout)` | Add the calculation group box (preview, calculate, direct entry). |
| `_make_line_edit` | `(placeholder, validator)` | Create a QLineEdit with placeholder text and a validator. |
| `_read_inputs` | `(self)` | Parse and unit-convert all measurement fields. |
| `_set_preview` | `(self, text, style_key = 'default')` | Update the preview label's text and style. |
| `_update_preview` | `(self)` | Recalculate and display the transport rate in the preview label. |
| `_calculate` | `(self)` | Compute the transport rate, emit the result, and show a detail dialog. |
| `_submit_direct` | `(self)` | Validate and emit a user-supplied transport rate. |
