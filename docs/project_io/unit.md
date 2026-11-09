# `unit.py`

Units dialog (visual): one choice of units for the whole app.

The unit definitions, ``ExportUnits`` value object, formatters, persistence
and the app-wide ``units`` object live in ``utils/unit.py``. This module only
builds the dialog.

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `show_advanced_dialog` | `(parent, current: ExportUnits) → ExportUnits \| None` | Open the Units dialog and return the updated ExportUnits, or None if |
| `show_units_dialog` | `(parent) → ExportUnits \| None` | Open the Units dialog on the app's current units. |
