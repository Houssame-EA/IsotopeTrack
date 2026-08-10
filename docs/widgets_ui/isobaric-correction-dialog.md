# `isobaric_correction_dialog.py`

Isobaric Correction dialog — calculator-style equation editor.

Overlaps come from the known interference list in
data/interference_corrections.json. Every analyte channel has one correction
equation. The default is the published table equation; the user can replace
it with any calculator-style expression:

    raw - 0.230074*Hg202 + 2*(Ar38/K39) - sqrt(Pt195)

'raw' is the analyte channel; Element+mass tokens (Hg202, Ar38, Cr54)
reference measured channels; + - * / ** parentheses and log, log10, sqrt,
exp, abs are supported. The result is always clamped at zero.

Custom equations persist in data/isobaric_overrides.json and are restored
next session. 'Reset to default' brings back the table equation. Analytes are
listed by atomic mass, lowest first. Open with:

    from widget.isobaric_correction_dialog import IsobaricCorrectionDialog
    IsobaricCorrectionDialog(self).exec()

---

## Classes

### `IsobaricCorrectionDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window, parent=None)` | Initialise the dialog and load equations for the current selection. |
| `_build_ui` | `(self)` | Build and lay out all widgets in the dialog. |
| `reload` | `(self)` | Refresh the dialog for reuse without recreating it. |
| `_load_entries` | `(self)` | Build one equation entry per selected analyte, sorted by mass. |
| `_validate_entry` | `(self, entry: dict)` | Validate an entry's expression and store enabled/note on it. |
| `_is_custom` | `(self, entry: dict) → bool` | True when the entry's expression differs from the table default. |
| `_populate_table` | `(self, select_row: int=0)` | Fill the analyte table from the current entries. |
| `_update_row` | `(self, r: int)` | Refresh one table row from its entry after edits. |
| `_persist_entry` | `(self, entry: dict)` | Save (or clear) the custom equation for one analyte to disk. |
| `_raw_base_for` | `(self, sample)` | Return channel data with any previously applied corrections restored to raw. |
| `_corrections_for` | `(self, entries)` | Build engine correction objects for the given entries. |
| `_effective_corrections` | `(self)` | Return enabled correction objects for every analyte entry. |
| `_selected_row` | `(self)` | Index of the selected table row, or None. |
| `_on_expression_changed` | `(self, text: str)` | Validate, store, and persist the edited expression live. |
| `_on_reset_analyte` | `(self)` | Restore the reference-table equation for the selected analyte. |
| `_refresh_equations` | `(self, entry: dict)` | Update the default and active equation labels for an entry. |
| `_refresh_preview` | `(self, entry: dict)` | Re-draw the IN/OUT preview plot for an entry's analyte channel. |
| `_on_row_selected` | `(self)` | Load the editor, equations, and preview for the selected analyte. |
| `_on_apply` | `(self)` | Apply every enabled equation to the working data. |
| `_on_revert` | `(self)` | Revert all applied corrections and restore the original raw signal. |
| `_update_button_states` | `(self)` | Sync button enabled states with the current correction status. |
| `_refresh_main_plot` | `(self)` | Redraw the main window's current trace so the applied correction is visible. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_plot_colors` | `()` | Return (background, foreground, raw_pen, corrected_pen) colours for the preview plot. |
