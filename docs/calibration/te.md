# `TE.py`

---

## Constants

| Name | Value |
|------|-------|
| `_METHOD_SIGNAL_MAP` | `{'Liquid weight': 'Weight Method', 'Number base...` |

## Classes

### `TransportRateCalibrationWindow` *(extends `QDialog`)*

Top-level dialog housing the three calibration method widgets.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, selected_methods, parent = None)` | Initialise the Transport Rate Calibration dialog. |
| `closeEvent` | `(self, event)` | Hide the window instead of destroying it on close. |
| `apply_theme` | `(self, *_)` | Re-apply all stylesheets from the current theme palette. |
| `_build_ui` | `(self)` | Construct the header, method selector, content area, and scroll wrapper. |
| `_show_selected_method` | `(self, index)` | Swap the visible calibration widget to match the combo-box selection. |
| `_on_calibration_completed` | `(self, method, transport_rate)` | Re-emit the calibration result with a standardised method name. |

## Functions

### `_ual`

```python
def _ual()
```

Return the UserActionLogger, or None if logging isn't ready.

**Returns:**

- `object: Result of the operation.`
