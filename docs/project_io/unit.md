# `unit.py`

Advanced Export Options dialog (visual).

The unit definitions, ``ExportUnits`` value object, formatters, and QSettings
persistence live in ``utils/unit.py``. This module only builds the dialog.

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `show_advanced_dialog` | `(parent, current: ExportUnits) → ExportUnits \| None` | Open the Advanced Options dialog and return the updated ExportUnits, |
