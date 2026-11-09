# `unit_combo.py`

A combo box of data types that shows them in the app's chosen units.

The items keep their saved names (``"Element Mass (fg)"``) for the code and
the project files, while the user sees ``"Element Mass (pg)"`` when the mass
unit is pg. Choosing other units relabels the items at once.

---

## Constants

| Name | Value |
|------|-------|
| `KEY_ROLE` | `Qt.ItemDataRole.UserRole + 41` |

## Classes

### `UnitComboBox` *(extends `QComboBox`)*

Combo box whose texts follow the app's units and whose API uses the saved names.

``currentText``, ``setCurrentText``, ``findText`` and ``itemText`` all
work with the saved names, so code written for a plain ``QComboBox`` of
data types keeps working unchanged.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `_key` | `(self, index)` |  |
| `_relabel` | `(self, *_)` | Show every item in the newly chosen units, keeping the choice. |
| `addItem` | `(self, *args)` | Add one data type; the text may be preceded by an icon, as for ``QComboBox``. |
| `addItems` | `(self, texts)` | Add several data types. |
| `insertItem` | `(self, index, *args)` | Insert one data type at *index*. |
| `itemText` | `(self, index)` | The saved name of the item at *index*. |
| `setItemText` | `(self, index, text)` | Rename the item at *index*; *text* is a saved name. |
| `currentText` | `(self)` | The saved name of the chosen data type. |
| `findText` | `(self, text, flags=Qt.MatchFlag.MatchExactly \| Qt.MatchFlag.MatchCaseS` | Index of the item whose saved name (or shown text) is *text*, or -1. |
| `setCurrentText` | `(self, text)` | Choose the item whose saved name (or shown text) is *text*. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_disconnect` | `(slot)` |  |
